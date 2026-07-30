# 份额量化 ROUND_DOWN 改 ROUND_HALF_UP（issue #87）

## 摘要
- 唯一量化入口 `backend/app/utils/quantize.py::quantize_shares` 改为 ROUND_HALF_UP，所有份额产生点（申购确认、调仓买卖、赎回、份额事件）自动统一生效，无并行实现。
- 已确认决策：全部路径统一改（owner 评论已否决申购截断例外）；负数接受远离零进位（-1.235 → -1.24）；历史数据通过全量重算快照对齐新口径。

## 代码改动

### app/utils/quantize.py
- `from decimal import Decimal, ROUND_DOWN` → `ROUND_HALF_UP`；`rounding=ROUND_DOWN` → `rounding=ROUND_HALF_UP`。
- 更新模块 docstring（第 4-5 行：删除「行业申购确认惯例 = ROUND_DOWN」表述，改为「场外基金行业惯例四舍五入，误差计入基金财产」口径）与函数 docstring（负数语义改为「远离零进位，如 -1.235 → -1.24」）。

### 调用方注释同步（逻辑不变，仅注释文案「第 3 位舍去」→「四舍五入」）
- `subscription_service.py` L120、L295
- `trade_service.py` L486
- `share_change_event_service.py` L35（模块 docstring）

## 测试改动

### tests/unit/test_quantize.py
- 重写 ROUND_DOWN 断言为 HALF_UP：`6837.295 → 6837.30`、`0.019 → 0.02` 等。
- 新增覆盖（对应 issue 验收项）：
  - issue 实例：`quantize_shares(Decimal("3000") / Decimal("0.9757")) == Decimal("3074.72")`
  - 边界 `x.xx5` 进位（如 `0.005 → 0.01`）与 `< 5` 舍去
  - 负数：`-1.235 → -1.24`、`-1.234 → -1.23`
  - None 透传、float/int/str 输入、exponent=-2（保留现有用例，按新模式调整期望值）

### tests/integration/test_shares_precision.py
- 现有用例 `10000 / 1.4623 = 6838.5426...` 在两种模式下结果相同（6838.54），无法区分模式。改用可区分的数值（issue 场景 `3000 @ 0.9757 → 3074.72`），并更新类/注释文案，覆盖申购确认与场外买入确认两条路径。

## 文档与迁移注释

- `AGENTS.md` §2.4：「份额统一 2 位小数（ROUND_DOWN，第 3 位直接舍去）」→「份额统一 2 位小数（ROUND_HALF_UP 四舍五入）」；删除 ROUND_DOWN=行业惯例的表述。
- `backend/CLI_MANUAL.md` L102、L401 同步改为四舍五入口径。
- `alembic/versions/0004_shares_precision_2_digits.py`：仅改注释（头部 docstring L20-23 与内联 L62-64），说明该迁移为当时一次性向零截断（与彼时 ROUND_DOWN 一致），运行时口径已于 issue #87 改为 ROUND_HALF_UP，且历史数据已通过快照全量重算对齐；迁移 SQL 本体不动。

## 历史数据全量重算（用户已选定）

代码改完并测试通过后，在目标环境执行：
1. 用后端管理 CLI 对每个有快照的组合执行 `ir snapshot recalculate`，区间为该组合最早快照日至最新快照日（`recalculate_snapshots` 为单一事务：先净值完整性预校验，逐日删旧→级联回退→重建→auto_confirm，auto_confirm 重确认时按新舍入模式重算份额）。
2. 检查返回 errors 为空；若净值完整性预校验失败则先补齐 NAV 再重跑（不会破坏现有数据）。
3. 风险说明：HALF_UP 相比 DOWN 只会持平或增加买入/申购份额，可用份额单调不减，历史卖出/赎回（用户输入份额，已是 2 位）不会因重算变为超卖。

## 验证

1. `pytest tests/unit/test_quantize.py tests/integration/test_shares_precision.py`，随后跑全量 `pytest`（确认无其他用例隐式依赖 ROUND_DOWN）。
2. 重算后验证 issue 验收场景：PORT001 中 022959.OF 可用份额 = 6837.30，全仓卖出 6837.3 份可正常录入。

## 收尾（GitHub）

- 提交改动（commit message 引用 `#87`），在 issue #87 下评论实施结果（代码改动点、重算结果、验收核对），确认后关闭 issue。提交/推送前先向用户确认。
