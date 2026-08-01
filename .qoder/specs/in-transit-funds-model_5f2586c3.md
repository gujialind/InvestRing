# Issue #93: 在途资金模型实现方案（最终版）

## 设计决策总结

**核心问题**：`sync_transfer_group` 强制配对腿共享 `confirm_date`，导致买入扣款延迟体现、卖出到账无法表达，产生负现金和市值缺口。

**解决方案**：
1. 解耦配对腿 `confirm_date`（CASH 腿独立确认日：买入=T日扣款，卖出=确认日或实际到账日）
2. 在 `portfolio_position` 中以独立行存储在途资金：`product_code="IN_TRANSIT_BUY"` 或 `"IN_TRANSIT_SELL"`, `market=""`（两条种子产品记录），`asset_type="cash"`，`cash_amount` 始终正数。通过 product_code 区分方向（与 CASH 一致的 market="" 模式）
3. 快照生成时通过 trade 表绝对计算各平台各方向的在途金额（含基金调仓配对 + 现金转移两类场景），仅在有在途时生成对应行
4. 现金跨平台转移（cross_day=True）调整为：转出方当日确认，在途资金自然记录在转入方（复用同一个 in-transit 检测机制）

**为什么选择独立行方案**：
- **存储高效**：仅在有在途时才生成行，交易不频繁时无多余数据
- **语义清晰**：在途资金作为独立持仓类目，持仓分析中天然可见为单独行项
- **代码复用**：落库路径与 CASH 完全一致（`cash_amount` 字段、`asset_type="cash"`、同分支的 market_value/total_value 计算），下游读取零改动
- **FK 约束**：迁移中扩展 product_code String(10)→(20)（全部 8 处），创建两条种子产品记录（`IN_TRANSIT_BUY` 和 `IN_TRANSIT_SELL`），与 CASH 同等虚拟产品
- **平台追踪**：自然具备 `platform_code` 维度，支持对账

---

## 数据模型设计

### IN_TRANSIT 行在 portfolio_position 中的表达

| 字段 | 买入在途行 | 卖出在途行 |
|------|-----------|----------|
| product_code | "IN_TRANSIT_BUY" | "IN_TRANSIT_SELL" |
| market | "" | "" |
| platform_code | 扣款平台 | 到账平台 |
| shares | NULL | NULL |
| cash_amount | 在途金额（**正数**） | 在途金额（**正数**） |
| market_value | = cash_amount | = cash_amount |
| asset_type | "cash" | "cash" |
| frozen_shares | 0 | 0 |
| frozen_amount | 0 | 0 |
| snapshot_date | 快照日期 | 快照日期 |

- 两条 product 种子记录：`(IN_TRANSIT_BUY, "")` 和 `(IN_TRANSIT_SELL, "")`，与 CASH 同为虚拟产品
- 唯一约束 `(portfolio_code, "IN_TRANSIT_BUY"/"IN_TRANSIT_SELL", "", platform_code, snapshot_date)` 天然隔离
- CHECK 约束 `shares XOR cash_amount` 满足（shares=NULL, cash_amount=NOT NULL）
- **仅在有在途时生成行**；无在途的快照日不生成该行
- **买入和卖出在途均为正数**（两者都是组合资产），通过 market 字段区分方向

### 业务语义

- **买入在途 IN_TRANSIT_BUY**（cash_amount > 0）：已扣款但份额未确认。资金已从平台划出（CASH sell 已确认），等待基金份额入账（fund buy confirm_date > 快照日）。代表组合已支付的待收份额。来源：基金买入调仓、现金转移转出方
- **卖出在途 IN_TRANSIT_SELL**（cash_amount > 0）：已卖出但到账未确认。基金份额已清除（fund sell 已确认），等待现金到账（CASH buy confirm_date > 快照日）。代表组合即将收回的待收现金。来源：基金卖出调仓
- 两者都是组合资产，cash_amount 均为正数

### 总资产公式

```
total_value = Σ(fund market_value) + Σ(CASH cash_amount) + Σ(IN_TRANSIT cash_amount)
```

