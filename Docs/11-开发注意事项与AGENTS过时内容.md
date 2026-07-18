# 开发注意事项与 AGENTS.md 过时内容

> 日期：2026-07-18
> 用途：为开发 agent 提供 issue 实施注意事项，并标注 AGENTS.md 中与代码实际不符的内容
> 关联 issue：#20, #23-#40（共 19 个）

---

## 1. AGENTS.md 过时内容清单

以下内容与实际代码不符，开发时以代码为准，AGENTS.md 需后续更新：

### 1.1 §1.4 "快照表中 CASH 持仓由 get_cash_value 统一计算"

| AGENTS.md 描述 | 实际代码 |
|---------------|---------|
| "快照表中 CASH 持仓：由 `get_cash_value` → `compute_cash_balance` 统一计算，不再在 `_generate_portfolio_position` 中增量累加" | 快照生成走增量累加路径（`snapshot_service.py:498-618`），未调 `get_cash_value` |
| "实时预览调 `compute_cash_balance(today)`，快照生成调 `get_cash_value(date)`" | 快照生成未调 `get_cash_value`；`calculate_available_cash` 基线调 `get_cash_value(latest_date)` |

关联：Issue #28（注释不一致）、#39（统一路径建议）

### 1.2 §1.4 "confirm/unconfirm/cancel 配对 CASH 腿自动同步"

| AGENTS.md 描述 | 实际代码 |
|---------------|---------|
| "confirm/unconfirm/cancel 基金腿时，配对 CASH 腿自动同步" | confirm/unconfirm/cancel 有 `_sync_transfer_group`，但 **PUT 和 DELETE 没有**配对同步 |

关联：Issue #26

### 1.3 §1.1 "生成前提：当天应确认交易都已处理完"

| AGENTS.md 描述 | 实际代码 |
|---------------|---------|
| "生成前提：净值和分红事件更新完成 + 当天应确认交易都已处理完" | auto_confirm 在快照生成**之后**才确认交易。Subscription 前置校验用 `apply_date < D`（允许当天 pending 存在），非"已处理完" |

关联：Issue #33（auto_confirm 时序重新设计）

### 1.4 §1.2 "买入冻结金额实时计算"

| AGENTS.md 描述 | 实际代码 |
|---------------|---------|
| "买入冻结金额：SUM(trade.amount) WHERE trade_type='buy' AND status='pending'" | `PortfolioPosition.frozen_amount` 固定为 0（`snapshot_service.py:673` 简化未实现） |

关联：Issue #40（遗留字段补全）

### 1.5 AGENTS.md 缺失内容

| 缺失项 | 说明 | 关联 issue |
|--------|------|-----------|
| auto_confirm_after_snapshot | 快照生成后自动确认 pending 交易的核心机制，AGENTS.md 未提及 | #29/#30/#31/#33 |
| 级联回退机制 | 删快照时回退 subscription/event 的逻辑，AGENTS.md 未描述 | #34 |
| force 模式 | 跳过校验生成快照的机制，AGENTS.md 未提及 | #32（建议移除） |

---

## 2. 实施依赖链

```
#20（TypeError，一行修复）→ 立即做，不依赖任何其他 issue

#34（Event 级联回退修复）→ 必须先做
  ↓ 是 #32 和 #33 的前提
#32（移除 force）+ #33（auto_confirm 时序重新设计）
  ↓ #33 依赖 #34，#32 依赖 #34
#29（Trade 净值获取）→ 与 #33 并行，但 #33 实施时需确认 #29 已修

独立可随时做：#23 / #24 / #25 / #26 / #35 / #36 / #37 / #38 / #39 / #40
```

**关键**：#34 不修复就动 #32/#33，会导致快照重新生成死锁。

---

## 3. 各 Issue 实施要点

### #20（P1）零持仓守卫 TypeError

```python
# snapshot_service.py:626 当前
pos_data.get("amount", Decimal("0")) <= 0  # amount=None 时返回 None → TypeError

# 改为
(pos_data.get("amount") or Decimal("0")) <= 0
```

一行修复，立即做。

### #34（P1）Event 级联回退过度回退

