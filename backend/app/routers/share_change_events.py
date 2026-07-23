from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging
from app.database import get_db
from app.models.share_change_event import ShareChangeEvent
from app.schemas.share_change_event import (
    ShareChangeEventCreate,
    ShareChangeEventUpdate,
    ShareChangeEventResponse,
)
from app.dependencies import get_current_user, get_current_admin
from app.services.share_change_event_service import (
    create_share_change_event as create_event_service,
    confirm_share_change_event as confirm_event_service,
    cancel_share_change_event as cancel_event_service,
    unconfirm_share_change_event as unconfirm_event_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
    force_cover: bool = Query(False, description="平台覆盖不全时降为 warning（默认阻断）"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    new_event = create_event_service(
        db,
        portfolio_code=event.portfolio_code,
        event_type=event.event_type,
        ex_date=event.ex_date,
        entitlement_date=event.entitlement_date,
        product_code=event.product_code,
        market=event.market,
        platform_code=event.platform_code,
        entitlement_shares=event.entitlement_shares,
        shares_before=event.shares_before,
        shares_change=event.shares_change,
        shares_after=event.shares_after,
        cash_change=event.cash_change,
        cash_product_code=event.cash_product_code,
        div_cash=event.div_cash,
        reinvest_nav=event.reinvest_nav,
        ratio=event.ratio,
        event_source=event.event_source,
        tushare_event_id=event.tushare_event_id,
        notes=event.notes,
        force_cover=force_cover,
    )
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
    event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).with_for_update().first()
    if not event:
        raise HTTPException(status_code=404, detail="Share change event not found")
    confirm_event_service(db, event)
    db.commit()
    db.refresh(event)
    return {"message": "Share change event confirmed successfully", "event": ShareChangeEventResponse.from_orm(event)}


@router.post("/{id}/cancel")
def cancel_share_change_event(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).with_for_update().first()
    if not event:
        raise HTTPException(status_code=404, detail="Share change event not found")
    cancel_event_service(db, event)
    db.commit()
    return {"message": "Share change event cancelled successfully"}


@router.post("/{id}/unconfirm")
def unconfirm_share_change_event(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """取消确认份额变动事件。

    - 仅 confirmed 状态可 unconfirm，否则 422 INVALID_STATUS
    - 快照保护：ex_date 及之后已有快照则拒绝 422 SNAPSHOT_DEPENDENCY
    - 基金级父记录（platform_code 为空）：级联删除所有子记录后置 pending
    - 平台级记录（platform_code 非空）：直接置 pending
    - 子记录（parent_event_id 非空）单独 unconfirm 拒绝：422 CANNOT_UNCONFIRM_CHILD
    """
    event = db.query(ShareChangeEvent).filter(ShareChangeEvent.id == id).with_for_update().first()
    if not event:
        raise HTTPException(status_code=404, detail="Share change event not found")
    unconfirm_event_service(db, event)
    db.commit()
    db.refresh(event)
    return {"message": "Share change event unconfirmed successfully", "event": ShareChangeEventResponse.from_orm(event)}


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

    # 父记录：先删除所有子记录
    db.query(ShareChangeEvent).filter(
        ShareChangeEvent.parent_event_id == event.id
    ).delete(synchronize_session=False)

    db.delete(event)
    db.commit()
    return {"message": "Share change event deleted successfully"}
