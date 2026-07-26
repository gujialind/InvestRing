# ShareChangeEvent 分级设计与 platform_code 修订

## 设计原则

### 事件分级

| event_type | 级别 | platform_code | 录入方式 |
|---|---|---|---|
| `share_split` | 基金级 | NULL | 录入 1 条，确认时自动拆分 |
| `share_merge` | 基金级 | NULL | 同上 |
| `bonus_share` | 基金级 | NULL | 同上 |
| `cash_dividend` | 平台级 | 必填 | 每个有持仓的平台各录 1 条 |
| `reinvest_dividend` | 平台级 | 必填 | 同上 |
| `forced_adjustment` | 平台级 | 必填 | 同上 |

### 自动拆分机制（确认时）

基金级事件确认时：
1. 查询 `entitlement_date` 快照中该基金所有平台的持仓
2. 为每个 `shares > 0` 的平台创建子记录（`parent_event_id` 指向父记录，`platform_code` = 该平台）
3. 子记录的 `entitlement_shares`/`shares_before`/`shares_change`/`shares_after` 按该平台独立计算
4. 父记录的汇总值设为各平台之和（审计用）

### 全覆盖校验（创建时）

平台级事件创建时：
1. 查询 `entitlement_date`（或最近快照日）该基金所有有持仓的平台
2. 检查同 `(portfolio, product, market, ex_date)` 是否已有各平台的事件
3. 未全覆盖 → 返回 warning（不阻断），列出未覆盖的平台

---

## Task 1: 模型与 Schema 变更

**文件:** `backend/app/models/share_change_event.py`

```python
# platform_code 保持 nullable=True（基金级事件为 NULL）
platform_code = Column(String(20), ForeignKey("platform.code"), nullable=True)

# 新增 parent_event_id（子记录指向父记录）
parent_event_id = Column(Integer, ForeignKey("share_change_event.id"), nullable=True)
```

**文件:** `backend/app/schemas/share_change_event.py`

- `ShareChangeEventBase`: `platform_code` 保持 `Optional[str] = None`
- `ShareChangeEventBase`: 新增 `parent_event_id: Optional[int] = None`
- `ShareChangeEventResponse`: 继承 `parent_event_id`
- `ShareChangeEventUpdate`: 移除 `platform_code`（创建后不可修改平台归属）

---

## Task 2: 录入层 — 分级校验 + 全覆盖检查

**文件:** `backend/app/routers/share_change_events.py` — `create_share_change_event`

### 2a: 替换现有条件必填逻辑（第 110-126 行）

删除现有的 `cash_dividend` / `forced_adjustment` 条件必填块，替换为：

```python
FUND_LEVEL_TYPES = {"share_split", "share_merge", "bonus_share"}
PLATFORM_LEVEL_TYPES = {"cash_dividend", "reinvest_dividend", "forced_adjustment"}

if event.event_type in PLATFORM_LEVEL_TYPES:
    # 平台级：platform_code 必填 + 平台存在性校验
    if not event.platform_code:
        raise HTTPException(422, detail={
            "error": "PLATFORM_REQUIRED",
            "message": f"{event.event_type} 为平台级事件，必须指定 platform_code"
        })
    platform = db.query(Platform).filter(Platform.code == event.platform_code).first()
    if not platform:
        raise HTTPException(404, detail={
            "error": "PLATFORM_NOT_FOUND",
            "message": f"平台 {event.platform_code} 不存在"
        })
    # 全覆盖校验（warning，不阻断）
    uncovered = _check_platform_coverage(db, event)
    if uncovered:
        logger.warning(f"平台覆盖不完整: {uncovered}")
        # 不 raise，在 response 中附加 warning

elif event.event_type in FUND_LEVEL_TYPES:
    # 基金级：platform_code 必须为空
    if event.platform_code:
        raise HTTPException(422, detail={
            "error": "PLATFORM_NOT_ALLOWED",
            "message": f"{event.event_type} 为基金级事件，不应指定 platform_code"
        })
```

### 2b: 新增全覆盖校验函数