```python
# snapshot_service.py:371-374 当前
or_(
    ShareChangeEvent.ex_date == snapshot_date,        # ← 删这行
    ShareChangeEvent.entitlement_date == snapshot_date, # ← 保留
)

# 改为（只保留 entitlement_date 条件）
ShareChangeEvent.entitlement_date == snapshot_date,
```

**注意**：只删 `ex_date == snapshot_date` 分支，不要误删整个 OR。

### #33（P1）auto_confirm 时序重新设计

5 处改动必须整体实施：

| # | 改动 | 文件 | 注意事项 |
|---|------|------|---------|
| 1 | Subscription 创建时设定 confirm_date | `subscriptions.py:185-188` | 对齐 Trade，confirm 时仍可覆盖（补录场景） |
| 2 | 前置校验 `apply_date < D` → `confirm_date <= D` | `snapshot_service.py:1103` | **换字段**，不是简单改 `<` 为 `<=` |
| 3 | auto_confirm 查询 `== D` → `== next_trading_day(D)` | `snapshot_service.py:950,988,1028` | 用 `next_trading_day` 不是硬编码 D+1 |
| 4 | 定时任务循环逐日处理 | `task_runner.py:76` | 终止条件 `current == today` |
| 5 | 移除 force 模式 | 多处 | 与 #32 合并 |

**关键区分**：`apply_date < D` → `confirm_date <= D` 是**换字段**（安全，效果等价），不是 `apply_date < D` → `apply_date <= D`（危险，会阻断当天 pending 导致死锁）。

### #29（P1）auto_confirm Trade 不重新获取净值

```python
# snapshot_service.py:956 当前
trade.status = "confirmed"  # 直接改 status，跳过净值获取

# 改为：提取 confirm_trade 的净值获取逻辑为公共函数
def _confirm_trade_logic(db, trade, product, confirm_date=None, price=None):
    """trade 确认核心逻辑，供手动和自动确认共用"""
    # 1. 获取净值（QDII 严格 T 日，非 QDII 建议改严格，见 #24）
    # 2. 重新计算 shares/amount
    # 3. 设置 status = confirmed
```

**注意**：QDII 净值获取更严格（`MISSING_QDII_NAV`），场内产品不需要净值（用收盘价）。

### #26（P1）PUT/DELETE 配对 CASH 同步

PUT 和 DELETE 的配对处理逻辑**不同**，不要混用：
- **PUT**：改基金腿金额后，**同步更新**配对 CASH 腿的 `amount`（不是删）
- **DELETE**：删基金腿后，**级联删除**配对 CASH 腿（不是更新）

### #23（P1）可用份额计算缺 as_of_date

三个函数统一增加 `as_of_date` 参数：
- `calculate_investor_available_shares`（position_service.py:220 + subscriptions.py:36 副本）
- `calculate_available_shares`（position_service.py:169 + trades.py:157 副本）
- `calculate_available_cash`（position_service.py:100）

调用处传 `subscription.apply_date` / `trade.trade_date`。**关联问题**：基线快照后到 as_of_date 之间的 confirmed 申购未加回（偏保守），完整修复需同时加回。

### #36（P1）批量删除逐日 commit

```python
# snapshots.py:250-270 当前
for snap_date in snapshot_dates:
    result = _delete_existing_snapshots(...)
db.commit()  # ← 最后统一 commit

# 改为
for snap_date in snapshot_dates:
    result = _delete_existing_snapshots(...)
    db.commit()  # ← 每日独立 commit
```

### #24（P2）非 QDII 净值严格取 T 日

```python
# trades.py:98-101 当前
PriceRecord.date <= trade_date  # 向前回溯

# 改为
PriceRecord.date == trade_date  # 严格匹配
```

### #25（P2）trade unconfirm 加快照保护

对齐 subscription 的 `SNAPSHOT_DEPENDENCY` 检查。

### #35（P2）快照连续性保证

优先实施建议 1（循环失败后停止）和建议 2（定时任务补生成缺失快照）。

---

## 4. 不要改的（设计正确，非缺陷）

