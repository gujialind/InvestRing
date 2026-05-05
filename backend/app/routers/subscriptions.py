from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.database import get_db
from app.models.subscription import Subscription
from app.models.portfolio import Portfolio
from app.models.investor import Investor
from app.models.investor_holding import InvestorHolding
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.trading_calendar import TradingCalendar
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse
from app.dependencies import get_current_user, get_current_admin

router = APIRouter()


def _is_trading_day(db: Session, target_date: date) -> bool:
    cal = db.query(TradingCalendar).filter(TradingCalendar.date == target_date).first()
    if not cal:
        return False
    return cal.is_open


def _get_latest_snapshot_date(db: Session, portfolio_code: str) -> Optional[date]:
    from sqlalchemy import func
    result = (
        db.query(func.max(PortfolioValueSnapshot.snapshot_date))
        .filter(PortfolioValueSnapshot.portfolio_code == portfolio_code)
        .scalar()
    )
    return result


def _calculate_investor_available_shares(
    db: Session, portfolio_code: str, investor_code: str
) -> Decimal:
    """
    投资人可用份额实时计算：
    投资人可用份额 = 最新快照份额
                  - SUM(pending赎回份额)
                  - SUM(confirmed赎回份额 WHERE 快照未生成)
    """
    latest_date = _get_latest_snapshot_date(db, portfolio_code)

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


@router.get("")
def get_subscriptions(
    portfolio_code: Optional[str] = None,
    investor_code: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_user),
):
    query = db.query(Subscription)
    if portfolio_code:
        query = query.filter(Subscription.portfolio_code == portfolio_code)
    if investor_code:
        query = query.filter(Subscription.investor_code == investor_code)
    # viewer 只能查看自己的记录
    if current_user.role != "admin":
        query = query.filter(Subscription.investor_code == current_user.code)
    total = query.count()
    items = query.order_by(Subscription.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=SubscriptionResponse)
def create_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    # 交易日校验
    if not _is_trading_day(db, subscription.apply_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "NON_TRADING_DAY", "message": "非交易日，请等待交易日再提交"},
        )

    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == subscription.portfolio_code)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    # 首次申购时组合状态为 draft，确认后变为 active
    if portfolio.status not in ("active", "draft"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "PORTFOLIO_NOT_ACTIVE", "message": "组合未激活"},
        )

    investor = (
        db.query(Investor)
        .filter(Investor.code == subscription.investor_code)
        .first()
    )
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    if subscription.sub_type == "subscribe":
        # 申购输入金额，系统计算份额（确认时计算）
        if subscription.amount is None or subscription.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "INVALID_AMOUNT", "message": "申购金额必须大于0"},
            )
        new_sub = Subscription(
            portfolio_code=subscription.portfolio_code,
            investor_code=subscription.investor_code,
            sub_type="subscribe",
            amount=subscription.amount,
            apply_date=subscription.apply_date,
            status="pending",
            notes=subscription.notes,
        )
    elif subscription.sub_type == "redeem":
        # 赎回输入份额，系统计算金额（按申请日净值）
        if subscription.shares is None or subscription.shares <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "INVALID_SHARES", "message": "赎回份额必须大于0"},
            )
        available = _calculate_investor_available_shares(
            db, subscription.portfolio_code, subscription.investor_code
        )
        if Decimal(str(subscription.shares)) > available:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "INSUFFICIENT_SHARES",
                    "message": "赎回份额超过可用份额",
                },
            )
        new_sub = Subscription(
            portfolio_code=subscription.portfolio_code,
            investor_code=subscription.investor_code,
            sub_type="redeem",
            shares=subscription.shares,
            apply_date=subscription.apply_date,
            status="pending",
            notes=subscription.notes,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid subscription type")

    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    return new_sub


@router.get("/{id}", response_model=SubscriptionResponse)
def get_subscription(
    id: int,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_user),
):
    subscription = db.query(Subscription).filter(Subscription.id == id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if current_user.role != "admin" and subscription.investor_code != current_user.code:
        raise HTTPException(status_code=403, detail="Permission denied")
    return subscription


def _get_next_trading_day(db: Session, from_date: date, days: int = 1) -> date:
    """
    获取 from_date 之后第 days 个交易日
    days=1 表示 T+1，days=0 表示当天
    """
    from sqlalchemy import func
    next_date = from_date
    for _ in range(max(days, 0)):
        next_date = (
            db.query(func.min(TradingCalendar.date))
            .filter(
                TradingCalendar.date > next_date,
                TradingCalendar.is_open == True,
            )
            .scalar()
        )
        if not next_date:
            break
    return next_date or from_date


@router.post("/{id}/confirm")
def confirm_subscription(
    id: int,
    confirm_date: Optional[date] = None,
    unit_price: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    subscription = db.query(Subscription).filter(Subscription.id == id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if subscription.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": "仅 pending 状态可确认"},
        )

    if confirm_date is None:
        confirm_date = _get_next_trading_day(db, subscription.apply_date, days=1)

    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == subscription.portfolio_code)
        .first()
    )

    is_first = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == subscription.portfolio_code,
            Subscription.sub_type == "subscribe",
            Subscription.status == "confirmed",
        )
        .count()
        == 0
    )

    if subscription.sub_type == "subscribe":
        if is_first:
            nav = Decimal("1.0000")
        else:
            if unit_price is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "MISSING_NAV", "message": "请提供确认净值"},
                )
            nav = Decimal(str(unit_price))
        shares = Decimal(str(subscription.amount)) / nav
        subscription.unit_price = nav
        subscription.shares = shares
        subscription.amount = subscription.amount
    else:
        if unit_price is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "MISSING_NAV", "message": "请提供确认净值"},
            )
        nav = Decimal(str(unit_price))
        amount = Decimal(str(subscription.shares)) * nav
        subscription.unit_price = nav
        subscription.amount = amount

    subscription.status = "confirmed"
    subscription.confirm_date = confirm_date

    if is_first and subscription.sub_type == "subscribe" and portfolio.status == "draft":
        portfolio.status = "active"
        portfolio.started_at = confirm_date

    db.commit()
    db.refresh(subscription)
    resp = SubscriptionResponse.from_orm(subscription)
    return {
        "message": "Subscription confirmed successfully",
        "id": resp.id,
        "portfolio_code": resp.portfolio_code,
        "sub_type": resp.sub_type,
        "amount": resp.amount,
        "shares": resp.shares,
        "unit_price": resp.unit_price,
        "status": resp.status,
        "confirm_date": resp.confirm_date,
        "subscription": resp,
    }


@router.post("/{id}/cancel")
def cancel_subscription(
    id: int,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    subscription = db.query(Subscription).filter(Subscription.id == id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if subscription.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": "仅 pending 状态可取消"},
        )

    subscription.status = "cancelled"
    db.commit()
    return {"message": "Subscription cancelled successfully"}


@router.put("/{id}", response_model=SubscriptionResponse)
def update_subscription(
    id: int,
    subscription: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    db_subscription = db.query(Subscription).filter(Subscription.id == id).first()
    if not db_subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    for field, value in subscription.dict(exclude_unset=True).items():
        setattr(db_subscription, field, value)

    db.commit()
    db.refresh(db_subscription)
    return db_subscription


@router.delete("/{id}")
def delete_subscription(
    id: int,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    subscription = db.query(Subscription).filter(Subscription.id == id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    db.delete(subscription)
    db.commit()
    return {"message": "Subscription deleted successfully"}
