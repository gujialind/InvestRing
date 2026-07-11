# 现金与交易录入重构实现计划

## 前置条件

- 重置数据库（开发测试阶段，无需迁移脚本）
- 所有讨论结论已确认（Q1-Q8 + 显式化方案 + 对称状态 + 创建时设定 confirm_date）

---

## P0 — 阻塞所有后续任务

### Task 1: Trade 模型新增 expected_confirm_date 逻辑（改用创建时设定 confirm_date）

**文件:** `backend/app/models/trade.py`
- 无需新增字段，复用已有 `confirm_date`

**文件:** `backend/app/routers/trades.py`
- `create_trade`（line 331-445）：创建 Trade 时计算 `confirm_date = _get_next_trading_day(db, trade.trade_date, days=product.confirm_days or 0)` 并写入
- `confirm_trade`（line 460-547）：简化逻辑 — 若传入 `confirm_date` 参数则覆盖，否则保留创建时已设定的值；去掉 `if confirm_date is None` 自动推算分支
- 配对 CASH trade（Task 4）的 `confirm_date` 与基金腿同步

**文件:** `backend/app/routers/cash_transfers.py`
- `create_cash_transfer`（line 51-190）：
  - cross_day=False：两腿 `confirm_date = transfer_date`（不变）
  - cross_day=True：两腿均 `status="pending"`、`confirm_date = _get_next_trading_day(db, transfer_date)`（对称状态改造，原设计卖腿 confirmed 买腿 pending 改为均 pending）

### Task 2: event_date -> ex_date 全局改名

**文件:**
- `backend/app/models/share_change_event.py`（line 13: `event_date` → `ex_date`）
- `backend/app/schemas/share_change_event.py`（line 9, 33: `event_date` → `ex_date`）
- `backend/app/routers/share_change_events.py`（所有引用 `event_date` 处）
- `backend/app/services/snapshot_service.py`（line 1050: `_check_share_change_events` 中的查询条件改用 `ex_date`）
- `Docs/02-数据库设计.md`（line 428, 595）
- `Docs/03-业务流程设计.md`（8 处，见设计文档 §16）

### Task 3: 快照硬闸门修复

**文件:** `backend/app/services/snapshot_service.py`
**函数:** `_check_pending_transactions`（line 936-965）

Trade 分支改为：
```python
pending_trades = db.query(Trade).filter(
    Trade.portfolio_code == portfolio_code,
    Trade.status == "pending",
    Trade.confirm_date <= target_date,
).count()
```

Subscription 分支不变（保持 `apply_date < target_date`）。

### Task 4: ShareChangeEvent 模型新增 platform_code 字段

**文件:** `backend/app/models/share_change_event.py`
- 新增 `platform_code = Column(String(20), ForeignKey("platform.code"), nullable=True)`
- 用途：现金分红等事件的 cash_change 归属平台。`forced_adjustment` 的外部注资/抽资可不限定平台（nullable）

**文件:** `backend/app/schemas/share_change_event.py`
- `ShareChangeEventBase` 新增 `platform_code: Optional[str] = None`
- `ShareChangeEventCreate` 中 `platform_code` 对 cash_dividend / forced_adjustment(cash_change!=0) 为必填

---

## P1 — 现金显式化 + regen 闭环

### Task 5: 申购/赎回确认时生成 CASH trade

**文件:** `backend/app/services/subscription_service.py`
**函数:** `confirm_single_subscription`（line 40-134）

在设置 `subscription.status = "confirmed"` 之后、`db.flush()` 之前，创建 CASH trade：

```python
from app.models.trade import Trade

cash_trade = Trade(
    portfolio_code=subscription.portfolio_code,
    platform_code=subscription.platform_code,
    product_code="CASH",
    market="",
    trade_type="buy" if subscription.sub_type == "subscribe" else "sell",
    amount=subscription.amount,
    price=Decimal("1"),
    fee=Decimal("0"),
    actual_amount=subscription.amount,
    trade_date=subscription.apply_date,
    confirm_date=subscription.confirm_date,
    status="confirmed",
    transfer_group=f"sub_{subscription.id}",
)
db.add(cash_trade)
```

### Task 6: 申购取消确认时删除 CASH trade

**文件:** `backend/app/services/subscription_service.py`
**函数:** `unconfirm_single_subscription`（line 137-177）

在 `subscription.status = "pending"` 之后，物理删除关联 CASH trade：