现有 `_generate_portfolio_value_snapshot` 代码已覆盖（`elif pos.cash_amount is not None: total_value += ...`）：
- IN_TRANSIT 行的 `cash_amount IS NOT NULL` → 自动纳入总市值 ✓
- **零代码改动**

---

## 关键改动

### Phase 1: 数据模型与迁移

#### 1.1 扩展 product_code 字段 String(10) → String(20)

**迁移文件**: `backend/alembic/versions/0006_product_code_extend_and_in_transit.py`

将以下 8 个字段从 `String(10)` 扩展到 `String(20)`（支持 IN_TRANSIT_BUY / IN_TRANSIT_SELL 命名）：

| 文件 | 字段 | 说明 |
|------|------|------|
| `models/product.py` | `code` | 主键 |
| `models/portfolio_position.py` | `product_code` | FK → product |
| `models/trade.py` | `product_code` | FK → product |
| `models/price_record.py` | `product_code` | FK → product |
| `models/manual_market_value.py` | `product_code` | FK → product |
| `models/nav_sync_detail.py` | `product_code` | FK → product |
| `models/share_change_event.py` | `product_code` | FK → product |
| `models/share_change_event.py` | `cash_product_code` | 可空 FK |

```python
# Alembic 迁移
for table in ['product', 'portfolio_position', 'trade', 'price_record',
              'manual_market_value', 'nav_sync_detail', 'share_change_event']:
    columns = ['code'] if table == 'product' else ['product_code']
    if table == 'share_change_event':
        columns.append('cash_product_code')
    for col in columns:
        op.alter_column(table, col, type_=sa.String(20), existing_type=sa.String(10))
```

**MySQL DDL**: `ALTER TABLE xxx MODIFY product_code VARCHAR(20)` — 无数据迁移，仅元数据变更。

#### 1.2 创建种子产品记录

```python
# 创建 IN_TRANSIT 虚拟产品（两条种子记录）
op.execute("""
    INSERT INTO product (code, market, name, asset_class_code, confirm_days, is_active)
    VALUES 
        ('IN_TRANSIT_BUY', '', '买入在途资金', NULL, 0, 1),
        ('IN_TRANSIT_SELL', '', '卖出在途资金', NULL, 0, 1)
    ON DUPLICATE KEY UPDATE name=VALUES(name)
""")
```

- 与 CASH 产品同等地位，一次性种子数据
- `confirm_days=0`、`is_active=1`、无 `asset_class_code`（非投资品）
- `market=""` 与 CASH 一致，通过 product_code 本身区分方向

#### 1.3 portfolio_value_snapshot 新增汇总列（可选增强）

```python
# 在 portfolio_value_snapshot 新增 in_transit_total 信息列
op.add_column('portfolio_value_snapshot', 
    sa.Column('in_transit_total', sa.Numeric(15, 4), server_default='0'))
```

供仪表盘快速展示，不影响核心逻辑。

#### 1.4 portfolio_position 模型无结构变更

现有模型无需任何列/约束修改。IN_TRANSIT 行使用现有字段即可。

---

### Phase 2: 配对腿确认日解耦

**文件**: `backend/app/services/trade_service.py`

#### 2.1 修改 `attach_paired_cash_leg()`（L61-98）

新增参数 `cash_confirm_date: Optional[date] = None`：

```python
def attach_paired_cash_leg(
    db, fund_trade, cash_amount, confirm_date,
    status="pending",
    cash_platform_code=None,
    cash_confirm_date=None,  # #93: CASH 腿独立确认日
) -> Trade:
    group = f"rebal_{uuid.uuid4().hex[:12]}"
    fund_trade.transfer_group = group
    
    # #93: CASH 腿确认日独立于基金腿
    if cash_confirm_date is None:
        if fund_trade.trade_type == "buy":
            # 买入扣款：T日即扣
            effective_cash_confirm = fund_trade.trade_date
        else:
            # 卖出到账：默认与基金确认日一致（无延迟）
            effective_cash_confirm = confirm_date
    else:
        effective_cash_confirm = cash_confirm_date
    
    cash_trade = Trade(
        portfolio_code=fund_trade.portfolio_code,
        platform_code=cash_platform_code or fund_trade.platform_code,
        product_code="CASH",
        market="",
        trade_type="sell" if fund_trade.trade_type == "buy" else "buy",
        shares=None,
        amount=cash_amount,
        price=Decimal("1"),
        fee=Decimal("0"),
        actual_amount=cash_amount,
        trade_date=fund_trade.trade_date,
        confirm_date=effective_cash_confirm,  # 独立确认日
        status=status,
        transfer_group=group,
    )
    db.add(cash_trade)
    return cash_trade
```

