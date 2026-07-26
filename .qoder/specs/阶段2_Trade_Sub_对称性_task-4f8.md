# 阶段2：Trade/Subscription 对称性与接口对齐

## 准备

- 切分支：`git checkout dev && git pull origin dev && git checkout -b fix/phase2-trade-subscription-symmetry`（dev 应为 c13f7a6）
- 基线回归：`cd backend && pytest -q` 确认 181 passed 起点干净

## 改动 1：#23 + #39 可用份额 as_of_date + 消除副本

**文件**：`backend/app/services/position_service.py`、`backend/app/routers/subscriptions.py`、`backend/app/routers/trades.py`、`backend/app/routers/positions.py`

- 给三个 service 函数增加 `as_of_date: Optional[date] = None` 形参（末位）：
  - `calculate_available_cash`（L100）
  - `calculate_available_shares`（L169）
  - `calculate_investor_available_shares`（L220）
- as_of_date 语义：`None` = 当前行为（latest_date = 最新快照日，after 范围 > latest_date，pending 全计）；传入时 latest_date 改为 `<= as_of_date` 的最大快照日，after 范围改为 `(latest_date, as_of_date]`，pending 不变（pending 即未生效，as_of_date 截止不影响 pending 计提）。内部复用一个 helper `get_latest_snapshot_date_le(db, portfolio_code, as_of_date)` 避免重复。
- 删除三处 router 副本：
  - `subscriptions.py:36 _calculate_investor_available_shares` → 调用 `calculate_investor_available_shares`（L198 调用点改 import + 调用，可透传 as_of_date 给后续接口可选参数）
  - `trades.py:75 _calculate_available_shares` → 调用 `calculate_available_shares`（L249 调用点改）
  - `positions.py:28 _calculate_available_shares` → 调用 `calculate_available_shares`（L217 调用点改；spec 未点名但同属 #39 副本，一并清理避免逻辑漂移）
- `calculate_available_cash` 的调用点（trades.py:209、positions.py:196）保持不传 as_of_date（沿用当前"now"语义）。

## 改动 2：#24 非QDII净值严格T日

**文件**：`backend/app/services/trade_service.py:64-75`

- 非QDII 分支 `PriceRecord.date <= trade_date` → `PriceRecord.date == trade_date`，`order_by` 可保留但单条即命中。
- 未命中返回 None → `confirm_single_trade` 已在 L150 抛 `MISSING_NAV`，行为对齐文档"禁止向前查找"。
- 更新 docstring：非QDII 也必须 T 日净值，缺失即拒绝。

## 改动 3：#25 unconfirm_trade 快照保护

**文件**：`backend/app/routers/trades.py:unconfirm_trade`（L402-430）

- 在状态校验后、置 pending 前，参照 `subscriptions.py:unconfirm_subscription`（L315-334）加 `SNAPSHOT_DEPENDENCY` 检查：
  - 查 `PortfolioValueSnapshot` where `portfolio_code == trade.portfolio_code and snapshot_date >= trade.confirm_date`，count>0 则抛 422 `SNAPSHOT_DEPENDENCY`。
- 现有的 `sync_transfer_group(db, trade, "pending")` 保留（配对 CASH 腿同步回 pending + 重算 confirm_date）。

## 改动 4：#26 PUT/DELETE 配对同步

**文件**：`backend/app/routers/trades.py:update_trade`（L433）、`delete_trade`（L461）

- `update_trade`：更新字段后、commit 前，若 `db_trade.transfer_group` 且改动涉及 `status`/`confirm_date`/`trade_date`，调用 `sync_transfer_group(db, db_trade, db_trade.status, db_trade.confirm_date)` 让配对 CASH 腿对齐。注意只对 pending 态修改（已有 confirmed 拒绝逻辑保护），status 不会变，主要同步 confirm_date/trade_date 改动。
- `delete_trade`：删除主腿前，若 `transfer_group` 存在，先 `db.query(Trade).filter(Trade.transfer_group == trade.transfer_group, Trade.id != trade.id).delete(synchronize_session=False)` 级联删除配对 CASH 腿，再 `db.delete(trade)`。已 confirmed 拒绝删除的逻辑保留。

## 改动 5：#27 CLI trades update/delete

**文件**：`ir-cli/ir_cli/commands/trades.py`

