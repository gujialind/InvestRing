from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from app.database import get_db
from app.models.share_change_event import ShareChangeEvent
from app.models.portfolio import Portfolio
from app.models.portfolio_position import PortfolioPosition
from app.models.trading_calendar import TradingCalendar
from app.schemas.share_change_event import (
    ShareChangeEventCreate,
    ShareChangeEventUpdate,
    ShareChangeEventResponse,
)
from app.dependencies import get_current_user, get_current_admin
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot

router = APIRouter()


def _is_trading_day(db: Session, target_date: date) -> bool:
    cal = db.query(TradingCalendar).filter(TradingCalendar.date == target_date).first()
    if not cal:
        return False
    return cal.is_open


@router.get("")
def get_share_change_events(
    portfolio_code: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(ShareChangeEvent)
    if portfolio_code:
        query = query.filter(ShareChangeEvent.portfolio_code == portfolio_code)
    total = query.count()
    items = query.order_by(ShareChangeEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=ShareChangeEventResponse)
def create_share_change_event(
    event: ShareChangeEventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    # (e) 权益登记日必须是交易日
    if not _is_trading_day(db, event.entitlement_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INVALID_ENTITLEMENT_DATE",
                "message": "权益登记日不是交易日",
            },
        )

    # (e) 除息日必须是交易日
    if not _is_trading_day(db, event.ex_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INVALID_EX_DATE",
                "message": "除息日不是交易日",
            },
        )

    # (d) 除息日必须严格大于权益登记日
    if event.ex_date <= event.entitlement_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INVALID_DATE_ORDER",
                "message": "除息日必须严格大于权益登记日（ex_date > entitlement_date）",
            },
        )

    # (a) 除息日必须晚于最新快照日
    latest_snapshot = (
        db.query(PortfolioValueSnapshot.snapshot_date)
        .filter(PortfolioValueSnapshot.portfolio_code == event.portfolio_code)
        .order_by(PortfolioValueSnapshot.snapshot_date.desc())
        .first()
    )
    if latest_snapshot and event.ex_date <= latest_snapshot[0]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "DATE_BEFORE_SNAPSHOT",
                "message": f"除息日必须晚于最新快照日（{latest_snapshot[0]}）",
            },
        )

    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == event.portfolio_code)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # (f) cash_dividend / forced_adjustment(cash_change!=0) 的 platform_code 必填
    if event.event_type == "cash_dividend" and not event.platform_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "PLATFORM_REQUIRED",
                "message": "现金分红事件必须指定 platform_code",
            },
        )
    if event.event_type == "forced_adjustment" and event.cash_change and event.cash_change != 0 and not event.platform_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "PLATFORM_REQUIRED",
                "message": "涉及现金变动的强制调整必须指定 platform_code",
            },
        )

    new_event = ShareChangeEvent(**event.dict())
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event


@router.get("/{id}", response_model=ShareChangeEventResponse)
def get_share_change_event(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Share change event not found")
    return event


@router.post("/{id}/confirm")
def confirm_share_change_event(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Share change event not found")
    if event.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": "仅 pending 状态可确认"},
        )

    # 校验权益登记日持仓快照是否存在
    position_snapshot = (
        db.query(PortfolioPosition)
        .filter(
            PortfolioPosition.portfolio_code == event.portfolio_code,
            PortfolioPosition.snapshot_date == event.entitlement_date,
        )
        .first()
    )
    if not position_snapshot:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "MISSING_POSITION_SNAPSHOT",
                "message": "权益登记日持仓快照不存在",
            },
        )

    # 从 entitlement_date 快照读取 entitlement_shares
    entitlement_position = (
        db.query(PortfolioPosition)
        .filter(
            PortfolioPosition.portfolio_code == event.portfolio_code,
            PortfolioPosition.product_code == event.product_code,
            PortfolioPosition.snapshot_date == event.entitlement_date,
        )
        .first()
    )
    entitlement_shares = Decimal(str(entitlement_position.shares or 0)) if entitlement_position else Decimal("0")

    event.entitlement_shares = entitlement_shares
    event.shares_before = entitlement_shares

    # 按 event_type 计算 shares_change / shares_after / cash_change
    if event.event_type == "cash_dividend":
        event.cash_change = entitlement_shares * Decimal(str(event.div_cash or 0))
        event.shares_change = Decimal("0")
        event.shares_after = entitlement_shares
    elif event.event_type == "reinvest_dividend":
        event.shares_change = entitlement_shares * Decimal(str(event.div_cash or 0)) / Decimal(str(event.reinvest_nav or 1))
        event.shares_after = entitlement_shares + event.shares_change
        event.cash_change = Decimal("0")
    elif event.event_type == "share_split":
        event.shares_after = entitlement_shares * Decimal(str(event.ratio or 1))
        event.shares_change = event.shares_after - entitlement_shares
        event.cash_change = Decimal("0")
    elif event.event_type == "share_merge":
        event.shares_after = entitlement_shares / Decimal(str(event.ratio or 1))
        event.shares_change = event.shares_after - entitlement_shares
        event.cash_change = Decimal("0")
    elif event.event_type == "bonus_share":
        event.shares_change = entitlement_shares * Decimal(str(event.ratio or 0))
        event.shares_after = entitlement_shares + event.shares_change
        event.cash_change = Decimal("0")
    # forced_adjustment: shares_change / cash_change 由用户直接填写，不自动计算

    event.status = "confirmed"
    event.confirmed_at = datetime.now()
    db.commit()
    db.refresh(event)
    return {"message": "Share change event confirmed successfully", "event": ShareChangeEventResponse.from_orm(event)}


@router.post("/{id}/cancel")
def cancel_share_change_event(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Share change event not found")
    if event.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": "仅 pending 状态可取消"},
        )

    event.status = "cancelled"
    db.commit()
    return {"message": "Share change event cancelled successfully"}


@router.put("/{id}", response_model=ShareChangeEventResponse)
def update_share_change_event(
    id: int,
    event: ShareChangeEventUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    db_event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Share change event not found")

    for field, value in event.dict(exclude_unset=True).items():
        setattr(db_event, field, value)

    db.commit()
    db.refresh(db_event)
    return db_event


@router.delete("/{id}")
def delete_share_change_event(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Share change event not found")

    db.delete(event)
    db.commit()
    return {"message": "Share change event deleted successfully"}
