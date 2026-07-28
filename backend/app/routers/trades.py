from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from decimal import Decimal
from app.database import get_db
from app.models.trade import Trade
from app.models.product import Product
from app.schemas.trade import (
    TradeCreate,
    TradeUpdate,
    TradeResponse,
    TradePreviewResult,
    TradePreviewResponse,
)
from app.dependencies import get_current_user, get_current_admin
from app.services.trade_service import (
    confirm_single_trade,
    calculate_confirm_preview,
    sync_transfer_group,
    create_trade as create_trade_service,
    cancel_trade as cancel_trade_service,
    unconfirm_trade as unconfirm_trade_service,
)

router = APIRouter()


@router.get("")
def get_trades(
    portfolio_code: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Trade)
    if portfolio_code:
        query = query.filter(Trade.portfolio_code == portfolio_code)
    total = query.count()
    items = query.order_by(Trade.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=TradeResponse)
def create_trade(
    trade: TradeCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    new_trade = create_trade_service(
        db,
        portfolio_code=trade.portfolio_code,
        product_code=trade.product_code,
        market=trade.market,
        trade_type=trade.trade_type,
        trade_date=trade.trade_date,
        amount=trade.amount,
        actual_amount=trade.actual_amount,
        fee=trade.fee,
        price=trade.price,
        shares=trade.shares,
        platform_code=trade.platform_code,
        notes=trade.notes,
    )
    db.commit()
    db.refresh(new_trade)
    return new_trade


# 注意：必须注册在 GET /{id} 之前，避免路径 "preview" 被 /{id} 吞掉
@router.get("/{id}/preview", response_model=TradePreviewResponse)
def preview_trade_confirm(
    id: int,
    confirm_date: Optional[date] = None,
    price: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """确认前预览：返回真实确认将写入的净值/份额/金额，不落库（与 confirm 共用计算实现）"""
    trade = db.query(Trade).filter(Trade.id == id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": "仅 pending 状态可预览确认结果"},
        )

    product = (
        db.query(Product)
        .filter(Product.code == trade.product_code, Product.market == trade.market)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    price_decimal = Decimal(str(price)) if price is not None else None
    preview = calculate_confirm_preview(
        db, trade, product, confirm_date=confirm_date, price=price_decimal
    )
    return TradePreviewResponse(
        trade=TradeResponse.from_orm(trade),
        preview=TradePreviewResult(
            **{k: v for k, v in preview.items() if k != "paired_cash_amount"}
        ),
        paired_cash_amount=preview["paired_cash_amount"],
    )


@router.get("/{id}", response_model=TradeResponse)
def get_trade(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    trade = db.query(Trade).filter(Trade.id == id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.post("/{id}/confirm")
def confirm_trade(
    id: int,
    confirm_date: Optional[date] = None,
    price: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    trade = db.query(Trade).filter(Trade.id == id).with_for_update().first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_STATUS", "message": "仅 pending 状态可确认"},
        )

    product = (
        db.query(Product)
        .filter(Product.code == trade.product_code, Product.market == trade.market)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    price_decimal = Decimal(str(price)) if price is not None else None
    confirm_single_trade(
        db, trade, product, confirm_date=confirm_date, price=price_decimal
    )
    db.commit()
    db.refresh(trade)
    resp = TradeResponse.from_orm(trade)
    return {
        "message": "Trade confirmed successfully",
        "id": resp.id,
        "portfolio_code": resp.portfolio_code,
        "trade_type": resp.trade_type,
        "status": resp.status,
        "confirm_date": resp.confirm_date,
        "trade": resp,
    }


@router.post("/{id}/cancel")
def cancel_trade(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    trade = db.query(Trade).filter(Trade.id == id).with_for_update().first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    cancel_trade_service(db, trade)
    db.commit()
    return {"message": "Trade cancelled successfully"}


@router.post("/{id}/unconfirm")
def unconfirm_trade(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    trade = db.query(Trade).filter(Trade.id == id).with_for_update().first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    unconfirm_trade_service(db, trade)
    db.commit()
    return {"message": "Trade unconfirmed successfully"}


@router.put("/{id}", response_model=TradeResponse)
def update_trade(
    id: int,
    trade: TradeUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    db_trade = db.query(Trade).filter(Trade.id == id).with_for_update().first()
    if not db_trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if db_trade.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "CANNOT_MODIFY_CONFIRMED",
                "message": "已确认的交易不可直接修改，请先取消确认后再修改"
            }
        )

    update_data = trade.dict(exclude_unset=True)
    # 记录是否改动与配对同步相关的字段
    sync_fields = {"status", "confirm_date", "trade_date"}
    needs_sync = bool(update_data.keys() & sync_fields)

    for field, value in update_data.items():
        setattr(db_trade, field, value)

    # 若改动涉及配对同步相关字段，同步 transfer_group 配对 CASH 腿
    if needs_sync and db_trade.transfer_group:
        sync_transfer_group(db, db_trade, db_trade.status, db_trade.confirm_date)

    # 金额字段变动时，同步配对 CASH 腿金额（#46）
    amount_fields = {"actual_amount", "amount", "fee", "shares", "price"}
    if db_trade.transfer_group and db_trade.product_code != "CASH":
        if update_data.keys() & amount_fields:
            paired = db.query(Trade).filter(
                Trade.transfer_group == db_trade.transfer_group,
                Trade.id != db_trade.id,
                Trade.product_code == "CASH",
            ).first()
            if paired:
                # CASH 腿金额 = 基金腿 actual_amount（买入=支出，卖出=收入）
                new_amount = db_trade.actual_amount or db_trade.amount
                paired.amount = new_amount
                paired.actual_amount = new_amount

    db.commit()
    db.refresh(db_trade)
    return db_trade


@router.delete("/{id}")
def delete_trade(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    trade = db.query(Trade).filter(Trade.id == id).with_for_update().first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "CANNOT_DELETE_CONFIRMED",
                "message": "已确认的交易不可直接删除，请先取消确认后再删除"
            }
        )

    # 级联删除配对 CASH 腿（同一 transfer_group 的另一腿）
    if trade.transfer_group:
        db.query(Trade).filter(
            Trade.transfer_group == trade.transfer_group,
            Trade.id != trade.id,
        ).delete(synchronize_session=False)

    db.delete(trade)
    db.commit()
    return {"message": "Trade deleted successfully"}
