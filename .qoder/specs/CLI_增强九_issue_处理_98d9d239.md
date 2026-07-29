# InvestRing CLI 增强：9 个 issue 评估与实施计划

## Summary

9 个 issue 均为 CLI 易用性/安全性增强。评估结论：

| Issue | 结论 | 理由 |
|---|---|---|
| #85 task logs 500 + describe | **采纳**（--with-effect 除外） | 500 是真实缺陷：`routers/tasks.py:131` 声明 `response_model=List[TaskExecutionLogResponse]` 但返回分页 dict，Pydantic 校验失败。describe 零迁移成本（`ScheduledTask.description` 字段已存在） |
| #74 trading-day 查询 | **采纳** | `trading_utils.py:16-58` 已有 `is_trading_day`/`get_next_trading_day`/`get_prev_trading_day`，纯暴露端点，且是 #84 的提示基础 |
| #75 delete-bulk --dry-run | **采纳** | 破坏性操作（逐日 commit 不可回滚）前的安全复核，纯查询实现零副作用 |
| #84 catch-up / generate-next | **采纳（服务端实现）** | `task_runner._generate_snapshots_for_date`（L166-202）已有逐日 checkpoint 成熟模式，`delete_snapshots_bulk` 路由有逐日 commit 先例，直接复用 |
| #86 错误就近提示 | **采纳** | `ir_cli/hints.py` 已有 31 条静态映射 + `output.py:90-92` 自动附加机制，扩展成本低 |
| #83 市场解析 | **采纳（service 层单一实现）** | 唯一市场自动补 + LOF 歧义报错，符合「业务逻辑单一实现于 service」约定，REST 与两套 CLI 共享 |
| #81 available-cash 参数风格 | **采纳（向后兼容）** | 位置参数保留为 deprecated fallback，新增 `--portfolio-code` option |
| #80 --help 完整示例 | **部分采纳** | 仅高频 create 类命令在 docstring 末尾附示例（click `\b` 块保留换行），不做自定义 help formatter |
| #76 末尾摘要行 | **不采纳** | ir-cli 输出本就是单行结构化 JSON（`output.py` 统一协议），已满足 grep/自动化解析；追加摘要行会破坏 `jq` 管道，收益为负 |

依赖顺序：P0 三项相互独立可并行；P1 的 #86 hints 中 MARKET_AMBIGUOUS 条目与 P2 的 #83 联动；#84 报错提示引用 #74 的命令。

---

## P0：缺陷修复与基础能力（相互独立，可并行）

### 1. #85a — 修复 task logs 500（后端必改）

- `backend/app/schemas/task.py`：新增 `PaginatedTaskLogResponse`（`items: List[TaskExecutionLogResponse]`、`total: int`、`page: int`、`page_size: int`）。
- `backend/app/routers/tasks.py:131`：`response_model` 改为 `PaginatedTaskLogResponse`，函数体不变（已返回该结构）。
- 回归确认：`frontend/src/lib/api/log.ts` 按分页 items 解析，契约不变，无需改前端。

### 2. #74 — 交易日查询三端点 + CLI 命令

- `backend/app/routers/trading_calendar.py` 新增 3 个 GET（复用 `app/services/trading_utils.py` 现有函数，权限 `get_current_user`）：
  - `GET /next?from_date=YYYY-MM-DD&days=1` → `{"from_date", "trading_day"}`（`get_next_trading_day`）
  - `GET /prev?from_date=YYYY-MM-DD&days=1` → `{"from_date", "trading_day"}`（`get_prev_trading_day`）
  - `GET /is-open?date=YYYY-MM-DD` → `{"date", "is_open"}`（`is_trading_day`）
  - 日历数据缺失（函数返回 None）时抛 `BusinessError("CALENDAR_NOT_SYNCED", ...)`，提示 `ir system calendar-sync`。
- `ir-cli/ir_cli/commands/system.py`：新增嵌套 typer 子应用 `trading-day`，含 `next`/`prev`/`is-open` 三命令，HTTP 调上述端点。
- `backend/cli/commands/system.py`：同名命令，直接调 `trading_utils` 函数。

### 3. #75 — snapshot delete-bulk --dry-run

- `backend/app/routers/snapshots.py::delete_snapshots_bulk`（L236 起）：新增 `dry_run: bool = Query(False)`；查询 `snapshot_dates` 后若 `dry_run=true`，直接返回 200 预览 `{"dry_run": true, "portfolio_code", "from_date", "count", "snapshot_dates": [...]}`，不校验 confirm、不删除。
- `ir-cli/ir_cli/commands/snapshots.py::delete_bulk`（L76-87）：新增 `--dry-run` flag；启用时跳过 `--yes` 校验，带 `dry_run=true` 调用，成功输出附 hint「确认后执行 `--yes`」。
- `backend/cli/commands/snapshots.py`：同步加 `--dry-run`（本地查询 `PortfolioValueSnapshot` 日期列表后直接输出）。
- `CONFIRM_REQUIRED` 的报错消息中追加「可先加 --dry-run 预览」。

