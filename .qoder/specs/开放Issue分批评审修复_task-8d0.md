# 开放 Issue 分批评审与修复

## 概述

参照 `Docs/11-开发注意事项与AGENTS过时内容.md` 的实施依赖链，对 19 个开放 issue（#20, #23–#40）分 4 阶段修复。采用**分批推进**：每阶段改代码 + 补/更新 pytest 用例 + 运行回归，验证通过后再进入下一阶段。关键约束：**#34 必须先于 #32/#33**（否则快照重算死锁）；**#33 是架构核心**，解决 #29/#30/#31/#32 的时序根因。

执行节奏：每阶段结束运行 `cd backend && pytest`，并在 issue 上用 `gh issue close` 关闭已修复项（附修复说明与 commit 引用）。

---

## 阶段 0：P0 低风险 Bug（#20, #34）

先清除会立即产生错误数据/死锁的两个 bug，作为后续阶段前提。

- **#20 现金持仓 TypeError**：`snapshot_service.py` `_generate_portfolio_position`（约 L625）现金判空逻辑 `pos_data.get("amount", Decimal("0")) <= 0` 在 amount 为 `None` 时抛 TypeError。改为 `(pos_data.get("amount") or Decimal("0")) <= 0`。
- **#34 级联回退过度**：`_cascade_unconfirm_share_change_events`（约 L367–375）的 `or_(ex_date == snapshot_date, entitlement_date == snapshot_date)` 会误回退当日除息事件。删除 `ex_date == snapshot_date` 分支，仅保留 `entitlement_date == snapshot_date`（对齐文档"删 D 日快照只回退 entitlement_date==D 的事件"）。

测试：`tests/unit/test_snapshot_service.py` 补现金 amount 型资产快照生成用例、删快照级联回退边界用例。

---

## 阶段 1：auto_confirm 时序重构（#33 主线，含 #29/#30/#31/#32/#35）

分支：从合并 PR #41 后的 `dev` 切出 `fix/phase1-auto-confirm-timing`，PR base=dev。依据文档 §3「#33 5 处改动整体实施」+「#32/#29 一起做」。核心：auto_confirm 由确认 `confirm_date==D` 改为确认 `confirm_date==next_trading_day(D)`，配合逐日循环生成快照，使 `confirm_date==C` 的交易在快照 C 中体现（confirm(next(D)) 后推进到 next(D) 再 generate，模型自洽）。

- **#33 时序重构（5 处，必须整体实施）**：
  - 改动1｜`subscriptions.py` `create_subscription`（两分支 L180–217）创建时即设 `confirm_date = get_next_trading_day(db, apply_date, days=1)`（申赎恒 T+1，**非** product.confirm_days；对齐 Trade 的"创建时日期齐备"）。`unconfirm_single_subscription` 已清空 confirm_date，重确认时 `confirm_single_subscription` 仍回算，行为一致。
  - 改动2｜`snapshot_service.py` `_check_pending_transactions`（L1101–1105）Subscription 判据 `apply_date < target_date` → `confirm_date <= target_date`（**换字段**，效果等价：`next_trading_day(apply_date) <= D ⟺ apply_date < D`；严禁改成 `apply_date <= D`）。
  - 改动3｜`auto_confirm_after_snapshot` 查询 `== snapshot_date` → `== get_next_trading_day(db, snapshot_date, days=1)`，**仅改 Trade（L948）、跨天转移（L986）、Event（L1026）三处**；**Subscription 分支（L894）保持 `apply_date <= snapshot_date` 不变**（走 confirm_single_subscription 读 apply_date 净值，广撒网含级联回退历史）；**跨天转移守卫（L995）保持 `date.today()` 不变**（真实世界到账保护，与查询条件正交，改 snapshot_date 会因 `next_date>snapshot_date` 恒真而全跳过）。
  - 改动4｜`task_runner._generate_snapshots_for_date`（L159–179）改为逐日循环：每组合从 `max(snapshot_date) 之后首个交易日` 到 `today-1`，逐交易日 generate + auto_confirm + commit（终止 current==today）。
  - 改动5｜移除 force（见 #32）。
- **#29 Trade 确认走净值（提取公共逻辑）**：新建 `app/services/trade_service.py`，迁入 `_get_nav_for_trade_confirmation` 与 `_sync_transfer_group`（从 `trades.py`，router 改 import），新增 `_confirm_trade_logic(db, trade, product, confirm_date=None, price=None)`（净值获取→重算 shares/amount→置 confirmed→同步配对腿）。`trades.py:confirm_trade`（L412–501）与 `snapshot_service` auto_confirm 的 Trade 分支（L952–968，当前直接 `status="confirmed"`）统一改调它；场内产品不取净值（收盘价），QDII 严格 T 日。
- **#30 完全由 #33 改动3 解决**：查询条件改为 `== next_trading_day(D)`（非 #30 原提案的 `<= snapshot_date`）；跨天守卫保持 `date.today()`（理由同改动3）。无独立代码改动，随 #33 关闭。
- **#31 自然消解（前提显式）**：#33 改动3 后 auto_confirm(D) 只确认 `ex_date == next_trading_day(D)` 的事件；此时因 `ex_date > entitlement_date` 且 ex_date 为 D 之后交易日 ⟹ `entitlement_date <= D`，D 日持仓快照已落库，`entitlement_shares` 必可读，`MISSING_POSITION_SNAPSHOT` 不再误报。无独立代码改动。
- **#32 移除 force**：删除 `schemas/snapshot.py:18` `force`、`routers/snapshots.py:75` `force=request.force`、`recalculate_snapshots` 的 `force` 形参与 `if not force` 分支（改为恒校验）、`generate_daily_snapshots` 的 `skip_validation` 形参（无其他 True 调用），及两处 CLI `backend/cli/commands/snapshots.py:33,39`、`ir-cli/ir_cli/commands/snapshots.py:31,35`（含 body 的 `force`）。前提：#34（阶段0已修）已保证重算无需 force 跳过校验。
- **#35 快照连续性**：建议1｜`recalculate_snapshots` 与 `task_runner` 循环中单日失败即 `break` 停止（**非 continue**，避免后续日基于缺失数据产生错误快照）；建议2｜定时任务由改动4 的 backfill 循环补齐缺失交易日快照。

