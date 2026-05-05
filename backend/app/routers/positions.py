from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.database import get_db
from app.models.portfolio_position import PortfolioPosition
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.subscription import Subscription
from app.models.trade import Trade
from app.models.product import Product
from app.schemas.position import PositionCreate, PositionUpdate, PositionResponse
from app.dependencies import get_current_user, get_current_admin

router = APIRouter()


def _get_latest_snapshot_date(db: Session, portfolio_code: str) -> Optional[date]:
    result = (
        db.query(func.max(PortfolioValueSnapshot.snapshot_date))
        .filter(PortfolioValueSnapshot.portfolio_code == portfolio_code)
        .scalar()
    )
    return result


def _calculate_available_cash(db: Session, portfolio_code: str) -> Decimal:
    """
    组合可用现金实时计算：
    最新快照现金
    + SUM(confirmed申购金额 WHERE 快照未生成)
    - SUM(confirmed赎回金额 WHERE 快照未生成)
    - SUM(pending买入金额)
    - SUM(confirmed买入金额 WHERE 快照未生成)
    + SUM(confirmed卖出金额 WHERE 快照未生成)
    """
    latest_date = _get_latest_snapshot_date(db, portfolio_code)

    # 最新快照现金（从 portfolio_value_snapshot 中，现金产品 code 为 CASH）
    # 这里简化：现金通过 portfolio_value_snapshot 的 total_value 反推
    # 实际系统中现金可能单独存储，这里用快照 total_value - 持仓市值 近似
    # 更合理的做法：从 portfolio_position 中找 CASH 产品的 amount
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

    # confirmed 申购未快照
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

    # confirmed 赎回未快照
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

    # pending 买入金额
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

    # confirmed 买入未快照
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

    # confirmed 卖出未快照
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


def _calculate_available_shares(
    db: Session, portfolio_code: str, product_code: str, market: Optional[str] = None
) -> Decimal:
    """
    基金可用份额实时计算：
    基金可用份额 = 最新快照份额
                - SUM(pending卖出份额)
                - SUM(confirmed卖出份额 WHERE 快照未生成)
    """
    latest_date = _get_latest_snapshot_date(db, portfolio_code)

    query = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == portfolio_code,
        PortfolioPosition.product_code == product_code,
    )
    if market:
        query = query.filter(PortfolioPosition.market == market)
    latest_position = query.order_by(PortfolioPosition.snapshot_date.desc()).first()

    shares = Decimal(latest_position.shares) if latest_position and latest_position.shares else Decimal("0")

    # pending 卖出份额
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

    # confirmed 卖出未快照
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


@router.get("")
def get_positions(
    portfolio_code: Optional[str] = None,
    snapshot_date: Optional[date] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(PortfolioPosition)
    if portfolio_code:
        query = query.filter(PortfolioPosition.portfolio_code == portfolio_code)
    if snapshot_date:
        query = query.filter(PortfolioPosition.snapshot_date == snapshot_date)
    else:
        # 默认查询最新快照：每个组合每个产品的最新日期
        subq = (
            db.query(
                PortfolioPosition.portfolio_code,
                PortfolioPosition.product_code,
                func.max(PortfolioPosition.snapshot_date).label("max_date"),
            )
            .group_by(PortfolioPosition.portfolio_code, PortfolioPosition.product_code)
            .subquery()
        )
        query = query.join(
            subq,
            (PortfolioPosition.portfolio_code == subq.c.portfolio_code)
            & (PortfolioPosition.product_code == subq.c.product_code)
            & (PortfolioPosition.snapshot_date == subq.c.max_date),
        )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=PositionResponse)
def create_position(
    position: PositionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    new_position = PortfolioPosition(**position.dict())
    db.add(new_position)
    db.commit()
    db.refresh(new_position)
    return new_position


@router.get("/{id}", response_model=PositionResponse)
def get_position(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    position = db.query(PortfolioPosition).filter(PortfolioPosition.id == id).first()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


@router.put("/{id}", response_model=PositionResponse)
def update_position(
    id: int,
    position: PositionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    db_position = db.query(PortfolioPosition).filter(PortfolioPosition.id == id).first()
    if not db_position:
        raise HTTPException(status_code=404, detail="Position not found")

    for field, value in position.dict(exclude_unset=True).items():
        setattr(db_position, field, value)

    db.commit()
    db.refresh(db_position)
    return db_position


@router.delete("/{id}")
def delete_position(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    position = db.query(PortfolioPosition).filter(PortfolioPosition.id == id).first()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    db.delete(position)
    db.commit()
    return {"message": "Position deleted successfully"}


@router.get("/portfolio/{portfolio_code}/available-cash")
def get_available_cash(
    portfolio_code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.portfolio import Portfolio

    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    cash = _calculate_available_cash(db, portfolio_code)
    return {"portfolio_code": portfolio_code, "available_cash": float(cash)}


@router.get("/portfolio/{portfolio_code}/product/{product_code}/available-shares")
def get_available_shares(
    portfolio_code: str,
    product_code: str,
    market: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.portfolio import Portfolio

    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    shares = _calculate_available_shares(db, portfolio_code, product_code, market)
    return {
        "portfolio_code": portfolio_code,
        "product_code": product_code,
        "market": market,
        "available_shares": float(shares),
    }