| 设计 | 原因 | 关联 issue |
|------|------|-----------|
| Trade 不级联回退 | trade confirm 依赖 PriceRecord 不依赖快照，不回退正确 | 已在文档确认 |
| cancel 场内/场外差异 | 模拟交易所"已成交不可撤销"语义 | 保持现状 |
| CASH 双路径 manual 边界 | 快照用 target_date 日终，实时用 latest_date 过去日终，不查 today | 已验证正确 |
| Subscription 前置校验 `apply_date < D` | **不要单独改为 `apply_date <= D`**（会阻断当天 pending 导致死锁）。#33 方案是换字段为 `confirm_date <= D`（效果等价） | #33 |

---

## 5. 测试要点

开发 agent 必须覆盖以下场景：

| 场景 | 涉及 issue | 验证点 |
|------|-----------|--------|
| 全部卖出基金（shares=0） | #20 | 快照不崩溃，持仓记录跳过 |
| 补录历史交易 | #23/#34/#35 | 删快照→级联回退→重新生成→数据一致 |
| 首次申购 | #33 | NAV=1.0000，组合 draft→active |
| 跨平台现金转移（当天+跨天） | #33 | 对称状态，D 日 NAV 不虚跌 |
| 场外基金 T+1 确认 | #29/#33 | shares 用实际净值重算 |
| 现金分红 event | #34 | ex_date==D 的 event 不被过度回退 |
| 修改 pending trade 金额 | #26 | 配对 CASH 腿同步更新 |
| 删除 pending trade | #26 | 配对 CASH 腿级联删除 |
| 定时任务跳天后补运行 | #35 | 缺失快照补生成 |
| 补录时后续日期交易不影响校验 | #23 | as_of_date 过滤后续交易 |

---

## 6. 代码风格约定

- 保持单 `db.commit()` 事务边界（除非实施 #37 加了 savepoint）
- 错误信息给出修正路径（如"请使用 PUT 修改字段或 DELETE 删除重录"）
- 关键操作加 `logger.info` / `logger.warning`
- 不要引入 `with db.begin()` 除非实施 #37

---

## 7. 参考文档

| 文档 | 用途 |
|------|------|
| `Docs/10-交易与快照核心逻辑梳理.md` | 完整的架构分析（实体关系、数据流转、事务边界、优化建议） |
| `AGENTS.md` | 核心业务规则（注意 §1.1-§1.4 部分内容过时，见本文档第 1 节） |
| `backend/CLI_MANUAL.md` | CLI 命令手册（ir-cli） |
| 各 issue body | 具体问题和修复建议 |

---

## 8. Issue 完整清单（#20 + #23-#40）

| Issue | 优先级 | 问题 | 依赖 |
|-------|--------|------|------|
| #20 | P1 | 零持仓守卫 TypeError | 无 |
| #23 | P1 | 可用份额计算缺 as_of_date | 无 |
| #24 | P2 | 非 QDII 净值 fallback | 无 |
| #25 | P2 | trade unconfirm 无快照保护 | 无 |
| #26 | P1 | PUT/DELETE 未同步配对 CASH trade | 无 |
| #27 | P2 | ir-cli 缺约束说明 + 命令 | #25/#26 |
| #28 | P3 | compute_cash_balance 注释不一致 | 无 |
| #29 | P1 | auto_confirm Trade 不重新获取净值 | 与 #33 并行 |
| #30 | P2 | auto_confirm 日期条件不一致 | #33 解决 |
| #31 | P2 | auto_confirm Event 确认时序 | #33 解决 |
| #32 | P2 | 移除 force 模式 | #34 |
| #33 | P1 | auto_confirm 时序重新设计 | #34 |
| #34 | P1 | Event 级联回退过度回退 | 无（最先做） |
| #35 | P2 | 交易日快照缺失连锁失败 | 无 |
| #36 | P1 | 批量删除统一 commit | 无 |
| #37 | P2 | 并发安全（行锁 + savepoint） | 无 |
| #38 | P2 | Event unconfirm 接口 | 无 |
| #39 | P2 | 消除代码重复 + 统一 CASH 路径 | 无 |
| #40 | P3 | 健壮性改进合集 | 无 |

### 建议实施顺序

1. **#20**（一行修复，立即做）
2. **#34**（前提条件，必须先做）
3. **#33 + #32 + #29**（架构改进，一起做）
4. **#23 / #26 / #36**（独立 P1，可并行）
5. **P2 批次**：#24 / #25 / #35 / #37 / #38 / #39
6. **P3 批次**：#27 / #28 / #40
