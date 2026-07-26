# Phase2 遗留修复 (#46 #47 #48 #49)

## 准备

- 切分支：`git checkout dev && git pull origin dev && git checkout -b fix/phase2-leftover-46-47-48-49`（dev 应为 84a439c）
- 基线回归：`cd backend && pytest -q` 确认起点干净

---

## 改动 1：#46 update_trade 配对 CASH 腿金额同步

**文件**：`backend/app/routers/trades.py`（update_trade, L427-441）、`backend/app/schemas/trade.py`

**问题**：PUT 修改基金腿 `actual_amount`/`fee` 后，配对 CASH 腿金额不变 → `compute_cash_balance` 计算错误。

**修改**：

1. `TradeUpdate` schema 补充 `trade_date: Optional[date] = None`（CLI 已支持 `--trade-date` 但 schema 缺失，当前被静默忽略）。

2. `update_trade` 函数中，在现有 `sync_transfer_group` 逻辑之后，增加金额同步：

```python
# 金额字段变动时，同步配对 CASH 腿金额
amount_fields = {"actual_amount", "amount", "fee", "shares", "price"}
if db_trade.transfer_group and db_trade.product_code != "CASH":
    if update_data.keys() & amount_fields:
        paired = db.query(Trade).filter(
            Trade.transfer_group == db_trade.transfer_group,
            Trade.id != db_trade.id,
            Trade.product_code == "CASH",
        ).first()
        if paired:
            # CASH 腿金额 = 基金腿 actual_amount（买入=支出，卖出=收入）
            new_amount = db_trade.actual_amount or db_trade.amount
            paired.amount = new_amount
            paired.actual_amount = new_amount
```

---

## 改动 2：#47 as_of_date 调用点接入

**文件**：`backend/app/routers/subscriptions.py`（L140-142）、`backend/app/routers/trades.py`（L161, L201-203）

**问题**：三个 service 函数已有 `as_of_date` 参数，但调用点均未传入，补录历史交易仍误拒。

**修改**：

1. `subscriptions.py` 赎回校验（L140）：
```python
available = calculate_investor_available_shares(
    db, subscription.portfolio_code, subscription.investor_code,
    as_of_date=subscription.apply_date,
)
```

2. `trades.py` 卖出校验（L201）：
```python
available_shares = calculate_available_shares(
    db, trade.portfolio_code, trade.product_code, trade.market,
    as_of_date=trade.trade_date,
)
```

3. `trades.py` 买入现金校验（L161）：
```python
available_cash = calculate_available_cash(
    db, trade.portfolio_code, trade.platform_code,
    as_of_date=trade.trade_date,
)
```

**语义说明**：当天新增交易传入当天日期等价于不传（无差异）；补录历史交易时截止日排除后续 confirmed 交易，修复误拒。

---

## 改动 3：#48 快照 CASH 持仓改用 get_cash_value()

**文件**：`backend/app/services/snapshot_service.py`（`_generate_portfolio_position`, L443-690）

**问题**：快照生成走增量累加（前日基准 + 窗口 trades + events + manual），实时计算走 `compute_cash_balance`，双路径维护负担大。

**修改思路**：

1. 在函数顶部 import `get_cash_value`：
```python
from app.services.position_service import get_cash_value
```

2. 修改 buy_trades / sell_trades 查询，排除 CASH 产品（CASH 不再增量累加）：
```python
buy_trades = db.query(Trade).filter(
    ..., Trade.product_code != "CASH",
).all()
```
同理 sell_trades。删除两个循环中的 `if trade.product_code == "CASH": ... continue` 分支。

3. 事件循环中，删除 `cash_dividend`/`forced_adjustment` 的 CASH 累加块（L579-585），改为仅 `continue`（现金影响由 `get_cash_value` 统一处理）：
```python
if event.event_type in ("cash_dividend", "forced_adjustment"):
    continue  # 现金影响由 get_cash_value 统一计算
```

4. 删除 manual_market_value 覆盖块（L609-620），已由 `get_cash_value` 内部处理。

5. 在事件循环之后、构建结果之前，插入 CASH 统一计算：
```python
# CASH 持仓：统一调用 get_cash_value（消除增量累加双路径）
cash_platforms = set()
# 从前日快照收集
for key, pos_data in list(positions.items()):
    if pos_data.get("asset_type") == "cash":
        cash_platforms.add(key[2])
        del positions[key]
# 从窗口内 CASH trades 收集新平台
window_cash_trades = db.query(Trade.platform_code).filter(
    Trade.portfolio_code == portfolio_code,
    Trade.product_code == "CASH",
    Trade.status == "confirmed",
    Trade.confirm_date >= start_apply_date,
    Trade.confirm_date <= target_date,
).distinct().all()
for (plat,) in window_cash_trades:
    if plat:
        cash_platforms.add(plat)
# 从窗口内事件收集新平台
window_cash_events = db.query(ShareChangeEvent.platform_code).filter(
    ShareChangeEvent.portfolio_code == portfolio_code,
    ShareChangeEvent.status == "confirmed",
    ShareChangeEvent.ex_date >= start_apply_date,
    ShareChangeEvent.ex_date <= target_date,
    ShareChangeEvent.platform_code.isnot(None),
    ShareChangeEvent.cash_change.isnot(None),
    ShareChangeEvent.cash_change != 0,
).distinct().all()
for (plat,) in window_cash_events:
    cash_platforms.add(plat)

for plat in cash_platforms:
    cash_val = get_cash_value(db, portfolio_code, plat, target_date)
    positions[("CASH", "", plat)] = {
        "shares": None,
        "amount": cash_val,
        "cost_price": None,
        "asset_type": "cash",
    }
```

---

## 改动 4：#49 cancel 错误信息补充修正路径

**文件**：`backend/app/routers/trades.py`（cancel_trade, L345）

**修改**：
```python
"message": "场内交易不可取消，请使用 PUT 修改字段或 DELETE 删除后重新创建"
```

---

## 测试

**文件**：`backend/tests/integration/test_trades.py`、`backend/tests/unit/test_snapshot_service.py`

- **#46**：创建基金买入（含配对 CASH 腿）→ PUT 改 `actual_amount` → 断言配对 CASH 腿 `amount` 同步更新。
- **#47**：构造"快照后有后续 confirmed 赎回"场景 → 补录历史日期赎回 → 断言不再误拒 INSUFFICIENT_SHARES。
- **#48**：现有 `test_snapshot_service.py` 快照生成测试应全部通过（行为等价验证）；补充一个 manual_market_value 覆盖场景确认 `get_cash_value` 路径正确。
- **#49**：cancel 场内交易 → 断言 message 包含 "PUT" 和 "DELETE" 关键词。

---

## 回归与提交

- `cd backend && pytest` 全量 0 失败。
- commit：`fix(trade): phase2 遗留修复 (#46 #47 #48 #49)`
- PR base=dev，body 逐 issue 对应 + 回归结果，Closes #46 #47 #48 #49。

---

## 风险与注意

- #48 性能：`get_cash_value` 对每个平台全量扫描 confirmed CASH trades + events。对于正常规模（数百笔交易）无问题；若组合有上万笔 CASH trade 可能需后续加索引优化。
- #47 语义：`as_of_date` 传入当天日期时行为与不传完全一致（after 范围上界 = today 等价于无上界），不影响正常新增流程。
- #46 金额同步仅针对 pending 态（confirmed 已被拒绝修改保护），不会破坏已确认数据。
