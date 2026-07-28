# ir schema 响应字段契约与 token 效率优化

## Summary

**问题核实（issue #64 属实，部分已过时）**：
- `ir schema`（`ir-cli/ir_cli/schema.py`，183 行）确实零响应字段契约：`build_schema()` 仅输出 protocol/conventions/enums/error_hints/workflows/commands，全文无 `market_value`/`amount` 等字段登记。
- `position list` 行内 `amount` 对基金行恒为 null **属设计约束**（`portfolio_position` CHECK：`shares`/`amount` 二选一，净值型 vs 非净值型），不是后端 bug——正确解法是契约标注，不是改后端。
- issue 中第 3、4 点（`date` 字段名、`data.data` 双层嵌套）**已随 #62（CLOSED）修复**：`portfolio_service.get_nav_history()`（L94-118）现返回单层列表且字段名为 `snapshot_date`。本计划无需再修，仅需契约固化。
- **关键技术事实**：`backend/openapi.json` 中 list 类 GET 端点响应 schema 为空 `{}`（router 未声明 response_model），但 `components.schemas` 中 `PositionResponse`/`TradeResponse`/`SubscriptionResponse`/`SnapshotStatusResponse` 字段与 nullable 信息齐全。因此生成脚本必须走「命令 → component schema 名」显式映射表，而非解析 paths。nav-history 无 Pydantic 模型，需在后端补一个。

**方案**（遵循维护者评论定调）：openapi.json 生成 + 少量人工 override + CI freshness check；首期仅覆盖 `position list`、`portfolio nav-history`、`snapshot status`、`trade list`、`sub list`；字段挂到 `commands.<group>.<sub>.output`。叠加 token 优化：紧凑字段编码 + `ir schema --index` 轻量索引模式（实测全量 schema ≈ 7,100 tokens，单 group ≈ 1,400 tokens，索引 < 300 tokens）。

## 后端最小补强（backend/）

1. **新增 `NavHistoryRecord` Pydantic 模型**：`backend/app/schemas/portfolio.py` 中新增（字段：`snapshot_date: date`、`unit_price/total_value/total_shares: Optional[float]`，与 `get_nav_history()` 返回 dict 完全一致）。
2. **nav-history 端点声明 `response_model=list[NavHistoryRecord]`**：`backend/app/routers/portfolios.py` 的 nav-history 路由（约 L99-107）。仅类型声明，不改返回逻辑；前端无消费方（已核实 frontend 无 nav-history 引用），后端 CLI 已兼容单层结构，零破坏面。
3. **重新导出 openapi.json**：运行 `backend/export_openapi.py` 更新 `backend/openapi.json`，使 nav-history 字段进入 `components.schemas`。

## 生成脚本与契约数据（ir-cli/）

4. **新建生成脚本 `ir-cli/scripts/gen_response_fields.py`**：
   - 输入：`backend/openapi.json` + 脚本内置映射表 `COMMAND_SCHEMA_MAP`（首期 5 条）：
     | 命令 | component schema | shape |
     |---|---|---|
     | position.list | PositionResponse | list |
     | portfolio.nav-history | NavHistoryRecord | list |
     | snapshot.status | SnapshotStatusResponse | object |
     | trade.list | TradeResponse | list |
     | sub.list | SubscriptionResponse | list |
   - 从 `components.schemas` 抽取字段名/类型/nullable（`anyOf` + null 判定 nullable）。
   - **紧凑编码**（token 优先，不用对象数组）：字段拼为单行字符串，如 `"id:int,portfolio_code:str,shares:num?,market_value:num?,amount:num?,snapshot_date:date"`；`?` 后缀 = nullable；`*` 前缀 = 属默认摘要字段（对照 `ir_cli/utils.py` 的 `SUMMARY_FIELDS`，由脚本自动标注）。
   - **人工 override 层**：脚本内 `NOTES_OVERRIDES` dict，仅登记语义标注，首期至少含：
     - `position.list.amount`: "仅CASH行有值，基金行恒为null（CHECK约束二选一），市值请用market_value"
     - `position.list.shares`: "净值型资产有值，CASH行为null"
     - `portfolio.nav-history.total_value`: "组合总市值（快照口径，对应持仓行market_value之和）"
     - `portfolio.nav-history` 整体: "单层列表按日期升序，日期字段为snapshot_date（#62已修复）"
   - 输出：生成 `ir-cli/ir_cli/response_fields.py`（含 `RESPONSE_FIELDS` dict + "AUTO-GENERATED, do not edit" 头注释），随包提交，**保持 ir-cli 无运行时后端依赖**。
   - 支持 `--check` 模式：重新生成并与现存文件比对，不一致时 exit 1（供 CI 用）。