---

## P1：快照追平与错误提示

### 4. #84 — snapshot catch-up / generate-next（服务端逐日 checkpoint）

遵循 `delete_snapshots_bulk` 路由逐日 commit 先例与 `task_runner._generate_snapshots_for_date` 循环模式：

- `backend/app/schemas/snapshot.py`：新增 `SnapshotCatchUpRequest {portfolio_code, to_date}`、`SnapshotCatchUpResult`、`SnapshotGenerateNextRequest {portfolio_code}`。
- `backend/app/routers/snapshots.py` 新增：
  - `POST /catch-up`：取 `get_latest_snapshot_date`；无快照 → `BusinessError("NO_SNAPSHOT_BASELINE")` 提示先 `snapshot generate` 生成首日；`latest >= to_date` → 幂等返回 `generated_count=0`；否则从 `get_next_trading_day(latest)` 起逐交易日调 `generate_daily_snapshots` + `auto_confirm_after_snapshot`，**每日 `db.commit()`**，单日失败 `rollback` 并停止，返回 `{"generated_dates": [...], "generated_count", "failed_date"?, "error"?}`。逐日推进天然满足连续性校验，不改 `generate_daily_snapshots`。
  - `POST /generate-next`：`next = get_next_trading_day(latest, 1)`，生成一日 + auto_confirm + commit，返回生成结果与日期。
- `ir-cli/ir_cli/commands/snapshots.py`：新增 `catch-up --portfolio-code --to-date`、`generate-next --portfolio-code`。
- `backend/cli/commands/snapshots.py`：同名命令，CLI 自持 session 逐日 commit（复用同一循环逻辑，抽为 `snapshot_service.catch_up_snapshots(db, portfolio_code, to_date, commit_per_day=True)` 供 router 与 backend/cli 共用，注释标注编排层 checkpoint 例外，参照 AGENTS.md §4.1）。
- `hints.py` 的 `SNAPSHOT_NOT_CONTINUOUS`、`NAV_NOT_AVAILABLE` 条目更新为推荐 `ir snapshot catch-up`。

### 5. #86 — 错误就近提示（hints 动态化）

- `ir-cli/ir_cli/hints.py`：
  - 静态表补充：`NOT_FOUND`（附 `--product-code 022959.OF --market CN_OTC` 格式示例与 `ir product list` 指引）、`PRODUCT_NOT_FOUND`、`MARKET_AMBIGUOUS`、`CONFIRM_REQUIRED`、`NO_SNAPSHOT_BASELINE`、`CALENDAR_NOT_SYNCED`。
  - 新增 `get_hint(code: str, details: dict | None) -> str | None`：优先按 code+details 动态生成（如 `MARKET_AMBIGUOUS` 插值 `details.available_markets`、`INSUFFICIENT_SHARES` 插值 `details.available_shares`），fallback 到静态 `ERROR_HINTS`。
- `ir-cli/ir_cli/output.py::error`（L90-92）：`ERROR_HINTS.get(code)` 改为 `get_hint(code, details)`。
- 后端在产品查找失败处（`trade_service`/`subscription_service`/`product_service`）确保 `details` 携带 `product_code` 与可用市场（与 #83 共享 `resolve_product_market` 的产出）。

### 6. #85b — task describe（--with-effect 不采纳）

- `backend/app/init_tasks.py`：为 3 个任务补充/更新 `description` 文案，包含数据影响说明（如 nav_sync：「每交易日 07:00 同步净值并自动回补当日快照，禁用将导致快照中断」）。字段已存在（`models/scheduled_task.py:10`），无迁移。
- `backend/app/routers/tasks.py`：新增 `GET /{code}`（describe）：返回任务全字段 + 最近一次 `TaskExecutionLog`；不存在返回 404。
- 两套 CLI `tasks.py` 命令组新增 `describe <code>`。
- `--with-effect` 不采纳：`task list` 已含 `last_run_status`/`last_run_at`，describe 覆盖详情需求，避免 N+1 查询。

---

## P2：易用性打磨

### 7. #83 — 市场解析（service 层单一实现）

- `backend/app/services/product_service.py`：新增 `resolve_product_market(db, product_code, market=None) -> tuple[str, str]`：
  - market 已给 → 原样返回；
  - 查 `Product.market WHERE code=product_code`：0 个 → `NotFoundError("PRODUCT_NOT_FOUND", details={"product_code": code})`；1 个 → 自动补全；多个（LOF）→ `BusinessError("MARKET_AMBIGUOUS", "产品存在多个市场，请指定 market", details={"available_markets": [...]})`。
