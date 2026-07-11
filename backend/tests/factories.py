# ============================================================================
# InvestRing 测试数据工厂 (factories.py)
# ============================================================================
# 提供快速创建测试数据的辅助函数。
# 所有函数接收 db session 作为第一个参数，并在创建后自动 commit。
# ============================================================================

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    Investor, Portfolio, Product, Platform,
    AssetClassification, TradingCalendar, PriceRecord,
    PortfolioPosition, PortfolioValueSnapshot, InvestorHolding,
    Subscription, Trade, ShareChangeEvent,
)
from app.utils.security import get_password_hash


# ---------------------------------------------------------------------------
# 投资人
# ---------------------------------------------------------------------------

def create_investor(
    db: Session,
    code: str = "INV001",
    name: str = "测试投资人",
    role: str = "viewer",
    password: str = "test123",
) -> Investor:
    """创建投资人，如已存在则直接返回"""
    existing = db.query(Investor).filter(Investor.code == code).first()
    if existing:
        return existing
    investor = Investor(
        code=code, name=name, role=role,
        password_hash=get_password_hash(password),
    )
    db.add(investor)
    db.commit()
    db.refresh(investor)
    return investor


# ---------------------------------------------------------------------------
# 组合
# ---------------------------------------------------------------------------

def create_portfolio(
    db: Session,
    code: str = "PORT001",
    name: str = "测试组合",
    status: str = "draft",
) -> Portfolio:
    """创建组合，如已存在则直接返回"""
    existing = db.query(Portfolio).filter(Portfolio.code == code).first()
    if existing:
        return existing
    portfolio = Portfolio(code=code, name=name, description="测试", status=status)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


# ---------------------------------------------------------------------------
# 平台
# ---------------------------------------------------------------------------

def create_platform(
    db: Session,
    code: str = "PLAT001",
    name: str = "测试平台",
    platform_type: str = "第三方平台",
) -> Platform:
    """创建平台，如已存在则直接返回"""
    existing = db.query(Platform).filter(Platform.code == code).first()
    if existing:
        return existing
    platform = Platform(code=code, name=name, platform_type=platform_type)
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return platform


# ---------------------------------------------------------------------------
# 资产分类
# ---------------------------------------------------------------------------

def create_asset_classification(
    db: Session,
    code: str = "TEST_ASSET",
    asset_type: str = "股票",
    asset_category: str = "国内股票",
    asset_subcat: str = "大盘",
) -> AssetClassification:
    existing = db.query(AssetClassification).filter(AssetClassification.code == code).first()
    if existing:
        return existing
    ac = AssetClassification(
        code=code, asset_type=asset_type,
        asset_category=asset_category, asset_subcat=asset_subcat,
    )
    db.add(ac)
    db.commit()
    db.refresh(ac)
    return ac


# ---------------------------------------------------------------------------
# 产品
# ---------------------------------------------------------------------------

