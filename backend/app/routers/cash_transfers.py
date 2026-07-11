"""
平台间现金转移 API

通过复用 Trade 表实现：一次转移生成两条 CASH 交易记录（卖出+买入），
通过 transfer_group 字段关联。支持当天完成和跨天到账两种模式。
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from decimal import Decimal

from app.database import get_db
from app.models.portfolio import Portfolio
from app.models.platform import Platform
from app.models.trade import Trade
from app.models.trading_calendar import TradingCalendar
from app.schemas.cash_transfer import (
    CashTransferCreate,
    CashTransferResponse,
    CashTransferListItem,
)
from app.services.position_service import calculate_available_cash
from app.dependencies import get_current_admin


router = APIRouter()


def _is_trading_day(db: Session, target_date: date) -> bool:
    cal = db.query(TradingCalendar).filter(TradingCalendar.date == target_date).first()
    if not cal:
        return False
    return cal.is_open


def _get_next_trading_day(db: Session, from_date: date) -> date:
    from sqlalchemy import func
    next_date = (
        db.query(func.min(TradingCalendar.date))
        .filter(
            TradingCalendar.date > from_date,
            TradingCalendar.is_open == True,
        )
        .scalar()
    )
    return next_date or from_date


@router.post("/portfolios/{portfolio_code}/cash-transfer", response_model=CashTransferResponse)
def create_cash_transfer(
    portfolio_code: str,
    request: CashTransferCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    创建平台间现金转移

    生成两条 Trade 记录（卖出 CASH + 买入 CASH），通过 transfer_group 关联。
    - 当天完成：两条 Trade 立即 confirm
    - 跨天到账：卖出 Trade 立即 confirm，买入 Trade 保持 pending
    """
    # 校验组合
    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail={"error": "PORTFOLIO_NOT_FOUND", "message": f"组合 {portfolio_code} 不存在"})
    if portfolio.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "PORTFOLIO_NOT_ACTIVE", "message": "组合未激活"},
        )

    # 校验两个平台存在且不同
    if request.from_platform == request.to_platform:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "SAME_PLATFORM", "message": "转出平台和转入平台不能相同"},
        )
    from_plat = db.query(Platform).filter(Platform.code == request.from_platform).first()
    if not from_plat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLATFORM_NOT_FOUND", "message": f"转出平台 {request.from_platform} 不存在"},
        )
    to_plat = db.query(Platform).filter(Platform.code == request.to_platform).first()
    if not to_plat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLATFORM_NOT_FOUND", "message": f"转入平台 {request.to_platform} 不存在"},
        )

    # 校验交易日
    if not _is_trading_day(db, request.transfer_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "NON_TRADING_DAY", "message": "非交易日，请等待交易日再提交"},
        )

    # (a) 转移日必须晚于最新快照日
    from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
    from sqlalchemy import func
    latest_snapshot_date = (
        db.query(func.max(PortfolioValueSnapshot.snapshot_date))
        .filter(PortfolioValueSnapshot.portfolio_code == portfolio_code)
        .scalar()
    )
    if latest_snapshot_date and request.transfer_date <= latest_snapshot_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "DATE_BEFORE_SNAPSHOT",
                "message": f"转移日必须晚于最新快照日（{latest_snapshot_date}）",
            },
        )

    # 校验金额
    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_AMOUNT", "message": "转移金额必须大于0"},
        )

    # 校验转出平台可用现金
    available_cash = calculate_available_cash(db, portfolio_code, request.from_platform)
    if Decimal(str(request.amount)) > available_cash:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INSUFFICIENT_CASH",
                "message": f"平台 {request.from_platform} 的可用现金不足（当前: {float(available_cash)}）",
            },
        )

    # 生成 transfer_group
    transfer_group = uuid.uuid4().hex[:12]
    amount = Decimal(str(request.amount))

    # 创建卖出 CASH（转出）
    sell_trade = Trade(
        portfolio_code=portfolio_code,
        platform_code=request.from_platform,
        product_code="CASH",
        market="",
        trade_type="sell",
        transfer_group=transfer_group,
        amount=amount,
        price=Decimal("1"),
        fee=Decimal("0"),
        actual_amount=amount,
        trade_date=request.transfer_date,
        status="pending",
        notes=request.notes or f"现金转移至 {request.to_platform}",
    )
    db.add(sell_trade)
    db.flush()

    # 创建买入 CASH（转入）
    buy_trade = Trade(
        portfolio_code=portfolio_code,
        platform_code=request.to_platform,
        product_code="CASH",
        market="",
        trade_type="buy",
        transfer_group=transfer_group,
        amount=amount,
        price=Decimal("1"),
        fee=Decimal("0"),
        actual_amount=amount,
        trade_date=request.transfer_date,
        status="pending",
        notes=request.notes or f"现金从 {request.from_platform} 转入",
    )
    db.add(buy_trade)
    db.flush()

    # 确认策略
    if not request.cross_day:
        # 当天完成：两条 Trade 立即 confirm
        sell_trade.status = "confirmed"
        sell_trade.confirm_date = request.transfer_date
        buy_trade.status = "confirmed"
        buy_trade.confirm_date = request.transfer_date
    else:
        # 跨天到账：两腿均 pending，confirm_date = 下一交易日（对称状态）
        # D 日快照中两腿均 pending → compute_cash_balance 不计入 → NAV 不跌
        # D+1 同时 confirm → 资金从 A 转移到 B
        next_trading_day = _get_next_trading_day(db, request.transfer_date)
        sell_trade.status = "pending"
        sell_trade.confirm_date = next_trading_day
        buy_trade.status = "pending"
        buy_trade.confirm_date = next_trading_day

    db.commit()
    db.refresh(sell_trade)
    db.refresh(buy_trade)

    return CashTransferResponse(
        transfer_group=transfer_group,
        from_platform=request.from_platform,
        to_platform=request.to_platform,
        amount=float(amount),
        cross_day=request.cross_day,
        sell_trade_id=sell_trade.id,
        buy_trade_id=buy_trade.id,
        sell_status=sell_trade.status,
        buy_status=buy_trade.status,
        transfer_date=request.transfer_date,
    )