```python
def _check_platform_coverage(db, event) -> list[str]:
    """检查同 ex_date 的平台级事件是否覆盖所有有持仓的平台"""
    # 查 entitlement_date（或最近快照日）该基金所有有持仓的平台
    positions = db.query(PortfolioPosition.platform_code).filter(
        PortfolioPosition.portfolio_code == event.portfolio_code,
        PortfolioPosition.product_code == event.product_code,
        PortfolioPosition.snapshot_date == event.entitlement_date,  # 或最近快照日
        PortfolioPosition.shares > 0,
    ).distinct().all()
    held_platforms = {p[0] for p in positions}

    # 查同 ex_date 已有的事件覆盖了哪些平台
    existing = db.query(ShareChangeEvent.platform_code).filter(
        ShareChangeEvent.portfolio_code == event.portfolio_code,
        ShareChangeEvent.product_code == event.product_code,
        ShareChangeEvent.ex_date == event.ex_date,
        ShareChangeEvent.status != "cancelled",
        ShareChangeEvent.platform_code.isnot(None),
    ).distinct().all()
    covered = {p[0] for p in existing}

    return list(held_platforms - covered)
```

---

## Task 3: 确认逻辑 — 基金级自动拆分 + 平台级 platform_code 过滤

**文件:** `backend/app/routers/share_change_events.py` — `confirm_share_change_event`

### 3a: 平台级事件 — 修复 entitlement_shares 读取（BUG #1）

在第 180-188 行的 `entitlement_position` 查询中新增 `platform_code` 过滤：

```python
entitlement_position = db.query(PortfolioPosition).filter(
    PortfolioPosition.portfolio_code == event.portfolio_code,
    PortfolioPosition.product_code == event.product_code,
    PortfolioPosition.platform_code == event.platform_code,  # ← 新增
    PortfolioPosition.snapshot_date == event.entitlement_date,
).first()
```

### 3b: 基金级事件 — 自动生成子记录

在确认逻辑中，根据 `event.platform_code` 是否为 NULL 分两条路径：

```python
if event.platform_code is None:
    # 基金级事件：自动拆分
    all_positions = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == event.portfolio_code,
        PortfolioPosition.product_code == event.product_code,
        PortfolioPosition.snapshot_date == event.entitlement_date,
        PortfolioPosition.shares > 0,
    ).all()

    if not all_positions:
        raise HTTPException(422, detail={
            "error": "MISSING_POSITION_SNAPSHOT",
            "message": "权益登记日无持仓，无需确认"
        })

    total_shares = Decimal("0")
    for pos in all_positions:
        total_shares += Decimal(str(pos.shares or 0))
        # 创建子记录
        child = ShareChangeEvent(
            portfolio_code=event.portfolio_code,
            product_code=event.product_code,
            market=event.market,
            event_type=event.event_type,
            ex_date=event.ex_date,
            entitlement_date=event.entitlement_date,
            platform_code=pos.platform_code,
            event_source=event.event_source,
            parent_event_id=event.id,
            entitlement_shares=Decimal(str(pos.shares or 0)),
            shares_before=Decimal(str(pos.shares or 0)),
            ratio=event.ratio,
            div_cash=event.div_cash,
            reinvest_nav=event.reinvest_nav,
            status="confirmed",
            confirmed_at=datetime.now(),
        )
        # 按公式计算子记录 shares_change/shares_after/cash_change
        _compute_event_fields(child)
        db.add(child)

    # 父记录设汇总值
    event.entitlement_shares = total_shares
    event.shares_before = total_shares
    # 父记录的 shares_after/shares_change 为汇总（审计用）
    _compute_event_fields(event)  # 用 total_shares 计算
else:
    # 平台级事件：原有逻辑 + platform_code 过滤（Task 3a）
    ...
```

### 3c: 抽取计算逻辑为公共函数

```python
def _compute_event_fields(event: ShareChangeEvent):
    """按 event_type 计算 shares_change/shares_after/cash_change"""
    es = event.entitlement_shares or Decimal("0")
    if event.event_type == "cash_dividend":
        event.cash_change = es * Decimal(str(event.div_cash or 0))
        event.shares_change = Decimal("0")
        event.shares_after = es
    elif event.event_type == "reinvest_dividend":
        event.shares_change = es * Decimal(str(event.div_cash or 0)) / Decimal(str(event.reinvest_nav or 1))
        event.shares_after = es + event.shares_change
        event.cash_change = Decimal("0")
    elif event.event_type == "share_split":
        event.shares_after = es * Decimal(str(event.ratio or 1))
        event.shares_change = event.shares_after - es
        event.cash_change = Decimal("0")
    elif event.event_type == "share_merge":
        event.shares_after = es / Decimal(str(event.ratio or 1))
        event.shares_change = event.shares_after - es
        event.cash_change = Decimal("0")
    elif event.event_type == "bonus_share":
        event.shares_change = es * Decimal(str(event.ratio or 0))
        event.sh