测试：`tests/unit/test_snapshot_service.py`、`tests/unit/test_run_nav_sync.py`、`tests/integration/test_subscriptions.py`、`tests/integration/test_trades.py` 补：创建即带 confirm_date、pending 拦截换字段等价性、T+1/T+2 基金在 confirm_date 当日快照体现、Event `ex_date==next_trading_day(D)` 确认、跨天守卫、force 移除后接口契约、区间 backfill 与失败即停。

---

## 阶段 2：Trade/Subscription 对称性与接口对齐（#23,#39,#24,#25,#26,#27,#38,#36）

- **#23 + #39 可用份额截止时间 + 消除副本**：`position_service.py` 三函数 `calculate_available_cash`/`calculate_available_shares`/`calculate_investor_available_shares` 增加 `as_of_date` 参数；删除 `subscriptions.py` `_calculate_investor_available_shares`、`trades.py` `_calculate_available_shares` 两处 router 副本，统一改调 service。
- **#24 QDII/非QDII 净值严格**：`trades.py` `_get_nav_for_trade_confirmation`（约 L98–102）非 QDII 分支由 `PriceRecord.date <= trade_date` 向前回溯改为 `== trade_date`（未同步则拒绝，对齐文档"禁止向前查找"）。
- **#25 unconfirm_trade 快照保护**：`trades.py` `unconfirm_trade`（约 L533–561）新增 `SNAPSHOT_DEPENDENCY` 检查，参照 `subscriptions.py` `unconfirm_subscription`（L313–332）。
- **#26 PUT/DELETE 配对同步**：`update_trade`（约 L564–589）、`delete_trade`（约 L592–613）复用 `_sync_transfer_group` 同步/级联删除配对 CASH 腿。
- **#27 CLI trades update/delete**：`ir-cli/ir_cli/commands/trades.py` 新增 update/delete 命令（`client.py` 已有 put/delete）；补 cancel/unconfirm docstring 约束说明（依赖 #26/#25 已完成）。
- **#38 事件 unconfirm 接口**：`routers/share_change_events.py` 新增 unconfirm 接口 + 快照保护，级联删除基金级子记录（`parent_event_id`）。
- **#36 逐日 commit**：`routers/snapshots.py` `delete_snapshots_bulk`（约 L270）由末尾统一 commit 改为逐日 commit。

测试：`tests/integration/test_trades.py`、`tests/integration/test_subscriptions.py`、`tests/integration/test_share_events.py` 补：as_of_date 截止计算、QDII 严格净值拒绝、unconfirm 快照保护、PUT/DELETE 配对同步、事件 unconfirm；`tests/unit/test_position_service.py` 覆盖 as_of_date 分支。

---

## 阶段 3：增强项（#28, #40, #37）

- **#28 注释修正**：`position_service.py` `compute_cash_balance`（约 L32）修正"快照生成均调用此函数"的错误注释（快照生成走 `get_cash_value`）。
- **#40 遗留字段与覆盖告警**：`models/investor_holding.py` 补 `market_value`/`total_cost`/`profit` 并在 `_generate_investor_holding` 回填；`_generate_portfolio_value_snapshot`（约 L751–758）回填 `unit_price_change_pct`；处理 `frozen_amount`（约 L673）；`share_change_events.py` `_check_platform_coverage` 未覆盖平台 warning 增强（不阻断）。需评估是否加 Alembic 迁移。
- **#37 并发安全（P3）**：关键 confirm/unconfirm 操作加 `SELECT ... FOR UPDATE` 行锁 + 跨表原子操作用 savepoint。单 admin 场景风险可控，作为最后增强项，若引入迁移/复杂度过高将回报评估。

测试：`tests/unit/test_snapshot_service.py` 补 investor_holding 派生字段与 unit_price_change_pct 断言；`test_share_events.py` 补覆盖告警。

---

## 测试计划

- 每阶段结束运行 `cd backend && pytest`（unit + integration + e2e），确保 0 失败再进入下一阶段。
- 覆盖文档第 5 节列出的回归场景：现金 amount 型快照、级联回退边界、确认次日快照、pending 拦截、QDII 严格净值、配对 CASH 同步、快照依赖保护、区间补算续跑、派生字段回填。
- 保留现有测试为基线，新增用例与被修 issue 一一对应。

## 假设与风险

- 遵守文档第 4 节"不要改的"：Trade 不做级联回退、cancel 场内/场外差异、CASH 双路径 manual 边界、Subscription 前置校验不单独改为 `apply_date <= D`。
- #40/#37 可能需要 Alembic 迁移（新增列）；执行阶段 3 前将确认迁移策略与数据库影响再回报。
- #33 为架构级改动，若阶段 1 回归暴露更深的时序耦合，将暂停并回报，不强行推进后续阶段。
- 每个 issue 修复后通过 `gh issue close` 关闭并附说明；如评审中发现文档未列的新问题，将新建 issue 或与你确认后再处理。