```python
db.query(Trade).filter(
    Trade.transfer_group == f"sub_{subscription.id}"
).delete()
```

**理由:** CASH trade 是派生记录，生命周期完全跟随 subscription。物理删除避免唯一约束冲突（regen 重新确认时需创建新 CASH trade）。

### Task 7: 基金调仓创建时配对 CASH trade

**文件:** `backend/app/routers/trades.py`
**函数:** `create_trade`（line 331-445）

基金买入时追加 CASH sell，基金卖出时追加 CASH buy：

```python
import uuid

transfer_group = f"rebal_{uuid.uuid4().hex[:12]}"
# 基金 trade 设置 transfer_group
new_trade.transfer_group = transfer_group

# 配对 CASH trade
cash_trade = Trade(
    portfolio_code=trade.portfolio_code,
    platform_code=trade.platform_code,
    product_code="CASH",
    market="",
    trade_type="sell" if trade.trade_type == "buy" else "buy",
    amount=Decimal(str(trade.actual_amount)) if trade.actual_amount else Decimal(str(trade.amount)),
    # 注意：用 actual_amount（含手续费的总成本/总收入），非 trade.amount（净值）
    price=Decimal("1"),
    fee=Decimal("0"),
    actual_amount=Decimal(str(trade.actual_amount)) if trade.actual_amount else Decimal(str(trade.amount)),
    trade_date=trade.trade_date,
    confirm_date=new_trade.confirm_date,  # 与基金腿同步（Task 1 已设定）
    status="pending",  # 与基金腿同步
    transfer_group=transfer_group,
)
db.add(cash_trade)
```

**关键:** CASH trade 的 amount 取 `actual_amount`（实际支付/收到的总额），非 `trade.amount`（扣/加费后的净值）。

### Task 8: transfer_group 原子翻转（confirm/unconfirm/cancel 级联）

**文件:** `backend/app/routers/trades.py`
**函数:** `confirm_trade`、`unconfirm_trade`、`cancel_trade`

新增工具函数：
```python
def _sync_transfer_group(db: Session, trade: Trade, target_status: str, confirm_date: Optional[date] = None):
    """同步 transfer_group 关联的另一腿状态"""
    if not trade.transfer_group:
        return
    paired = db.query(Trade).filter(
        Trade.transfer_group == trade.transfer_group,
        Trade.id != trade.id,
    ).first()
    if paired:
        paired.status = target_status
        if confirm_date is not None:
            paired.confirm_date = confirm_date
        elif target_status == "pending":
            paired.confirm_date = None  # unconfirm 时清空
```

在 `confirm_trade`、`unconfirm_trade`、`cancel_trade` 中调用此函数。

**文件:** `backend/app/routers/cash_transfers.py`
**函数:** `confirm_cash_transfer`（line 193-249）

改为同时确认 transfer_group 的两条 pending trade（对称状态改造后两腿均 pending）：
- 保留 TRANSFER_NOT_READY 守卫
- 找到 transfer_group 下所有 pending trade → 同时 confirmed，confirm_date = next_trading_day(transfer_date)

### Task 9: compute_cash_balance 实现

**文件:** `backend/app/services/position_service.py`（替换 `calculate_available_cash`）

```python
def compute_cash_balance(db, portfolio_code, platform_code=None, as_of_date=None):
    """
    显式计算 as_of_date 时的现金余额。
    源1：trade 表 confirmed CASH trades（confirm_date <= as_of_date）
    源2：event 表 confirmed events（ex_date <= as_of_date, cash_change != 0）
    不含 manual_market_value 覆盖。
    """
    if as_of_date is None:
        as_of_date = date.today()
    balance = Decimal("0")

    # 源1：CASH trades
    trades = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.product_code == "CASH",
        Trade.status == "confirmed",
        Trade.confirm_date <= as_of_date,
    )
    if platform_code:
        trades = trades.filter(Trade.platform_code == platform_code)
    for t in trades:
        if t.trade_type == "buy":
            balance += Decimal(str(t.amount or 0))
        elif t.trade_type == "sell":
            balance -= Decimal(str(t.amount or 0))

    # 源2：事件 cash_change
    events = db.query(ShareChangeEvent).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.status == "confirmed",
        ShareChangeEvent.ex_date <= as_of_date,
        ShareChangeEvent.cash_change.isnot(None),
        ShareChangeEvent.cash_change != 0,
    )
    if platform_code:
        events = events.filter(ShareChangeEvent.platform_code == platform_code)
    for e in events:
        balance += Decimal(str(e.cash_change))

    return balance
```

