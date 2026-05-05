from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
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
    # 权益登记日必须是交易日
    if not _is_trading_day(db, event.entitlement_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INVALID_ENTITLEMENT_DATE",
                "message": "权益登记日不是交易日",
            },
        )

    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == event.portfolio_code)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

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

    event.status = "confirmed"
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
