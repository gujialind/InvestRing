# 修复 Issue #15 和 #17

## Summary

- **Issue #15**: ir-cli HTTP 客户端 timeout 硬编码 60s，大范围快照重算超时。修改为默认 300s 并支持环境变量覆盖。
- **Issue #17**: 快照生成的 CASH 持仓使用全量汇总法（`compute_cash_balance`），导致 `manual_market_value` 覆盖无法传递到后续日期。改为与净值型产品一致的增量法。

---

## Issue #15: CLI HTTP 超时配置化

**文件**: `ir-cli/ir_cli/client.py`

**改动**:

1. 在 `APIClient.__init__` 中，将 `timeout=60.0` 改为从环境变量 `IR_HTTP_TIMEOUT` 读取，默认 300 秒：

```python
import os
# ...
timeout = float(os.environ.get("IR_HTTP_TIMEOUT", "300"))
self._client = httpx.Client(
    base_url=self.base_url,
    headers=headers,
    timeout=timeout,
)
```

**影响范围**: 仅 CLI 客户端初始化逻辑，不影响后端或前端。

---

## Issue #17: CASH 持仓改用增量法

**文件**: `backend/app/services/snapshot_service.py`

**核心思路**: 将 `_generate_portfolio_position` 中 CASH 的处理方式从"全量汇总"改为"前一日快照 + 窗口增量 + manual override"，与基金持仓的增量模式一致。

### 改动点（5 处 + 1 处导入清理）

| # | 位置 (当前行号) | 当前行为 | 改为 |
|---|---|---|---|
| 1 | L468-470 (prev_snapshot 循环) | `if pos.product_code == "CASH": continue` | 加载 CASH 的 `amount` 到 positions 字典，key=`("CASH", "", platform_code)` |
| 2 | L503-505 (buy_trades 循环) | `if trade.product_code == "CASH": continue` | CASH buy → `positions[cash_key]["amount"] += trade.amount` |
| 3 | L541-543 (sell_trades 循环) | `if trade.product_code == "CASH": continue` | CASH sell → `positions[cash_key]["amount"] -= trade.amount` |
| 4 | L558-560 (events 循环) | `if event.event_type in ("cash_dividend", "forced_adjustment"): continue` | 累加 `event.cash_change` 到对应平台的 CASH position |
| 5 | L584-612 (CASH 块) | 遍历所有平台调 `get_cash_value` 从零计算 | 改为仅查询 `manual_market_value` 表做日期精确覆盖（绝对替换） |
| 6 | L22 (import) | `from app.services.position_service import get_cash_value` | 改为 `from app.models import ManualMarketValue` |

### 详细伪代码

```python
# --- 改动 1: prev_snapshot 循环，不再跳过 CASH ---
for pos in prev_positions:
    if pos.product_code == "CASH":
        key = ("CASH", "", pos.platform_code)
        positions[key] = {
            "shares": None,
            "amount": Decimal(str(pos.amount or 0)),
            "cost_price": None,
            "asset_type": "cash",
        }
        continue
    # ... 原有基金持仓逻辑不变

# --- 改动 2: buy_trades 循环，CASH buy 增加 amount ---
for trade in buy_trades:
    if trade.product_code == "CASH":
        cash_key = ("CASH", "", trade.platform_code)
        if cash_key not in positions:
            positions[cash_key] = {"shares": None, "amount": Decimal("0"), "cost_price": None, "asset_type": "cash"}
        positions[cash_key]["amount"] += Decimal(str(trade.amount or 0))
        continue
    # ... 原有基金逻辑不变

# --- 改动 3: sell_trades 循环，CASH sell 减少 amount ---
for trade in sell_trades:
    if trade.product_code == "CASH":
        cash_key = ("CASH", "", trade.platform_code)
        if cash_key not in positions:
            positions[cash_key] = {"shares": None, "amount": Decimal("0"), "cost_price": None, "asset_type": "cash"}
        positions[cash_key]["amount"] -= Decimal(str(trade.amount or 0))
        continue
    # ... 原有基金逻辑不变

# --- 改动 4: events 循环，现金事件累加 cash_change ---
for event in confirmed_events:
    if event.event_type in ("cash_dividend", "forced_adjustment"):
        if event.cash_change:
            cash_key = ("CASH", "", event.platform_code)
            if cash_key not in positions:
                positions[cash_key] = {"shares": None, "amount": Decimal("0"), "cost_price": None, "asset_type": "cash"}
            positions[cash_key]["amount"] += Decimal(str(event.cash_change))
        continue
    # ... 原有份额变动逻辑不变

# --- 改动 5: 替换原 CASH 块，仅做 manual_market_value 覆盖 ---
# 删除原来的平台收集 + get_cash_value 循环（L584-L612）
# 替换为：
for key, pos_data in positions.items():
    if pos_data.get("asset_type") == "cash":
        _, _, plat_code = key
        manual = db.query(ManualMarketValue).filter(
            ManualMarketValue.portfolio_code == portfolio_code,
            ManualMarketValue.platform_code == plat_code,
            ManualMarketValue.product_code == "CASH",
            ManualMarketValue.date == target_date,
        ).first()
        if manual:
            pos_data["amount"] = Decimal(str(manual.market_value))
```

### 边界情况处理

- **首次快照（无前一日快照）**: 无 prev_snapshot 时 positions 为空，CASH 仅通过窗口内 buy/sell trades 和 events 累加——行为等价于旧版 `compute_cash_balance` 的全量计算（因为窗口 = 全部历史），结果一致。
- **新平台首次出现**: buy_trades/sell_trades/events 循环中对 `cash_key not in positions` 做了初始化处理。
- **manual_market_value 覆盖**: 仅在 `target_date` 精确匹配时替换，其值自然流入后续日期的增量基准。

### 不影响的函数

- `position_service.py` 中的 `compute_cash_balance` 和 `get_cash_value` 保持不变（仍用于 `calculate_available_cash` 实时查询场景）
- `calculate_available_cash` 中的 baseline 逻辑仍从快照读取（快照已用增量法生成，含 manual override），无需修改

---

## Test Plan

1. **Issue #15**: 设置 `IR_HTTP_TIMEOUT=5` 后发起长请求，验证 5s 超时；不设置时验证默认 300s 生效。
2. **Issue #17**: 复现 issue 描述的场景——设置 manual_market_value 后生成次日快照，验证增量传递正确；验证首次快照（无 prev_snapshot）现金计算结果与旧版一致。

---

## Assumptions

- `get_cash_value` 和 `compute_cash_balance` 仍保留，供 `calculate_available_cash`（实时查询）使用，不删除。
- 改动 4 中 events 循环需要处理窗口约束：当前查询已限制 `ex_date <= target_date`，增量窗口还需 `ex_date >= start_apply_date`——但现有查询未加此约束（从 entitlement_date 排序应用，但未限制起始日）。由于原逻辑对基金份额变动也未加 `ex_date >= start_apply_date`（依靠"跳过已在前一日快照中反映的事件"的隐含逻辑——因为前一日快照已包含 ex_date <= prev_snapshot 的事件效果），CASH 增量法同理：前一日 CASH amount 已包含了 ex_date <= prev_snapshot 的事件 cash_change，窗口内只需处理 `ex_date > prev_snapshot AND ex_date <= target_date` 的事件。需要在 events 查询中加入 `ex_date >= start_apply_date` 条件以避免重复累加。这一修正同时适用于基金份额变动（当前虽然基金端没有问题因为 shares_change 是绝对值而非增量，但 CASH 的 cash_change 是增量值，必须限制窗口）。
