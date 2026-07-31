from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.database import get_db
from app.models.portfolio_position import PortfolioPosition
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.schemas.position import PositionCreate, PositionUpdate, PositionResponse, CashPositionUpdate
from app.services.position_service import (
    calculate_available_cash,
    calculate_available_shares,
    calculate_investor_available_shares,
)
from app.dependencies import get_current_user, get_current_admin

router = APIRouter()


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

    shares = calculate_available_shares(db, portfolio_code, product_code, market)
    return {
        "portfolio_code": portfolio_code,
        "product_code": product_code,
        "market": market,
        "available_shares": float(shares),
    }


@router.get("/portfolio/{portfolio_code}/investor/{investor_code}/available-shares")
def get_investor_available_shares(
    portfolio_code: str,
    investor_code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.investor import Investor
    from app.models.portfolio import Portfolio

    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    investor = db.query(Investor).filter(Investor.code == investor_code).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    shares = calculate_investor_available_shares(db, portfolio_code, investor_code)
    return {
        "portfolio_code": portfolio_code,
        "investor_code": investor_code,
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
    - 同日存在已确认现金交易时附 warnings 提示（issue #88，不阻断）
    """
    from app.services.position_service import update_cash_position as update_cash_service

    result = update_cash_service(
        db,
        portfolio_code=portfolio_code,
        platform_code=request.platform_code,
        amount=request.cash_amount,
        update_date=request.update_date,
        created_by=current_user.code if hasattr(current_user, 'code') else None,
    )
    db.commit()

    return {
        "success": True,
        "message": "现金市值覆盖已写入 manual_market_value，建议重新生成快照以更新持仓",
        "portfolio_code": result["portfolio_code"],
        "platform_code": result["platform_code"],
        "cash_amount": result["cash_amount"],
        "computed_value": result["computed_value"],
        "update_date": result["update_date"].isoformat(),
        "requires_snapshot_regen": True,
        "warnings": result["warnings"],
    }


@router.get("/portfolio/{portfolio_code}/cash-position")
def list_cash_overrides(
    portfolio_code: str,
    platform_code: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    查询现金手动覆盖记录（manual_market_value，issue #88）

    权限：仅admin
    """
    from app.services.position_service import list_manual_cash_overrides

    items = list_manual_cash_overrides(
        db,
        portfolio_code,
        platform_code=platform_code,
        start_date=start_date,
        end_date=end_date,
    )
    return {"items": items, "total": len(items)}


@router.delete("/portfolio/{portfolio_code}/cash-position")
def delete_cash_override(
    portfolio_code: str,
    platform_code: str,
    update_date: date,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    删除现金手动覆盖记录（issue #88）

    删除后该日该平台回退到自然计算值；若覆盖已 baked in 快照，
    需重算快照才生效（requires_snapshot_regen）。

    权限：仅admin
    """
    from app.services.position_service import delete_manual_cash_override

    result = delete_manual_cash_override(
        db,
        portfolio_code=portfolio_code,
        platform_code=platform_code,
        value_date=update_date,
    )
    db.commit()

    return {
        "success": True,
        "message": f"已删除 {portfolio_code}/{platform_code} 在 {update_date} 的现金覆盖记录",
        "portfolio_code": result["portfolio_code"],
        "platform_code": result["platform_code"],
        "update_date": result["value_date"].isoformat(),
        "deleted_value": result["deleted_value"],
        "requires_snapshot_regen": result["requires_snapshot_regen"],
    }