#### 2.2 修改 `sync_transfer_group()`（L101-154）

**移除 confirm_date 同步**（L133-134），保留 status/trade_date/amount 同步：

```python
def sync_transfer_group(db, trade, target_status, confirm_date=None):
    ...
    for paired_trade in paired:
        paired_trade.trade_date = trade.trade_date          # 保持：组内不变量
        paired_trade.status = target_status                 # 保持：状态同步
        # ❌ 移除: if confirm_date is not None: paired_trade.confirm_date = confirm_date
        # #93: confirm_date 不再同步。各腿保持创建时设定的独立确认日。
        
        # unconfirm（pending）时：CASH 腿回退到创建时的默认确认日
        if target_status == "pending" and paired_trade.product_code == "CASH":
            if paired_trade.trade_type == "sell":
                # 买入的 CASH sell：回退到 trade_date（T日扣款）
                paired_trade.confirm_date = paired_trade.trade_date
            else:
                # 卖出的 CASH buy：回退到基金确认日（默认一致，无延迟）
                fund_leg = next((p for p in paired if p.product_code != "CASH"), None)
                if fund_leg and fund_leg.confirm_date:
                    paired_trade.confirm_date = fund_leg.confirm_date
        
        # 金额镜像保持不变
        if mirror_amount is not None and paired_trade.product_code == "CASH":
            paired_trade.amount = mirror_amount
            paired_trade.actual_amount = mirror_amount
```

**影响范围**：confirm/cancel/unconfirm/PUT 四处调用。仅移除 confirm_date 传播，其余行为不变。申赎和现金转移有独立 confirm 逻辑，不经此函数同步 confirm_date。

#### 2.3 Trade Router/CLI 支持传入到账日

**文件**: `backend/app/routers/trades.py`, `backend/cli/commands/trade.py`, `ir-cli/ir_cli/commands/trade.py`

- REST: `POST /api/trades` 新增可选字段 `cash_confirm_date: Optional[date]`（卖出时传入实际到账日，缺省=确认日）
- CLI: `ir trade create sell` 新增 `--cash-confirm-date`（到账日，可选）
- 买入方向无需额外参数（CASH 默认 T 日确认）
- 卖出方向无需额外参数（CASH 默认与确认日一致），仅当到账日晚于确认日时才传入

---

### Phase 2.5: 现金跨平台转移调整

**文件**: `backend/app/services/cash_transfer_service.py`

#### 2.5.1 修改 `create_cash_transfer()` 的 cross_day 逻辑（L106-112）

转出方当日确认，转入方 pending：

```python
if not cross_day:
    # 当天完成：两腿立即 confirm（不变）
    sell_trade.status = "confirmed"
    sell_trade.confirm_date = transfer_date
    buy_trade.status = "confirmed"
    buy_trade.confirm_date = transfer_date
else:
    # #93: 跨天到账——转出方当日确认，转入方 pending
    next_trading_day = get_next_trading_day(db, transfer_date, days=1)
    sell_trade.status = "confirmed"  # 转出方当日确认（资金已划出）
    sell_trade.confirm_date = transfer_date
    buy_trade.status = "pending"     # 转入方 pending（待到账）
    buy_trade.confirm_date = next_trading_day
```

**效果**：cross_day 时，T 日快照自动检测到 transfer_group 内一腿 confirmed (sell)、一腿 pending (buy) → `_compute_in_transit_amounts` 查询 ② 捕获 → 生成 IN_TRANSIT_BUY 行在转入方平台。

#### 2.5.2 修改 `confirm_cash_transfer()` 仅确认转入腿（L130-166）