**calculate_available_cash 改为：**
```python
def calculate_available_cash(db, portfolio_code, platform_code=None):
    latest_date = get_latest_snapshot_date(db, portfolio_code)
    cash = compute_cash_balance(db, portfolio_code, platform_code, latest_date)

    # 快照后 confirmed CASH trades
    after_trades = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.product_code == "CASH",
        Trade.status == "confirmed",
        Trade.confirm_date > latest_date if latest_date else True,
    )
    if platform_code:
        after_trades = after_trades.filter(Trade.platform_code == platform_code)
    for t in after_trades:
        if t.trade_type == "buy":
            cash += Decimal(str(t.amount or 0))
        elif t.trade_type == "sell":
            cash -= Decimal(str(t.amount or 0))

    # pending CASH sells（已承诺未执行）
    pending_sells = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.product_code == "CASH",
        Trade.status == "pending",
        Trade.trade_type == "sell",
    )
    if platform_code:
        pending_sells = pending_sells.filter(Trade.platform_code == platform_code)
    for t in pending_sells:
        cash -= Decimal(str(t.amount or 0))

    # 快照后 confirmed event cash_change
    after_events = db.query(ShareChangeEvent).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.status == "confirmed",
        ShareChangeEvent.ex_date > latest_date if latest_date else True,
        ShareChangeEvent.cash_change.isnot(None),
        ShareChangeEvent.cash_change != 0,
    )
    if platform_code:
        after_events = after_events.filter(ShareChangeEvent.platform_code == platform_code)
    for e in after_events:
        cash += Decimal(str(e.cash_change))

    return cash
```

**删除所有旧版 `_calculate_available_cash`：**
- `backend/app/routers/trades.py`（line 128-256）
- `backend/app/routers/positions.py`（line 28-150）
- 所有调用点改调 `position_service.calculate_available_cash`

### Task 10: _generate_portfolio_position CASH 计算简化

**文件:** `backend/app/services/snapshot_service.py`
**函数:** `_generate_portfolio_position`（line 391-670）

删除以下 CASH 特殊处理分支：
- line 469-471: CASH 买入直改 amount
- line 497-506: CASH 卖出直改 amount
- line 510-533: 从前一日快照初始化 CASH 持仓
- line 535-573: 申购/赎回 CASH 影响
- line 576-605: 买入/卖出非CASH 对 CASH 的影响

替换为：
```python
# CASH 持仓：直接调用 get_cash_value
platforms = db.query(Trade.platform_code).filter(
    Trade.portfolio_code == portfolio_code,
    Trade.product_code == "CASH",
).distinct().all()

# 也包含事件涉及的 platform_code
event_platforms = db.query(ShareChangeEvent.platform_code).filter(
    ShareChangeEvent.portfolio_code == portfolio_code,
    ShareChangeEvent.platform_code.isnot(None),
).distinct().all()

all_platforms = set(p[0] for p in platforms) | set(p[0] for p in event_platforms if p[0])

for platform_code in all_platforms:
    cash_amount = get_cash_value(db, portfolio_code, platform_code, target_date)
    if cash_amount != 0:
        positions[("CASH", "", platform_code)] = {
            "shares": None,
            "amount": cash_amount,
            "cost_price": None,
            "asset_type": "cash",
        }
```

### Task 11: 份额变动事件在快照中应用（只改基金份额）

**文件:** `backend/app/services/snapshot_service.py`
**函数:** `_generate_portfolio_position`

在卖出交易应用之后（原 Step 3 后）、CASH 持仓初始化之前插入：

```python
# 应用份额变动事件（ex_date <= target_date 且 confirmed）
# 按 entitlement_date 升序处理
events = db.query(ShareChangeEvent).filter(
    ShareChangeEvent.portfolio_code == portfolio_code,
    ShareChangeEvent.status == "confirmed",
    ShareChangeEvent.ex_date <= target_date,
).order_by(ShareChangeEvent.entitlement_date.asc()).all()

for event in events:
    key = (event.product_code, event.market, event.platform_code)  # 份额变更用事件 platform
    # 注意：份额变更应作用到对应产品的持仓，不限定 platform（基金份额通常不分平台）
    # 实际应找对应 product_code + market 的持仓
    fund_key = (event.product_code, event.market, None)  # 基金份额不分平台
    
    # 按 event_type 公式应用（仅基金份额变更，现金由 compute_cash_balance 覆盖）
    if event.event_type == "reinvest_dividend":
        shares_change = event.entitlement_shares * event.div_cash / event.reinvest_nav
        # 找到或创建对应基金持仓，增加份额
        ...
    elif event.event_type == "share_split":
        # shares_after = entitlement_shares * ratio
        ...
    elif event.event_type == "share_merge":
        # shares_after = entitlement_shares / ratio
        ...
    elif event.event_type == "bonus_share":
        # shares_change = entitlement_shares * ratio
        ...
    # cash_dividend 和 forced_adjustment 的 cash_change 由 compute_cash_balance 覆盖，此处不处理
```

