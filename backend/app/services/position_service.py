"""
持仓相关服务函数

从 routers 层提取的共享函数，供 CLI 和 router 共用。
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.portfolio_position import PortfolioPosition
from app.models.subscription import Subscription
from app.models.trade import Trade
from app.services.trading_utils import get_latest_snapshot_date


def calculate_available_cash(db: Session, portfolio_code: str) -> Decimal:
    """
    组合可用现金实时计算：
    最新快照现金
    + SUM(confirmed申购金额 WHERE 快照未生成)
    - SUM(confirmed赎回金额 WHERE 快照未生成)
    - SUM(pending买入金额)
    - SUM(confirmed买入金额 WHERE 快照未生成)
    + SUM(confirmed卖出金额 WHERE 快照未生成)
    """
    latest_date = get_latest_snapshot_date(db, portfolio_code)

    cash_position = (
        db.query(PortfolioPosition)
        .filter(
            PortfolioPosition.portfolio_code == portfolio_code,
            PortfolioPosition.product_code == "CASH",
        )
        .order_by(PortfolioPosition.snapshot_date.desc())
        .first()
    )
    cash = Decimal(cash_position.amount) if cash_position and cash_position.amount else Decimal("0")

    confirmed_subs = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.status == "confirmed",
            Subscription.sub_type == "subscribe",
        )
        .all()
    )
    for s in confirmed_subs:
        if latest_date is None or (s.confirm_date and s.confirm_date > latest_date):
            cash += Decimal(s.amount) if s.amount else Decimal("0")

    confirmed_redeems = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.status == "confirmed",
            Subscription.sub_type == "redeem",
        )
        .all()
    )
    for s in confirmed_redeems:
        if latest_date is None or (s.confirm_date and s.confirm_date > latest_date):
            cash -= Decimal(s.amount) if s.amount else Decimal("0")

    pending_buys = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.status == "pending",
            Trade.trade_type == "buy",
        )
        .all()
    )
    for t in pending_buys:
        cash -= Decimal(t.amount) if t.amount else Decimal("0")

    confirmed_buys = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.status == "confirmed",
            Trade.trade_type == "buy",
        )
        .all()
    )
    for t in confirmed_buys:
        if latest_date is None or (t.confirm_date and t.confirm_date > latest_date):
            cash -= Decimal(t.amount) if t.amount else Decimal("0")

    confirmed_sells = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.status == "confirmed",
            Trade.trade_type == "sell",
        )
        .all()
    )
    for t in confirmed_sells:
        if latest_date is None or (t.confirm_date and t.confirm_date > latest_date):
            cash += Decimal(t.amount) if t.amount else Decimal("0")

    return cash


def calculate_available_shares(
    db: Session, portfolio_code: str, product_code: str, market: Optional[str] = None
) -> Decimal:
    """
    基金可用份额实时计算：
    基金可用份额 = 最新快照份额
                - SUM(pending卖出份额)
                - SUM(confirmed卖出份额 WHERE 快照未生成)
    """
    latest_date = get_latest_snapshot_date(db, portfolio_code)

    query = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == portfolio_code,
        PortfolioPosition.product_code == product_code,
    )
    if market:
        query = query.filter(PortfolioPosition.market == market)
    latest_position = query.order_by(PortfolioPosition.snapshot_date.desc()).first()

    shares = Decimal(latest_position.shares) if latest_position and latest_position.shares else Decimal("0")

    pending_sells = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.product_code == product_code,
            Trade.status == "pending",
            Trade.trade_type == "sell",
        )
        .all()
    )
    for t in pending_sells:
        shares -= Decimal(t.shares) if t.shares else Decimal("0")

    confirmed_sells = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.product_code == product_code,
            Trade.status == "confirmed",
            Trade.trade_type == "sell",
        )
        .all()
    )
    for t in confirmed_sells:
        if latest_date is None or (t.confirm_date and t.confirm_date > latest_date):
            shares -= Decimal(t.shares) if t.shares else Decimal("0")

    return shares


def calculate_investor_available_shares(
    db: Session, portfolio_code: str, investor_code: str
) -> Decimal:
    """
    投资人可用份额实时计算：
    投资人可用份额 = 最新快照份额
                  - SUM(pending赎回份额)
                  - SUM(confirmed赎回份额 WHERE 快照未生成)
    """
    from app.models.investor_holding import InvestorHolding

    latest_date = get_latest_snapshot_date(db, portfolio_code)

    latest_holding = (
        db.query(InvestorHolding)
        .filter(
            InvestorHolding.portfolio_code == portfolio_code,
            InvestorHolding.investor_code == investor_code,
        )
        .order_by(InvestorHolding.snapshot_date.desc())
        .first()
    )
    shares = Decimal(latest_holding.shares) if latest_holding else Decimal("0")

    pending_redeems = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.investor_code == investor_code,
            Subscription.sub_type == "redeem",
            Subscription.status == "pending",
        )
        .all()
    )
    for s in pending_redeems:
        shares -= Decimal(s.shares) if s.shares else Decimal("0")

    confirmed_redeems = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.investor_code == investor_code,
            Subscription.sub_type == "redeem",
            Subscription.status == "confirmed",
        )
        .all()
    )
    for s in confirmed_redeems:
        if latest_date is None or (s.confirm_date and s.confirm_date > latest_date):
            shares -= Decimal(s.shares) if s.shares else Decimal("0")

    return shares