```python
def confirm_cash_transfer(db, *, portfolio_code, transfer_group):
    # 仅查询 pending 的转入腿（sell 已在创建时确认）
    pending_buy = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.transfer_group == transfer_group,
        Trade.product_code == "CASH",
        Trade.trade_type == "buy",
        Trade.status == "pending",
    ).first()
    
    if not pending_buy:
        raise NotFoundError(...)
    
    confirm_date = pending_buy.confirm_date or get_next_trading_day(db, pending_buy.trade_date, days=1)
    if confirm_date > date.today():
        raise BusinessError("TRANSFER_NOT_READY", ...)
    
    pending_buy.status = "confirmed"
    pending_buy.confirm_date = confirm_date
    
    return {...}
```

#### 2.5.3 `list_cash_transfers()` 调整状态展示

跨天转移的状态从“两腿均 pending”变为“sell confirmed + buy pending”，列表展示逻辑需相应更新（cross_day 判断改为基于 buy 腿状态）。

---

### Phase 3: 快照生成逻辑

**文件**: `backend/app/services/snapshot_service.py`

#### 3.1 新增 `_compute_in_transit_amounts()` 函数

```python
def _compute_in_transit_amounts(
    db: Session, portfolio_code: str, snapshot_date: date
) -> Dict[Tuple[str, str], Decimal]:
    """绝对计算各平台各方向的在途资金金额
    
    Returns: dict[(platform_code, direction)] = amount（正数）
        direction: "buy" | "sell"
    
    规则：
    ① 基金调仓：同 transfer_group 内一腿已确认(confirm_date<=D)
       另一腿虽 confirmed 但 confirm_date>D
    ② 现金转移（cross_day）：CASH sell 已确认，CASH buy 未确认
    买入和卖出在途均为正数。
    """
    from sqlalchemy.orm import aliased
    
    result: Dict[Tuple[str, str], Decimal] = {}
    CashLeg = aliased(Trade)
    FundLeg = aliased(Trade)
    
    # --- ① 基金调仓在途 ---
    
    # 买入在途: CASH sell confirmed, fund buy not-in-snapshot
    buy_transit_fund = db.query(
        CashLeg.platform_code,
        func.sum(CashLeg.amount)
    ).join(
        FundLeg,
        and_(
            CashLeg.transfer_group == FundLeg.transfer_group,
            CashLeg.id != FundLeg.id,
            FundLeg.product_code != "CASH"
        )
    ).filter(
        CashLeg.portfolio_code == portfolio_code,
        CashLeg.product_code == "CASH",
        CashLeg.trade_type == "sell",
        CashLeg.status == "confirmed",
        CashLeg.confirm_date <= snapshot_date,
        FundLeg.status == "confirmed",
        FundLeg.confirm_date > snapshot_date,
    ).group_by(CashLeg.platform_code).all()
    
    for platform_code, amount in buy_transit_fund:
        if amount and amount > 0:
            result[(platform_code, "buy")] = Decimal(str(amount))
    
    # 卖出在途: fund sell confirmed, CASH buy not-in-snapshot
    sell_transit_fund = db.query(
        CashLeg.platform_code,
        func.sum(CashLeg.amount)
    ).join(
        FundLeg,
        and_(
            CashLeg.transfer_group == FundLeg.transfer_group,
            CashLeg.id != FundLeg.id,
            FundLeg.product_code != "CASH"
        )
    ).filter(
        CashLeg.portfolio_code == portfolio_code,
        CashLeg.product_code == "CASH",
        CashLeg.trade_type == "buy",
        CashLeg.status == "confirmed",
        CashLeg.confirm_date > snapshot_date,
        FundLeg.status == "confirmed",
        FundLeg.confirm_date <= snapshot_date,
    ).group_by(CashLeg.platform_code).all()
    
    for platform_code, amount in sell_transit_fund:
        if amount and amount > 0:
            result[(platform_code, "sell")] = Decimal(str(amount))
    
    # --- ② 现金转移在途（cross_day：CASH sell 已确认，CASH buy pending）---
    CashSell = aliased(Trade)
    CashBuy = aliased(Trade)
    
    cash_transfer_transit = db.query(
        CashBuy.platform_code,
        func.sum(CashBuy.amount)
    ).join(
        CashSell,
        and_(
            CashBuy.transfer_group == CashSell.transfer_group,
            CashBuy.id != CashSell.id,
        )
    ).filter(
        CashBuy.portfolio_code == portfolio_code,
        CashBuy.product_code == "CASH",
        CashBuy.trade_type == "buy",
        CashSell.product_code == "CASH",
        CashSell.trade_type == "sell",
        CashSell.status == "confirmed",
        CashSell.confirm_date <= snapshot_date,
        CashBuy.status != "confirmed",  # pending 或 confirm_date > snapshot_date
    ).group_by(CashBuy.platform_code).all()
    
    for platform_code, amount in cash_transfer_transit:
        if amount and amount > 0:
            result[(platform_code, "buy")] = (
                result.get((platform_code, "buy"), Decimal("0")) + Decimal(str(amount))
            )
    
    return result
```