5. **schema.py 集成**：`build_schema()` / `_command_entry()` 改造——按 `(group, sub)` 查 `RESPONSE_FIELDS`，命中则在命令条目加 `"output": {"shape": "list|object", "fields": "<紧凑串>", "notes": {...}}`。全量与 `ir schema <group>` 视图均携带（5 个命令的紧凑串合计增量约 600 tokens，可接受）。

## 索引模式与约定更新（token 节省）

6. **新增 `ir schema --index`**：`ir_cli/main.py` schema 命令加 `--index` flag，`build_schema()` 加 `index_only` 参数——仅输出 `{protocol(精简), groups: {组名: [子命令名]}}`（< 1KB）。默认行为完全不变，向后兼容。
7. **更新 `CONVENTIONS`**（schema.py L26-33）：新增两条——`output.fields` 编码规则说明（`?`=可空、`*`=默认摘要字段、notes 为字段级警示），以及「先 `ir schema --index` 再 `ir schema <group>` 按需加载」的推荐用法（实测按 group 加载较全量省约 59% token）。

## CI 防漂移与测试

8. **CI freshness check**：`.github/workflows/ci.yml` 新增轻量 step（无需起后端服务）：`python ir-cli/scripts/gen_response_fields.py --check`，不一致即 fail 并提示重新生成。放在现有 backend job 之后或独立 job（仅需 python + 仓库文件）。
9. **新增 ir-cli 首个测试 `ir-cli/tests/test_schema.py`**：断言①5 个命令条目均含 `output.fields` 且字段串包含关键字段（如 position.list 含 `market_value` 与 `amount?`）；②`--index` 输出不含 params/output 细节；③默认 `ir schema` 结构向后兼容（protocol/enums/commands 键仍在）。
10. **回归验证**：跑 `backend/tests/integration/test_market_data_coverage.py`（nav-history #62 用例）确认 response_model 声明未改变响应结构；手动 `ir schema position | python -m json.tool` 抽查。

## 文档与收尾

11. **AGENTS.md §6** 追加一行：ir-cli 的 `ir schema` 已含响应字段契约（`output.fields`）与 `--index` 索引模式，契约由 `gen_response_fields.py` 从 openapi.json 生成、CI 校验一致性。
12. **（可选）issue 跟进**：实现完成后在 issue #64 评论实施结果；`amount/market_value/total_value` 与日期字段的后端命名统一治理另开 issue（维护者已定调不在本期）。

## Dependencies

- 步骤 1→2→3 串行（后端模型 → 路由声明 → 重导出 openapi.json）。
- 步骤 4 依赖 3（需含 NavHistoryRecord 的新 openapi.json）；步骤 5 依赖 4；步骤 6、7 可与 4-5 并行开发但同处 schema.py，建议同一实现者串行完成。
- 步骤 8、9 依赖 4-7 全部完成；10-11 最后。

## Risks and Mitigations

- **openapi.json 类型表达复杂（anyOf/format）导致脚本解析偏差** → 首期仅 5 个 schema，脚本对未识别类型统一降级为 `any` 并在 --check 输出警告；测试断言关键字段兜底。
- **契约随后端 schema 变更漂移** → CI --check 强制同步；生成文件头注明重新生成命令。
- **schema 输出膨胀** → 紧凑单行编码 + 首期仅 5 命令（约 +600 tokens）；`--index`/按 group 加载提供更低成本路径，净效果为省 token。
- **response_model 声明改变 nav-history 序列化行为** → 模型字段与现返回 dict 一一对应、全 Optional；以既有 #62 集成测试回归验证。

## Rejected Alternatives

- **纯手写响应字段**：维护者明确反对；SUMMARY_FIELDS 已证明手工同步易漂移，字段量放大后不可持续。
- **ir-cli 运行时拉取后端 /openapi.json**：引入运行时依赖与额外往返，违背 ir-cli 轻量定位，且每次拉取本身消耗 token/时延。
- **后端统一 amount/market_value/total_value 及日期字段命名**：破坏性 API 变更，波及前端与快照三表语义（shares/amount 互斥是 DB CHECK 约束设计），维护者已定调另开 issue 单独治理。
- **首期覆盖全部 16 个命令组**：override 标注与验证成本高，先以 5 个高频命令验证机制，脚本映射表天然支持后续增量扩展。
- **字段用对象数组表示**（issue 原文示例格式）：token 成本约为紧凑单行串的 3-4 倍，与「节省 token」目标冲突，语义信息改由 `notes` 承载。