def create_product(
    db: Session,
    code: str = "000001.OF",
    market: str = "CN_OTC",
    name: str = "测试基金",
    product_type: str = "OEF",
    asset_class_code: str = "STOCK_CN_LARGE",
    confirm_days: int = 1,
    is_qdii: bool = False,
) -> Product:
    """创建产品，如已存在则直接返回"""
    existing = db.query(Product).filter(
        Product.code == code, Product.market == market
    ).first()
    if existing:
        return existing

    # 确保资产分类存在
    if not db.query(AssetClassification).filter(AssetClassification.code == asset_class_code).first():
        create_asset_classification(db, code=asset_class_code)

    product = Product(
        code=code, market=market, name=name,
        product_type=product_type, asset_class_code=asset_class_code,
        confirm_days=confirm_days, is_qdii=is_qdii,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


# ---------------------------------------------------------------------------
# 价格记录
# ---------------------------------------------------------------------------

def create_price_record(
    db: Session,
    product_code: str,
    market: str,
    record_date: date,
    unit_price: float,
) -> PriceRecord:
    """创建价格记录"""
    record = PriceRecord(
        product_code=product_code, market=market,
        date=record_date, unit_price=Decimal(str(unit_price)),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# 交易日历
# ---------------------------------------------------------------------------

def ensure_trading_day(db: Session, d: date, is_open: bool = True) -> TradingCalendar:
    """确保指定日期在交易日历中存在"""
    existing = db.query(TradingCalendar).filter(TradingCalendar.date == d).first()
    if existing:
        return existing
    cal = TradingCalendar(date=d, is_open=is_open, exchange="SSE")
    db.add(cal)
    db.commit()
    db.refresh(cal)
    return cal


# ---------------------------------------------------------------------------
# 申购 / 赎回
# ---------------------------------------------------------------------------

def create_subscription(
    db: Session,
    portfolio_code: str,
    investor_code: str,
    sub_type: str = "subscribe",
    amount: float = 10000.0,
    shares: Optional[float] = None,
    unit_price: Optional[float] = None,
    apply_date: date = date(2025, 1, 6),
    status: str = "pending",
) -> Subscription:
    """创建申购/赎回记录"""
    sub = Subscription(
        portfolio_code=portfolio_code,
        investor_code=investor_code,
        sub_type=sub_type,
        amount=Decimal(str(amount)),
        shares=Decimal(str(shares)) if shares else None,
        unit_price=Decimal(str(unit_price)) if unit_price else None,
        apply_date=apply_date,
        status=status,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# ---------------------------------------------------------------------------
# 调仓交易
# ---------------------------------------------------------------------------

def create_trade(
    db: Session,
    portfolio_code: str,
    product_code: str,
    market: str,
    trade_type: str = "buy",
    amount: float = 5000.0,
    shares: Optional[float] = None,
    price: Optional[float] = 1.5,
    fee: float = 0.0,
    platform_code: str = "MYCF",
    trade_date: date = date(2025, 1, 6),
    status: str = "pending",
) -> Trade:
    """创建调仓交易记录"""
    trade = Trade(
        portfolio_code=portfolio_code,
        platform_code=platform_code,
        product_code=product_code,
        market=market,
        trade_type=trade_type,
        amount=Decimal(str(amount)),
        shares=Decimal(str(shares)) if shares else None,
        price=Decimal(str(price)) if price else None,
        fee=Decimal(str(fee)),
        trade_date=trade_date,
        status=status,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


# ---------------------------------------------------------------------------
# 持仓快照（PortfolioPosition）
# ---------------------------------------------------------------------------

def create_position_snapshot(
    db: Session,
    portfolio_code: str,
    product_code: str,
    market: str,
    snapshot_date: date,
    shares: Optional[float] = None,
    amount: Optional[float] = None,
    unit_price: Optional[float] = 1.5,
    cost_price: Optional[float] = 1.5,
    market_value: float = 0.0,
    platform_code: Optional[str] = None,
) -> PortfolioPosition:
    """创建持仓快照（注意：shares 和 amount 二选一）"""
    pos = PortfolioPosition(
        portfolio_code=portfolio_code,
        platform_code=platform_code,
        product_code=product_code,
        market=market,
        shares=Decimal(str(shares)) if shares is not None else None,
        amount=Decimal(str(amount)) if amount is not None else None,
        unit_price=Decimal(str(unit_price)) if unit_price else None,
        cost_price=Decimal(str(cost_price)) if cost_price else None,
        market_value=Decimal(str(market_value)),
        snapshot_date=snapshot_date,
    )
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return pos


# ---------------------------------------------------------------------------
# 组合市值快照（PortfolioValueSnapshot）
# ---------------------------------------------------------------------------

def create_value_snapshot(
    db: Session,
    portfolio_code: str,
    snapshot_date: date,
    total_value: float,
    total_shares: float,
    unit_price: float,
) -> PortfolioValueSnapshot:
    """创建组合市值快照"""
    snap = PortfolioValueSnapshot(
        portfolio_code=portfolio_code,
        snapshot_date=snapshot_date,
        total_value=Decimal(str(total_value)),
        total_shares=Decimal(str(total_shares)),
        unit_price=Decimal(str(unit_price)),
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


# ---------------------------------------------------------------------------
# 投资人持仓快照（InvestorHolding）
# ---------------------------------------------------------------------------

def create_investor_holding(
    db: Session,
    portfolio_code: str,
    investor_code: str,
    snapshot_date: date,
    shares: float,
    cost_per_share: Optional[float] = 1.0,
) -> InvestorHolding:
    """创建投资人份额快照"""
    holding = InvestorHolding(
        portfolio_code=portfolio_code,
        investor_code=investor_code,
        snapshot_date=snapshot_date,
        shares=Decimal(str(shares)),
        cost_per_share=Decimal(str(cost_per_share)) if cost_per_share else None,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


# ---------------------------------------------------------------------------
# 份额变动事件（ShareChangeEvent）
# ---------------------------------------------------------------------------

def create_share_change_event(
    db: Session,
    portfolio_code: str,
    product_code: str,
    market: str,
    event_type: str = "cash_dividend",
    ex_date: date = date(2025, 1, 10),
    entitlement_date: date = date(2025, 1, 9),
    event_source: str = "manual",
    status: str = "pending",
    platform_code: Optional[str] = None,  # 平台级事件必传，基金级事件不传
    **kwargs,
) -> ShareChangeEvent:
    """创建份额变动事件。
    平台级事件（cash_dividend/reinvest_dividend/forced_adjustment）须传 platform_code。
    基金级事件（share_split/share_merge/bonus_share）不传 platform_code。
    """
    event = ShareChangeEvent(
        portfolio_code=portfolio_code,
        product_code=product_code,
        market=market,
        event_type=event_type,
        ex_date=ex_date,
        entitlement_date=entitlement_date,
        event_source=event_source,
        status=status,
        platform_code=platform_code,
        **kwargs,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
