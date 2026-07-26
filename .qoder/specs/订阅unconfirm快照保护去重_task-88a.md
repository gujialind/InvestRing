# 订阅 unconfirm 快照保护去重与冗余异常捕获清理

## 概述
两处遗留问题一并修复：A. 把重复的 SNAPSHOT_DEPENDENCY 检查内嵌进 service（级联删除路径 opt-out）；B. 删除 REST/CLI 对 `BusinessError` 子类的冗余 `try/except`（全局 handler / `cli_context` 已统一映射）。响应体与状态码逐字不变。

## 关键约束（研究结论）
- `unconfirm_single_subscription` 有 **3 个** caller：REST、CLI、快照删除级联 [`_cascade_unconfirm_subscriptions`](file:///home/collyn/projects/InvestRing/backend/app/services/snapshot_service.py#L306-L350)。级联执行时快照仍存在，因此内嵌检查必须支持 opt-out，否则级联回退会被误阻断（且被 `except Exception` 吞成静默失败）。
- 契约一致性已核验：全局 handler [`main.py#L55-L61`](file:///home/collyn/projects/InvestRing/backend/app/main.py#L55-L61) 与 [`cli_context#L50-L53`](file:///home/collyn/projects/InvestRing/backend/cli/context.py#L50-L53) 均把 `BusinessError` 映射为相同结果；`InvalidStatusError`/`NavNotAvailableError` 都是 `BusinessError` 子类、默认 422。

## Service 层
- `subscription_service.py::unconfirm_single_subscription`：
  - 新增 keyword-only 参数 `check_snapshot: bool = True`。
  - 在 `status != "confirmed"` 校验之后、改动字段之前，插入快照保护（与 [`trade_service.unconfirm_trade`](file:///home/collyn/projects/InvestRing/backend/app/services/trade_service.py#L384-L399) 同构）：当 `check_snapshot and subscription.confirm_date` 且存在 `snapshot_date >= confirm_date` 的 `PortfolioValueSnapshot` 时，抛 `BusinessError("SNAPSHOT_DEPENDENCY", <沿用现有文案>)`。`PortfolioValueSnapshot`、`BusinessError` 已在顶部导入。
  - 更新 docstring，补充 `check_snapshot` 语义与 `SNAPSHOT_DEPENDENCY` 抛出。
- `snapshot_service.py::_cascade_unconfirm_subscriptions`（L334）：调用改为 `unconfirm_single_subscription(db, sub, check_snapshot=False, auto_flush=False)`。

## REST：routers/subscriptions.py
- `unconfirm_subscription`（L155-196）：删除内联快照检查块（L165-185）与 `try/except InvalidStatusError`（L187-193），改为直接调用 `unconfirm_single_subscription(db, subscription)` 后 `db.commit()`。
- `confirm_subscription`（L95-132）：删除 `try/except InvalidStatusError/NavNotAvailableError`（L105-116），直接调用 `confirm_single_subscription(db, subscription)`。
- 清理失效导入：`PortfolioValueSnapshot`（L10）、`NavNotAvailableError`/`InvalidStatusError`（L22-23）；并顺带移除 grep 已证实的死导入 `is_trading_day/get_next_trading_day/get_latest_snapshot_date`（L12-16）与 `calculate_investor_available_shares`（L17）。保留 `status`（cancel/update/delete 仍用）。

## CLI：cli/commands/subscriptions.py
- `unconfirm_subscription`（L135-175）：删除内联快照检查（L152-167）与 `try/except InvalidStatusError`（L169-172）；函数内 import 仅留 `unconfirm_single_subscription`（去掉 `PortfolioValueSnapshot`、`InvalidStatusError`）。
- `confirm_subscription`（L85-114）：删除 `try/except`（L102-107）；函数内 import 仅留 `confirm_single_subscription`（去掉 `NavNotAvailableError`、`InvalidStatusError`）。
- SNAPSHOT_DEPENDENCY / INVALID_STATUS / NAV_NOT_AVAILABLE 均由 `cli_context` 统一映射为 `error(code, message)`。

## 测试计划
- `cd backend && python -m pytest`：重点确认快照删除级联相关用例仍能正确回退订阅（opt-out 生效），以及 `test_subscriptions.py` 全绿。
- 手动核验（curl/ir）：confirmed 订阅在 confirm_date 之后有快照 → REST 422 `SNAPSHOT_DEPENDENCY`；无快照 → 200 且配对 CASH trade 删除；非 confirmed → 422 `INVALID_STATUS`。
- `GetProblems` 覆盖三个改动文件，确认无未用导入/语法问题。

## 假设
- 按问答确认：A = 内嵌 + 级联 opt-out；B = REST(confirm+unconfirm) + CLI(confirm+unconfirm) 全量清理冗余捕获。
- 一并清理 grep 证实的既有死导入以贯彻"router 变瘦"；如需严格最小 diff，可仅移除本次改动直接产生的失效导入。