- 接入点：`trade_service.create_trade`、`subscription_service.create_subscription`、`products` router 的 `product get` 路径，在产品查找前调用。
- Schema：`TradeCreate`/`SubscriptionCreate` 的 `market` 改 `Optional[str]`（服务端解析后落库仍为完整值）。
- `product list` 响应确认含 `market` 字段（`ProductResponse` 已含则不动，缺则补）。
- 两套 CLI 对应 create/get 命令的 `--market` 改为可选。

### 8. #81 — available-cash 参数风格统一（向后兼容）

- `ir-cli/ir_cli/commands/positions.py` 与 `backend/cli/commands/positions.py` 的 `available-cash`（一并处理 `available-shares`）：
  - 位置参数改 `Optional`（help 标注 deprecated），新增 `--portfolio-code` option；option 优先，两者皆缺报 `VALIDATION_ERROR`；使用位置参数时向 stderr 打 deprecation 警告（不污染 stdout JSON）。
- `hints.py` 中 `INSUFFICIENT_CASH`/`INSUFFICIENT_SHARES` 的示例命令改为 `--portfolio-code` 风格。

### 9. #80 — help 示例（docstring 方式，部分采纳）

- 仅对高频 create 类命令追加示例：两套 CLI 的 `sub create`、`trade create`、`cash-transfer create`、`snapshot generate`、`share-event create`。
- 在命令 docstring 末尾用 click 的 `\b` 转义块附一条含全部必填参数的可复制命令（`\b` 防止 click 重排换行）。不引入自定义 help formatter。

### 不采纳 — #76 末尾摘要行

在 issue 回复中说明：ir-cli 输出协议已是单行结构化 JSON（`{"ok", "data", "meta", "hints"}`），天然支持 grep/jq/自动化判断；追加非 JSON 摘要行将破坏管道解析。建议关闭。

---

## 横切事项（每个后端变更批次后执行）

1. 重新导出 OpenAPI：运行 `backend/export_openapi.py` 更新 `backend/openapi.json`。
2. 重新生成契约：`ir-cli/scripts/gen_response_fields.py` 更新 `response_fields.py`（CI `--check` 强制，遗漏即挂）。
3. `ir-cli/ir_cli/schema.py` 的 WORKFLOWS 补充新命令配方（catch-up、trading-day、dry-run、describe）。
4. 文档：`backend/CLI_MANUAL.md` 增补新命令；`AGENTS.md` §4.2 路由表更新端点数与新端点（snapshots +2、trading_calendar +3、tasks +1）。
5. 收尾：用 `gh issue comment` 将各 issue 的采纳结论与实现说明回帖（#76 附不采纳理由）。

## Test Plan

- 后端 pytest（`backend/tests/integration/`）：
  - task logs 端点返回 200 且分页结构正确（回归 500）；task describe 404/200。
  - trading-day next/prev/is-open 正常与日历缺失分支。
  - catch-up：多日追平、幂等（latest>=to_date）、中途失败停止且已成功日保留、无基准报错。
  - generate-next 单日生成；delete-bulk `dry_run=true` 零副作用（删除前后计数一致）。
  - `resolve_product_market` 0/1/N 市场三分支；trade/sub 创建省略 market 的自动补全与 LOF 歧义报错。
- ir-cli pytest（`ir-cli/tests/`）：`get_hint` 动态插值与 fallback；available-cash 位置参数/option 双通道。
- 契约与门禁：`gen_response_fields.py --check` 通过；后端全量测试无回归。
- 前端不改代码，仅浏览器验证 `/settings/tasks` 任务日志页正常加载（500 修复的用户可见验证）。

## Assumptions

- 9 个 issue 中的 CLI 报错样例来自 ir-cli，但按项目「两套 CLI 命令组一致」约定，命令层改动两套同步。
- `MARKET_AMBIGUOUS` 为新错误码，纳入错误码契约（AGENTS.md 附录）。
- #81 的位置参数 deprecated 过渡期至少保留 2 个版本，本次不移除。

## Rejected Alternatives

- **#84 客户端循环实现**（ir-cli 侧 loop 逐日调 generate）：N 次 HTTP + N 次独立事务、错误处理割裂，且服务端已有 `task_runner` 逐日 checkpoint 成熟模式 → 选服务端实现。
- **#85 移除 response_model 直接返回 dict**：丢失 OpenAPI 契约，破坏 `gen_response_fields.py` 生成链路 → 选新增 Paginated schema。
- **#83 纯 CLI 侧市场解析**：违反「业务逻辑单一实现于 service」分层约定，两套 CLI 必然漂移，REST 用户也无法受益 → service 层实现。
- **#76 opt-in `--summary` flag**：现有 JSON 协议已满足机器可读需求，新增输出模式徒增协议复杂度与文档负担 → 不采纳。
- **#80 自定义 help formatter / rich 格式化**：维护成本高于收益 → docstring `\b` 块方案。
- **#85 `task list --with-effect`**：需 N+1 查询或新聚合端点，而 list 已含 last_run 字段 → 由 describe 覆盖。