@router.post("/portfolios/{portfolio_code}/cash-transfer/{transfer_group}/confirm")
def confirm_cash_transfer(
    portfolio_code: str,
    transfer_group: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    确认跨天转移的两条 pending Trade

    对称状态改造后，两腿均 pending，需同时确认。
    """
    # 查找该 transfer_group 的所有 pending trade
    pending_trades = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.transfer_group == transfer_group,
            Trade.product_code == "CASH",
            Trade.status == "pending",
        )
        .all()
    )
    if not pending_trades:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "TRANSFER_NOT_FOUND", "message": f"未找到待确认的转移记录 {transfer_group}"},
        )

    # 取第一条 trade 的 confirm_date（两腿 confirm_date 相同）
    confirm_date = pending_trades[0].confirm_date
    if not confirm_date:
        confirm_date = _get_next_trading_day(db, pending_trades[0].trade_date)

    # TRANSFER_NOT_READY 守卫
    if confirm_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "TRANSFER_NOT_READY",
                "message": f"跨天转移尚未到确认日期（预计确认日: {confirm_date}）",
            },
        )

    # 同时确认两腿
    for trade in pending_trades:
        trade.status = "confirmed"
        trade.confirm_date = confirm_date

    db.commit()

    return {
        "message": "跨天转移确认成功",
        "transfer_group": transfer_group,
        "confirmed_count": len(pending_trades),
        "confirm_date": confirm_date.isoformat() if confirm_date else None,
    }


@router.get("/portfolios/{portfolio_code}/cash-transfers")
def list_cash_transfers(
    portfolio_code: str,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    查询平台间现金转移记录

    通过 Trade.transfer_group IS NOT NULL AND Trade.product_code='CASH' 过滤，
    按 transfer_group 分组返回。
    """
    # 查找所有带 transfer_group 的 CASH 交易
    trades = (
        db.query(Trade)
        .filter(
            Trade.portfolio_code == portfolio_code,
            Trade.transfer_group.isnot(None),
            Trade.product_code == "CASH",
        )
        .order_by(Trade.created_at.desc())
        .all()
    )

    # 按 transfer_group 分组
    groups = {}
    for t in trades:
        if t.transfer_group not in groups:
            groups[t.transfer_group] = {"sell": None, "buy": None}
        if t.trade_type == "sell":
            groups[t.transfer_group]["sell"] = t
        elif t.trade_type == "buy":
            groups[t.transfer_group]["buy"] = t

    # 构建结果
    items = []
    for tg, pair in groups.items():
        sell = pair.get("sell")
        buy = pair.get("buy")
        if not sell or not buy:
            continue
        items.append(CashTransferListItem(
            transfer_group=tg,
            from_platform=sell.platform_code or "",
            to_platform=buy.platform_code or "",
            amount=float(sell.amount or 0),
            # 对称状态后：跨天判断依据为 confirm_date > trade_date
            cross_day=(sell.confirm_date is not None and sell.confirm_date > sell.trade_date),
            sell_status=sell.status,
            buy_status=buy.status,
            transfer_date=sell.trade_date,
            sell_confirm_date=sell.confirm_date,
            buy_confirm_date=buy.confirm_date,
            notes=sell.notes,
        ))

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": [item.model_dump() for item in items[start:end]],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