### Task 12: 事件确认时自动计算并回写字段

**文件:** `backend/app/routers/share_change_events.py`
**函数:** `confirm_share_change_event`（line 92-128）

在 `event.status = "confirmed"` 之前：

```python
# 从 entitlement_date 快照读取 entitlement_shares
position = db.query(PortfolioPosition).filter(
    PortfolioPosition.portfolio_code == event.portfolio_code,
    PortfolioPosition.product_code == event.product_code,
    PortfolioPosition.snapshot_date == event.entitlement_date,
).first()

if not position:
    raise MISSING_POSITION_SNAPSHOT

event.entitlement_shares = Decimal(str(position.shares or 0))
event.shares_before = Decimal(str(position.shares or 0))

# 按 event_type 计算 shares_change / shares_after / cash_change
if event.event_type == "cash_dividend":
    event.cash_change = event.entitlement_shares * Decimal(str(event.div_cash or 0))
    event.shares_change = Decimal("0")
    event.shares_after = event.entitlement_shares
elif event.event_type == "reinvest_dividend":
    event.shares_change = event.entitlement_shares * Decimal(str(event.div_cash or 0)) / Decimal(str(event.reinvest_nav or 1))
    event.shares_after = event.entitlement_shares + event.shares_change
    event.cash_change = Decimal("0")
elif event.event_type == "share_split":
    event.shares_after = event.entitlement_shares * Decimal(str(event.ratio or 1))
    event.shares_change = event.shares_after - event.entitlement_shares
    event.cash_change = Decimal("0")
elif event.event_type == "share_merge":
    event.shares_after = event.entitlement_shares / Decimal(str(event.ratio or 1))
    event.shares_change = event.shares_after - event.entitlement_shares
    event.cash_change = Decimal("0")
elif event.event_type == "bonus_share":
    event.shares_change = event.entitlement_shares * Decimal(str(event.ratio or 0))
    event.shares_after = event.entitlement_shares + event.shares_change
    event.cash_change = Decimal("0")
# forced_adjustment: shares_change / cash_change 由用户直接填写，不自动计算

event.confirmed_at = datetime.now()
```

### Task 13: 事件级联回退 + pending 事件拦截快照

**文件:** `backend/app/services/snapshot_service.py`

新增函数 `_cascade_unconfirm_share_change_events`：
```python
def _cascade_unconfirm_share_change_events(db, portfolio_code, snapshot_date):
    """删快照时级联回退依赖该快照的 confirmed 事件（双日期 OR）"""
    events = db.query(ShareChangeEvent).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.status == "confirmed",
        or_(
            ShareChangeEvent.ex_date == snapshot_date,
            ShareChangeEvent.entitlement_date == snapshot_date,
        ),
    ).all()
    for event in events:
        event.status = "pending"
        event.confirmed_at = None
        event.entitlement_shares = None
        event.shares_before = None
        event.shares_change = None
        event.shares_after = None
        event.cash_change = None
    return [{"id": e.id, "action": "unconfirmed"} for e in events]
```

在 `_delete_existing_snapshots`（line 355-388）中调用此函数。

修改 `_check_share_change_events`（line 1042-1060）：
- 查询条件改为 `ex_date <= target_date`（原为 `entitlement_date <= target_date`）
- status 从 "warning" 改为 "failed"（拦截快照生成）

### Task 14: auto_confirm_after_snapshot 扩展到 Trade + Event

**文件:** `backend/app/services/snapshot_service.py`
**函数:** `auto_confirm_after_snapshot`（line 838-916）

在现有 Subscription 自动确认之后，追加：