**性能**：3 次 JOIN + GROUP BY 查询，transfer_group 有索引，数据量极小。

#### 3.2 修改 `_generate_portfolio_position()`

**三处改动**：

**(a) 加载前一日快照时跳过 IN_TRANSIT 行**（约 L707 位置）：

```python
for pos in prev_positions:
    # #93: IN_TRANSIT 行不继承（每日独立计算）
    if pos.product_code in ("IN_TRANSIT_BUY", "IN_TRANSIT_SELL"):
        continue
    if pos.product_code == "CASH":
        ...  # 现有 CASH 逻辑
```

**(b) 确认交易处理后，计算并生成 IN_TRANSIT 行**（约 L845 之后、构建对象之前）：

```python
    # #93: 计算在途资金，生成独立 IN_TRANSIT_BUY/IN_TRANSIT_SELL 行
    in_transit = _compute_in_transit_amounts(db, portfolio_code, target_date)
    for (platform_code, direction), amount in in_transit.items():
        product_code = "IN_TRANSIT_BUY" if direction == "buy" else "IN_TRANSIT_SELL"
        key = (product_code, "", platform_code)
        positions[key] = {
            "shares": None,
            "cash_amount": amount,  # 始终正数
            "cost_price": None,
            "asset_type": "cash",  # 在途资金本质是现金
        }
```

**(c) 构建 PortfolioPosition 对象时处理 IN_TRANSIT**（约 L860-924）：

由于 IN_TRANSIT 的 `asset_type="cash"`，现有代码的 `is_cash` 判断自动覆盖：

```python
    IN_TRANSIT_CODES = {"IN_TRANSIT_BUY", "IN_TRANSIT_SELL"}
    
    for (product_code, market, platform_code), pos_data in positions.items():
        is_cash = pos_data.get("asset_type") == "cash"  # CASH 和 IN_TRANSIT 都是 True
        is_in_transit = product_code in IN_TRANSIT_CODES
        
        # 跳过零持仓（现金/在途不跳过）— 现有逻辑已正确
        if not is_cash:
            if pos_data["shares"] is not None and pos_data["shares"] <= 0:
                continue
        
        # market_value = cash_amount — 现有逻辑已正确
        if pos_data["asset_type"] == "cash":
            market_value = pos_data["cash_amount"]
        
        # frozen 计算：仅 CASH 需要，IN_TRANSIT 跳过
        if product_code == "CASH":
            frozen_amount = _calculate_frozen_amount(...)
        else:
            frozen_amount = Decimal("0")
        
        if not is_in_transit:
            frozen_shares = _calculate_frozen_shares(...)
        else:
            frozen_shares = Decimal("0")
        
        position = PortfolioPosition(...)
        result_positions.append(position)
```

**核心变化极少**：仅在 frozen 计算处增加 product_code 判断跳过 IN_TRANSIT 的无效查询。market_value 和零持仓跳过逻辑零改动。

#### 3.3 `_generate_portfolio_value_snapshot()` — 无改动

