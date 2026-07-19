from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.database import get_db
from app.models.subscription import Subscription
from app.models.portfolio import Portfolio
from app.models.investor import Investor
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.platform import Platform
from app.services.trading_utils import (
    is_trading_day,
    get_next_trading_day,
    get_latest_snapshot_date,
)
from app.services.position_service import calculate_investor_available_shares
from app.services.subscription_service import (
    confirm_single_subscription,
    unconfirm_single_subscription,
    NavNotAvailableError,
    InvalidStatusError,
)
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse
from app.dependencies import get_current_user, get_current_admin

router = APIRouter()


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
    if not is_trading_day(db, subscription.apply_date):
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

    # (a) 申请日必须晚于最新快照日
    latest_snapshot_date = get_latest_snapshot_date(db, subscription.portfolio_code)
    if latest_snapshot_date and subscription.apply_date <= latest_snapshot_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "DATE_BEFORE_SNAPSHOT",
                "message": f"申请日必须晚于最新快照日（{latest_snapshot_date}）",
            },
        )

    investor = (
        db.query(Investor)
        .filter(Investor.code == subscription.investor_code)
        .first()
    )
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    # 校验平台存在性
    platform = (
        db.query(Platform)
        .filter(Platform.code == subscription.platform_code)
        .first()
    )
    if not platform:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLATFORM_NOT_FOUND", "message": f"平台 {subscription.platform_code} 不存在"},
        )

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
            platform_code=subscription.platform_code,
            sub_type="subscribe",
            amount=subscription.amount,
            apply_date=subscription.apply_date,
            confirm_date=get_next_trading_day(db, subscription.apply_date, days=1),
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
        available = calculate_investor_available_shares(
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
            platform_code=subscription.platform_code,
            sub_type="redeem",
            shares=subscription.shares,
            apply_date=subscription.apply_date,
            confirm_date=get_next_trading_day(db, subscription.apply_date, days=1),
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



@router.post("/{id}/confirm")
def confirm_subscription(
    id: int,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    subscription = db.query(Subscription).filter(Subscription.id == id).with_for_update().first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    try:
        confirm_single_subscription(db, subscription)
    except InvalidStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": str(e)},
        )
    except NavNotAvailableError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "NAV_NOT_AVAILABLE", "message": str(e)},
        )

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
    subscription = db.query(Subscription).filter(Subscription.id == id).with_for_update().first()
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


@router.post("/{id}/unconfirm")
def unconfirm_subscription(
    id: int,
    db: Session = Depends(get_db),
    current_user: Investor = Depends(get_current_admin),
):
    subscription = db.query(Subscription).filter(Subscription.id == id).with_for_update().first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # 快照保护：确认日及之后已有快照则拒绝
    if subscription.status == "confirmed" and subscription.confirm_date:
        snapshots_after = (
            db.query(PortfolioValueSnapshot)
            .filter(
                PortfolioValueSnapshot.portfolio_code == subscription.portfolio_code,
                PortfolioValueSnapshot.snapshot_date >= subscription.confirm_date,
            )
            .count()
        )
        if snapshots_after > 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "SNAPSHOT_DEPENDENCY",
                    "message": (
                        f"该申赎已被快照纳入（{subscription.confirm_date} 及之后有 {snapshots_after} 张快照），"
                        f"请先删除 {subscription.confirm_date} 及之后的快照"
                    ),
                },
            )

    try:
        unconfirm_single_subscription(db, subscription)
    except InvalidStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": str(e)},
        )

    db.commit()
    return {"message": "Subscription unconfirmed successfully"}


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

    if db_subscription.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "CANNOT_MODIFY_CONFIRMED",
                "message": "已确认的申购赎回事件不可直接修改，请先取消确认后再修改"
            }
        )

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

    if subscription.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "CANNOT_DELETE_CONFIRMED",
                "message": "已确认的申购赎回事件不可直接删除，请先取消确认后再删除"
            }
        )

    db.delete(subscription)
    db.commit()
    return {"message": "Subscription deleted successfully"}