- 新增 `update` 命令：`ir trades update {id} --field value...`，构造 body 调 `client.put(f"/api/trades/{id}", json_data=body)`。支持 `--shares --amount --price --fee --actual-amount --notes --confirm-date` 等可选字段。
- 新增 `delete` 命令：`ir trades delete {id}`，调 `client.delete(f"/api/trades/{id}")`。
- 给 `cancel`/`unconfirm` 补 docstring 约束说明：cancel 仅场外 pending 可用；unconfirm 受 SNAPSHOT_DEPENDENCY 保护（依赖 #25 已完成）。
- client.py 的 `put`（L123）/`delete`（L133）已存在，无需改。

## 改动 6：#38 事件 unconfirm 接口

**文件**：`backend/app/routers/share_change_events.py`

- 新增 `@router.post("/{id}/unconfirm")`：
  - 仅 confirmed 状态可 unconfirm，否则 422 `INVALID_STATUS`
  - 快照保护：查 `PortfolioValueSnapshot` where `snapshot_date >= event.ex_date`，count>0 抛 422 `SNAPSHOT_DEPENDENCY`（参照 subscriptions 的 confirm_date→ex_date，事件按 ex_date 生效）
  - 基金级父记录（`platform_code is None`）：先级联删除所有 `parent_event_id == event.id` 的子记录（`db.query.delete`），再置父记录 pending 并清空 `confirmed_at`、`shares_change`/`shares_after`/`cash_change`/`entitlement_shares`/`shares_before`（恢复到确认前状态，便于重确认重算）
  - 平台级事件（`platform_code` 非空）：直接置 pending，清空计算字段
  - 子记录（`parent_event_id` 非空）单独 unconfirm 应拒绝：422 `CANNOT_UNCONFIRM_CHILD`（必须 unconfirm 父记录）

## 改动 7：#36 delete_snapshots_bulk 逐日 commit

**文件**：`backend/app/routers/snapshots.py`（L249-269）

- 循环内每次 `_delete_existing_snapshots` 成功后立即 `db.commit()`，失败 `db.rollback()` + 抛异常（已有）。
- 移除末尾的统一 `db.commit()`（L269）。
- 汇总 `results`/`total_cascaded_*` 计数逻辑保留。

## 测试

**文件**：`backend/tests/unit/test_position_service.py`、`backend/tests/integration/test_trades.py`、`backend/tests/integration/test_subscriptions.py`、`backend/tests/integration/test_share_events.py`

- `test_position_service.py`：as_of_date 分支——传入历史日时 latest_date 取 <= as_of_date、after 范围 (latest, as_of]、pending 不变。
- `test_trades.py`：非QDII T 日净值缺失拒绝（#24）；unconfirm_trade 有快照时 SNAPSHOT_DEPENDENCY（#25）；update 改 confirm_date 配对 CASH 腿同步（#26）；delete 级联删配对 CASH 腿（#26）。
- `test_subscriptions.py`：调用点改 service 后行为不变回归。
- `test_share_events.py`：事件 unconfirm 成功、快照保护、基金级父 unconfirm 级联删子记录、子记录单独 unconfirm 被拒（#38）。
- 保留现有测试为基线。

## 回归与提交

- `cd backend && pytest` 全量 0 失败（目标在 181 基础上增加新用例）。
- commit：`fix(trade): 阶段2 Trade/Subscription 对称性与接口对齐 (#23 #24 #25 #26 #27 #36 #38 #39)`
- PR base=dev，body 逐 issue 对应 + 回归结果，Closes #23 #24 #25 #26 #27 #36 #38 #39。
- 合并后 `gh issue close` 各 issue 附修复说明与 commit 引用。

## 假设与风险

- as_of_date 语义采用"latest snapshot <= as_of_date"，符合"截止某日可用"的直觉；若评审希望沿用"now + 之后 pending"的另一种语义将在评审反馈后调整。
- positions.py 的 `_calculate_available_shares` 副本 spec 未点名，但与 #39 同质，一并清理以免逻辑漂移；如评审认为超范围可回退此子项。
- #38 事件 unconfirm 清空计算字段后，重确认会重新读 entitlement_date 快照计算，行为与首次确认一致；不会产生孤儿子记录（父级联删）。
- 不触碰 #28/#40/#37（属阶段3增强项，可能需 Alembic 迁移，本阶段不做）。