现有代码 L964-968 已自动覆盖 IN_TRANSIT：
```python
elif pos.cash_amount is not None:
    total_value += Decimal(str(pos.cash_amount))
```

IN_TRANSIT 行的 `cash_amount IS NOT NULL` → 自动纳入 total_value。**零代码改动**。

可选增强：记录 `in_transit_total` 到 snapshot 表：
```python
IN_TRANSIT_CODES = {"IN_TRANSIT_BUY", "IN_TRANSIT_SELL"}
in_transit_total = sum(
    Decimal(str(pos.cash_amount)) for pos in positions 
    if pos.product_code in IN_TRANSIT_CODES and pos.cash_amount
)
snapshot.in_transit_total = float(in_transit_total) if in_transit_total else 0
```

---

### Phase 4: 现金计算逻辑验证

**文件**: `backend/app/services/position_service.py`

`calculate_available_cash()` **无需修改**。解耦后：
- 买入 CASH sell：confirm_date=T → 正确扣减可用现金
- 卖出 CASH buy：confirm_date=到账日 → 到账前不增加可用现金
- pending CASH sell 预留逻辑保持不变

`compute_cash_balance()` 仅读 confirmed CASH trades，不涉及 IN_TRANSIT，**无需修改**。

---

### Phase 5: API 与前端适配

#### 5.1 位置响应 Schema

**文件**: `backend/app/schemas/position.py`

无需新增字段。IN_TRANSIT 行作为普通 position 返回：
```json
{
  "product_code": "IN_TRANSIT_BUY",
  "market": "",
  "platform_code": "ZGYH",
  "cash_amount": 8003.30,
  "market_value": 8003.30,
  "asset_type": "cash",
  "frozen_shares": 0,
  "frozen_amount": 0,
  "snapshot_date": "2026-06-30"
}
```

前端可按 `product_code in ["IN_TRANSIT_BUY", "IN_TRANSIT_SELL"]` 筛选在途资金。

#### 5.2 前端持仓分析展示

Position 列表自然包含 IN_TRANSIT 行，按 product_code 分组显示：
- 基金持仓（product_code 为具体基金/股票代码）
- 现金（product_code: CASH）
- 买入在途（product_code: IN_TRANSIT_BUY）
- 卖出在途（product_code: IN_TRANSIT_SELL）

#### 5.3 CLI 支持

**文件**: `backend/cli/commands/trade.py`, `ir-cli/ir_cli/commands/trade.py`

- `ir trade create sell` 新增 `--cash-confirm-date`（到账日，可选，缺省=确认日）
- `ir position list` 天然显示 IN_TRANSIT 行（已有的输出逻辑适配）

---

### Phase 6: 测试与文档

#### 6.1 集成测试

**文件**: `backend/tests/integration/test_in_transit.py`（新）

核心场景：
1. T 日买入基金 → 验证 T 日快照有 IN_TRANSIT 行（cash_amount>0）、CASH 减少、基金未入账
2. T+1 日快照 → IN_TRANSIT 行消失、基金入账
3. T 日卖出基金 + 传入 --cash-confirm-date=T+3 → T+1 快照有 IN_TRANSIT/SELL 行（cash_amount>0）、基金清仓、现金未增
4. 到账日快照 → IN_TRANSIT 行消失、现金增加
5. T 日卖出基金（无 cash-confirm-date）→ T+1 快照无 IN_TRANSIT 行（到账日=确认日，无在途窗口）
6. 全程 total_value 无缺口

#### 6.2 现有测试适配

**文件**: `backend/tests/integration/test_trades.py`
- `TestUpdateDeletePairedSync` 类：修改断言，CASH 腿 confirm_date 不再随基金腿同步

#### 6.3 文档更新

**文件**: `AGENTS.md`
- §2.2: 新增“在途资金”来源行（product_code=IN_TRANSIT，与 CASH 同等虚拟产品）
- §3.3: 更新 sync_transfer_group 行为（不再同步 confirm_date）
- §2.4: total_value 公式补充 `+ Σ(IN_TRANSIT cash_amount)`
- §4.4: product 表新增 IN_TRANSIT 种子记录说明
- §5.3: 三层复用策略补充 IN_TRANSIT 与 CASH 的区分方式（product_code 而非 asset_type）

