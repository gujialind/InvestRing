from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.database import get_db
from app.models.portfolio_position import PortfolioPosition
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.trade import Trade
from app.models.product import Product
from app.schemas.position import PositionCreate, PositionUpdate, PositionResponse, CashPositionUpdate
from app.services.position_service import calculate_available_cash
from app.dependencies import get_current_user, get_current_admin

router = APIRouter()


def _get_latest_snapshot_date(db: Session, portfolio_code: str) -> Optional[date]:
    result = (
        db.query(func.max(PortfolioValueSnapshot.snapshot_date))
        .filter(PortfolioValueSnapshot.portfolio_code == portfolio_code)
        .scalar()
    )
    return result


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
    # (g) 禁止直接操作 portfolio_position 表（快照为系统生成，不可手动创建）
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "POSITION_TABLE_PROTECTED",
            "message": "持仓快照由系统自动生成，不可手动创建。如需修改现金持仓，请使用 /portfolio/{portfolio_code}/cash-position 端点",
        },
    )


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
    # (g) 禁止直接操作 portfolio_position 表
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "POSITION_TABLE_PROTECTED",
            "message": "持仓快照由系统自动生成，不可手动修改。如需修改现金持仓，请使用 /portfolio/{portfolio_code}/cash-position 端点",
        },
    )


@router.delete("/{id}")
def delete_position(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    # (g) 禁止直接操作 portfolio_position 表
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "POSITION_TABLE_PROTECTED",
            "message": "持仓快照由系统自动生成，不可手动删除。如需删除快照，请使用 DELETE /snapshots/{portfolio_code}/{snapshot_date}",
        },
    )


@router.get("/portfolio/{portfolio_code}/available-cash")
def get_available_cash(
    portfolio_code: str,
    platform_code: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.portfolio import Portfolio

    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    cash = calculate_available_cash(db, portfolio_code, platform_code)
    result = {"portfolio_code": portfolio_code, "available_cash": float(cash)}
    if platform_code:
        result["platform_code"] = platform_code
    return result


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


@router.post("/portfolio/{portfolio_code}/cash-position")
def update_cash_position(
    portfolio_code: str,
    request: CashPositionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    更新非净值型资产（现金）金额
    
    权限：仅admin
    规则：
    - 必须在交易日进行
    - 必须指定平台代码
    - 写入 manual_market_value 表（绝对替换），不再直接写 portfolio_position
    - 写入后提示用户重新生成快照（非强制）
    """
    from app.models.portfolio import Portfolio
    from app.models.platform import Platform
    from app.models.trading_calendar import TradingCalendar
    from app.models.manual_market_value import ManualMarketValue
    from app.services.position_service import compute_cash_balance
    
    # 检查组合是否存在
    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PORTFOLIO_NOT_FOUND", "message": f"组合 {portfolio_code} 不存在"}
        )
    
    # 校验平台存在性
    platform = db.query(Platform).filter(Platform.code == request.platform_code).first()
    if not platform:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLATFORM_NOT_FOUND", "message": f"平台 {request.platform_code} 不存在"}
        )
    
    # 确定更新日期（默认为今天）
    update_date = request.update_date or date.today()
    
    # 校验是否为交易日
    trading_day = db.query(TradingCalendar).filter(
        TradingCalendar.date == update_date,
        TradingCalendar.is_open == True
    ).first()
    
    if not trading_day:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "NON_TRADING_DAY",
                "message": "非交易日，请等待交易日再提交"
            }
        )
    
    # 计算当前隐式值（用于审计）
    computed = compute_cash_balance(db, portfolio_code, request.platform_code, update_date)

    # 查找或创建 manual_market_value 记录（upsert）
    manual = db.query(ManualMarketValue).filter(
        ManualMarketValue.portfolio_code == portfolio_code,
        ManualMarketValue.platform_code == request.platform_code,
        ManualMarketValue.product_code == "CASH",
        ManualMarketValue.date == update_date,
    ).first()
    
    if manual:
        manual.market_value = Decimal(str(request.amount))
        manual.computed_value = computed
    else:
        manual = ManualMarketValue(
            portfolio_code=portfolio_code,
            platform_code=request.platform_code,
            product_code="CASH",
            date=update_date,
            market_value=Decimal(str(request.amount)),
            computed_value=computed,
            created_by=current_user.code if hasattr(current_user, 'code') else None,
        )
        db.add(manual)
    
    db.commit()
    db.refresh(manual)
    
    return {
        "success": True,
        "message": "现金市值覆盖已写入 manual_market_value，建议重新生成快照以更新持仓",
        "portfolio_code": portfolio_code,
        "platform_code": request.platform_code,
        "amount": float(manual.market_value),
        "computed_value": float(computed) if computed is not None else None,
        "update_date": update_date.isoformat(),
        "requires_snapshot_regen": True,
    }