```python
# Trade 自动确认（confirm_date == snapshot_date 的 pending trades）
pending_trades = db.query(Trade).filter(
    Trade.portfolio_code == portfolio_code,
    Trade.status == "pending",
    Trade.confirm_date == snapshot_date,
    # 排除跨天转移（由 confirm_cash_transfer 专属端点处理）
    Trade.transfer_group.is_(None) | (Trade.product_code != "CASH"),
).all()

for trade in pending_trades:
    try:
        # 复用 confirm_trade 的净值获取逻辑
        # 注意：需区分 confirm_trade（按 confirm_days + 取净值）与 confirm_cash_transfer
        # 此处只处理非 CASH 转移的普通调仓 trade
        _auto_confirm_trade(db, trade)
    except Exception as e:
        logger.warning(f"Trade auto-confirm failed: {trade.id}, {e}")

# Event 自动确认（ex_date == snapshot_date 的 pending events）
pending_events = db.query(ShareChangeEvent).filter(
    ShareChangeEvent.portfolio_code == portfolio_code,
    ShareChangeEvent.status == "pending",
    ShareChangeEvent.ex_date == snapshot_date,
).all()

for event in pending_events:
    try:
        _auto_confirm_event(db, event)
    except Exception as e:
        logger.warning(f"Event auto-confirm failed: {event.id}, {e}")
```

注意：跨天转移的两腿（transfer_group 非空且 product_code=CASH）的自动确认由 `confirm_cash_transfer` 逻辑处理，不在 `auto_confirm_after_snapshot` 中。或者，可以在 regen 中也处理跨天转移（检查 TRANSFER_NOT_READY 条件满足后同时确认两腿）。

### Task 15: 录入层约束

**文件:**
- `backend/app/routers/trades.py` — `create_trade`
- `backend/app/routers/subscriptions.py` — `create_subscription`
- `backend/app/routers/cash_transfers.py` — `create_cash_transfer`
- `backend/app/routers/share_change_events.py` — `create_share_change_event`

约束清单：
- (a) 按类型拦截应用日 <= D（D = 最新快照日）：Trade `trade_date > D`，Subscription `apply_date > D`，ShareChangeEvent `ex_date > D`
- (b) 日期字段非空校验（规范 1，Trade 的 confirm_date 已在创建时自动设定）
- (c) ShareChangeEvent `ex_date == entitlement_date` 拒绝创建
- (d) ShareChangeEvent `ex_date >= entitlement_date` 约束（除息日不早于登记日）
- (e) ShareChangeEvent `ex_date` 和 `entitlement_date` 均须为交易日（当前仅校验 `entitlement_date`，补 `ex_date`）
- (f) ShareChangeEvent cash_dividend / forced_adjustment(cash_change!=0) 的 `platform_code` 必填
- (g) 禁止 `create_position` / `update_position` / `delete_position` 直接操作 `portfolio_position` 表（移除或加权限拒绝）

### Task 16: 通用删快照入口

**文件:** `backend/app/routers/snapshots.py`

新增端点或复用现有 `DELETE /{portfolio_code}/{snapshot_date}`：
- 提供"删 D-N 之后全部快照"的批量入口
- 复用 `_delete_existing_snapshots` + 级联回退（Subscription CASH trade 物理删除 + Event 退 pending）

### Task 17: Trade.transfer_group 唯一索引

**直接在数据库 schema 中添加（重置数据库时生效）：**
```sql
CREATE UNIQUE INDEX idx_trade_transfer_group_unique 
ON trade(transfer_group, product_code, trade_type) 
WHERE transfer_group IS NOT NULL;
```

注意：MySQL 不支持 partial index，改用普通唯一索引 + 应用层保证 transfer_group 为空时不冲突（NULL 值在 MySQL 唯一索引中不参与唯一性检查）。

---

## P2 — 手动市值层

### Task 18: manual_market_value 表

**新增模型:** `backend/app/models/manual_market_value.py`

```python
class ManualMarketValue(Base):
    __tablename__ = "manual_market_value"
    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_code = Column(String(20), ForeignKey("portfolio.code"), nullable=False)
    platform_code = Column(String(20), ForeignKey("platform.code"), nullable=False)
    product_code = Column(String(10), nullable=False)
    date = Column(Date, nullable=False)
    market_value = Column(Numeric(15, 4), nullable=False)
    computed_value = Column(Numeric(15, 4))  # 隐式计算值（审计）
    created_by = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('portfolio_code', 'platform_code', 'product_code', 'date', name='uq_manual_market_value'),
    )
```