---

## 执行依赖关系

```
Phase 1 (基础): 迁移 + 种子数据
    1.1: product_code String(10)→(20) 扩展（8处）
    1.2: 创建 IN_TRANSIT_BUY / IN_TRANSIT_SELL 种子产品记录
    1.3: portfolio_value_snapshot 可选 in_transit_total 列
    
Phase 2 (解耦): Trade Service [depends on Phase 1]
    2.1: attach_paired_cash_leg 独立 confirm_date
    2.2: sync_transfer_group 移除 confirm_date 同步
    2.3: Router/CLI 支持 cash_confirm_date
    
Phase 2.5 (现金转移): Cash Transfer Service [depends on Phase 1]
    2.5.1: create_cash_transfer cross_day 转出方当日确认
    2.5.2: confirm_cash_transfer 仅确认转入腿
    2.5.3: list_cash_transfers 状态展示适配
    
Phase 3 (快照): Snapshot 逻辑 [depends on Phase 1 + 2 + 2.5]
    3.1: _compute_in_transit_amounts 新函数（含基金调仓 + 现金转移两类场景）
    3.2: _generate_portfolio_position 集成
    
Phase 4 (验证): 确认现有计算逻辑无需改动 [depends on Phase 2]

Phase 5 (展示): API/前端 [depends on Phase 3]
    
Phase 6 (收尾): 测试 + 文档 [depends on all]
```

---

## 验收断言（PORT001 06-30 ~ 07-21）

| 快照日期 | 断言 |
|---------|------|
| 06-30 | ZGYH CASH cash_amount=0; IN_TRANSIT_BUY @ ZGYH cash_amount=8003.30; 022925 无持仓行 |
| 07-01 | 022925.OF 入账; IN_TRANSIT_BUY 行不存在; 如卖出传入到账日 → IN_TRANSIT_SELL @ 到账平台 cash_amount=7537.44 |
| 到账日 | IN_TRANSIT_SELL 行不存在; CASH cash_amount 增加 |
| 全程 | 无负现金; total_value = cash + fund_mv + in_transit（无缺口） |

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| sync_transfer_group 改动影响现有流程 | 申赎 CASH 由 subscription_service 直接 confirmed 生成，不经 sync；现金转移有独立 confirm 逻辑。仅 rebal_ 组受影响 |
| 跨天现金转移行为变更 | 之前两腿 pending，现在 sell confirmed + buy pending。confirm_cash_transfer 仅确认 buy 腿。前端列表展示需适配 |
| 已有 369 张快照无 IN_TRANSIT 行 | 正确——历史快照从未有在途概念，无需补数据。新快照自然生成 |
| 在途查询性能 | 2 次 JOIN + GROUP BY，transfer_group 有索引，数据量极小 |
| 前端未适配 IN_TRANSIT 行 | IN_TRANSIT 的 asset_type="cash"，前端现有的现金展示逻辑不会报错；可通过 product_code 筛选 |
| IN_TRANSIT 行被误操作更新/删除 | 复用现有 ORM event（before_update/before_delete raise RuntimeError），与 CASH 行同等保护 |
| product 表 IN_TRANSIT 记录被误删 | FK RESTRICT 约束阻止删除（有 position 引用时） |

---

## 被否决的替代方案

| 方案 | 否决原因 |
|------|---------|
| CASH 行新增 in_transit_buy/sell 列 | 交易不频繁时每日每平台 CASH 行都有两个空值列（稀疏数据）；买卖方向挤入同一行不如独立行清晰 |
| IN_TRANSIT + market=BUY/SELL | market 字段与 CASH 的 market="" 不一致；通过 product_code 区分更统一 |
| 独立表 in_transit_position | 违背"position 表即持仓全貌"原则；持仓分析需 JOIN |
| 仅在 portfolio_value_snapshot 加列 | 丢失平台维度，无法对账 |
| position_type 列 + 修改唯一约束 | 需迁移回填 369 张快照的所有行（添加 position_type="settled"），风险高 |
