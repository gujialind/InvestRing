# ShareChangeEvent platform_code 强制 + 关联约束修订

> **来源：** Docs/08 2026-07-11 最终修订（commit e923e9b）
> **状态：** 待评估与实施

---

## 变更摘要

本次变更涉及 **ShareChangeEvent 表结构、创建约束、确认逻辑、快照应用** 四个层面的修改。核心变更：`platform_code` 从「部分场景必填」改为「所有 event_type 一律必填」；基金份额应用须按平台精确匹配 `portfolio_position` 持仓。

---

## 1. 数据库变更

### 1.1 ShareChangeEvent.platform_code 非空约束

```
旧：platform_code VARCHAR(20) NULL
新：platform_code VARCHAR(20) NOT NULL
```

**理由：** 不同平台可设置不同分红方式（现金分红 vs 红利再投），份额变动事件须精确到平台。`portfolio_position` 中同一基金在不同平台为独立持仓记录。

### 1.2 迁移（开发测试阶段可直接重置）

```sql
-- 若表中有数据：
UPDATE share_change_event SET platform_code = 'DEFAULT' WHERE platform_code IS NULL;
ALTER TABLE share_change_event MODIFY platform_code VARCHAR(20) NOT NULL;
```

---

## 2. Schema 变更

**文件：** `backend/app/schemas/share_change_event.py`

```
旧：
  platform_code: Optional[str] = None  # ShareChangeEventBase / Create

新：
  platform_code: str  # ShareChangeEventBase / Create，所有 event_type 必填
```

`ShareChangeEventCreate` 中移除 `platform_code` 的条件必填逻辑——改为统一必填。

---

## 3. 录入层约束变更

**文件：** `backend/app/routers/share_change_events.py` — `create_share_change_event`

已有约束（保持不变）：

| # | 约束 |
|---|---|
| (a) | `ex_date > D`（D = 最新快照日，Task 15 已实现） |
| (b) | `ex_date`、`entitlement_date` 非空 |
| (d) | `ex_date > entitlement_date` |
| (e) | `ex_date`、`entitlement_date` 均为交易日 |
| (g) | `create/update/delete_position` 禁止直接操作 `portfolio_position` |

**本次新增/修改：**

| # | 约束 | 说明 |
|---|---|---|
| **(new)** | `platform_code` 对所有 event_type 非空，且 `platform` 表存在 | 替换旧的条件必填逻辑 |
| (c) | **删除** `ex_date == entitlement_date 拒绝创建` | 与 (d) 矛盾——(d) 已拒绝所有 ≤，不需要单独 = |
| (d) | 保持 `ex_date > entitlement_date` | 基数日必须严格早于应用日，否则快照生成死锁（见下文 §5） |

---

## 4. 确认逻辑变更

**文件：** `backend/app/routers/share_change_events.py` — `confirm_share_change_event`

### 4.1 读取 entitlement_shares 时的匹配条件

```
旧（原 SPEC Task 12）：
  position = db.query(PortfolioPosition).filter(
      PortfolioPosition.portfolio_code == event.portfolio_code,
      PortfolioPosition.product_code == event.product_code,
      PortfolioPosition.snapshot_date == event.entitlement_date,
  ).first()

新：
  position = db.query(PortfolioPosition).filter(
      PortfolioPosition.portfolio_code == event.portfolio_code,
      PortfolioPosition.product_code == event.product_code,
      PortfolioPosition.platform_code == event.platform_code,   ← 新增
      PortfolioPosition.snapshot_date == event.entitlement_date,
  ).first()
```

**理由：** `portfolio_position` 中同一基金在不同平台为独立持仓（如 `000001.OF` 在平台 A 持仓 5000 份，平台 B 持仓 3000 份）。事件的 `entitlement_shares` 只取事件关联平台的持仓份额。

---

## 5. 快照事件应用变更

**文件：** `backend/app/services/snapshot_service.py` — `_generate_portfolio_position`

### 5.1 基金份额应用须按平台匹配

```
旧（原 SPEC Task 11 伪代码）：
  fund_key = (event.product_code, event.market, None)  # 注释："基金份额不分平台"

新：
  fund_key = (event.product_code, event.market, event.platform_code)
```

**理由：** 从 `entitlement_date` 快照读取的 `entitlement_shares` 已是该平台的份额（§4.1 变更后）。快照应用时同样写入该平台对应的 `portfolio_position` 记录，保证份额变更只影响目标平台。

### 5.2 确认字段已预计算，直接读取

Task 12 已实现在确认时预计算 `shares_before`/`shares_change`/`shares_after`/`cash_change`。事件应用时直接读这些字段，无需重算。

---

## 6. 级联回退变更

**文件：** `backend/app/services/snapshot_service.py` — `_cascade_unconfirm_share_change_events`

已实现（Task 13），无需变更。`platform_code` 从 NOT NULL 字段恢复为原值，无需特殊处理。

---

## 7. 受影响的验收项

### 数据库

- [ ] `share_change_event.platform_code` 改为 `NOT NULL`

### 份额变动事件

- [ ] ShareChangeEvent 的 `platform_code` 对所有 event_type 录入时必填
- [ ] `confirm_share_change_event` 读取 `entitlement_shares` 时按 `platform_code` 过滤
- [ ] `_generate_portfolio_position` 事件应用按 `(product_code, market, platform_code)` 匹配持仓
- [ ] `ex_date > entitlement_date` 约束（录入拦截；无单独的 == 拒绝分支）

---

## 8. 为什么必须是 `>` 而不是 `>=`

当 `ex_date == entitlement_date == target_date` 时：

```
生成 target_date 快照
  → 需要应用事件（ex_date == target_date）
    → 需要 entitlement_shares（从 entitlement_date 快照读）
      → entitlement_date == target_date → 快照正在生成中，数据库中不存在
        → 死锁
```

`ex_date > entitlement_date` 保证基数日快照必然在应用日前一天已生成——无死锁。

---

## 9. 影响范围总结

| 文件 | 改动 | 改动量 |
|---|---|---|
| `models/share_change_event.py` | `platform_code` nullable → NOT NULL | 1 行 |
| `schemas/share_change_event.py` | `Optional[str]` → `str`；移除条件必填 | ~5 行 |
| `routers/share_change_events.py` | create 统一校验 platform_code 非空；删除 (c) 约束 | ~5 行 |
| `routers/share_change_events.py` | confirm 读取 entitlement_shares 加 platform_code 过滤 | 1 行 |
| `snapshot_service.py` | 事件应用 fund_key 匹配 platform_code | 1 行 |
| 数据库 | ALTER TABLE NOT NULL | 1 条 DDL |