### Task 19: update_cash_position 改道写 manual_market_value

**文件:** `backend/app/routers/positions.py`
**函数:** `update_cash_position`（line 349-439）

改为 upsert `manual_market_value` 表，不再直接写 `portfolio_position`。
写入后提示用户重新生成快照（非强制）。

### Task 20: get_cash_value + recalculate_snapshots 感知

**文件:** `backend/app/services/snapshot_service.py`

新增函数：
```python
def get_cash_value(db, portfolio_code, platform_code, target_date):
    v = compute_cash_balance(db, portfolio_code, platform_code, target_date)
    manual = db.query(ManualMarketValue).filter(
        ManualMarketValue.portfolio_code == portfolio_code,
        ManualMarketValue.platform_code == platform_code,
        ManualMarketValue.product_code == "CASH",
        ManualMarketValue.date == target_date,
    ).first()
    if manual:
        v = Decimal(str(manual.market_value))  # 绝对替换
    return v
```

`_generate_portfolio_position` 的 CASH 持仓使用 `get_cash_value`（Task 10 已包含）。

---

## 验收清单

### 闸门与 regen
- [ ] `_check_pending_transactions` Trade 分支为 `confirm_date <= target_date`
- [ ] Subscription 分支未动（`apply_date < target_date`）
- [ ] QDII T+2 不误杀 D+1 快照
- [ ] `auto_confirm_after_snapshot` 扩展到 Trade + Event
- [ ] 含合理在途 Trade + pending 事件的组合 regen 不卡死

### 现金显式化
- [ ] 申购确认后 trade 表有 CASH buy，`transfer_group = "sub_{id}"`
- [ ] 赎回确认后 trade 表有 CASH sell
- [ ] 基金买入创建后有配对 CASH sell，同 transfer_group，amount = actual_amount
- [ ] confirm/unconfirm/cancel 基金腿 → CASH 腿同步（原子翻转）
- [ ] `compute_cash_balance` = SUM(confirmed CASH trades) + SUM(event cash_change)
- [ ] 旧 `calculate_available_cash`（3 份）已删除，所有调用点改道
- [ ] `_generate_portfolio_position` 无 CASH 特殊处理分支
- [ ] 快照 CASH = `get_cash_value` 落库值
- [ ] 实时预览 = `compute_cash_balance(today)`，不读 manual_market_value

### 跨天转移
- [ ] cross_day=True 时两腿均 pending（对称状态）
- [ ] 两腿 confirm_date 均为 next_trading_day(transfer_date)
- [ ] `confirm_cash_transfer` 同时确认两腿
- [ ] TRANSFER_NOT_READY 守卫保留
- [ ] D 日 NAV 不因在途转移虚跌
- [ ] 在途期间可用现金 A 减少（pending CASH sell 预留）

### 份额变动事件
- [ ] `event_date` 全局改为 `ex_date`（模型、schema、router、快照服务）
- [ ] `_generate_portfolio_position` 对 `ex_date <= target` 的 confirmed 事件按公式应用基金份额
- [ ] 事件 cash_change 由 `compute_cash_balance` 读取，不直接改 CASH 持仓
- [ ] `entitlement_shares` / `shares_before` / `shares_change` / `shares_after` / `cash_change` 确认时自动回写
- [ ] 删快照触发 `_cascade_unconfirm_share_change_events`（双日期 OR 回退）
- [ ] pending 事件拦截快照生成（非仅 warning）
- [ ] `ex_date == entitlement_date` 在录入时拒绝
- [ ] 多事件同日按 `entitlement_date` 升序应用
- [ ] ShareChangeEvent 有 `platform_code` 字段，cash_dividend 时必填

### 快照表保护
- [ ] `create_position` / `update_position` / `delete_position` 禁止直接操作
- [ ] `update_cash_position` 写 `manual_market_value`，不直接改 `portfolio_position`

### manual_market_value
- [ ] `manual_market_value` 表存在，含审计字段
- [ ] `(portfolio, platform, product, date)` 唯一约束
- [ ] 写入后提示用户 regen（非强制）

### 数据库
- [ ] `Trade.transfer_group` 唯一索引 `UNIQUE(transfer_group, product_code, trade_type)`
- [ ] `share_change_event.event_date` 改名 `ex_date`
- [ ] `share_change_event` 新增 `platform_code` 字段
- [ ] 新增 `manual_market_value` 表
