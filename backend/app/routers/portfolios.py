from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime
from app.database import get_db
from app.models.portfolio import Portfolio
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.subscription import Subscription
from app.models.trade import Trade
from app.models.investor_holding import InvestorHolding
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate, PortfolioResponse
from app.dependencies import get_current_user, get_current_admin

router = APIRouter()


@router.get("")
def get_portfolios(
    status: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Portfolio)
    if status:
        query = query.filter(Portfolio.status == status)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=PortfolioResponse)
def create_portfolio(
    portfolio: PortfolioCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    db_portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio.code).first()
    if db_portfolio:
        raise HTTPException(status_code=400, detail="Portfolio already exists")

    new_portfolio = Portfolio(
        code=portfolio.code,
        name=portfolio.name,
        description=portfolio.description,
        status="draft",
    )
    db.add(new_portfolio)
    db.commit()
    db.refresh(new_portfolio)
    return new_portfolio


@router.get("/{code}", response_model=PortfolioResponse)
def get_portfolio(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.put("/{code}", response_model=PortfolioResponse)
def update_portfolio(
    code: str,
    portfolio: PortfolioUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    db_portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
    if not db_portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    for field, value in portfolio.dict(exclude_unset=True).items():
        setattr(db_portfolio, field, value)

    db.commit()
    db.refresh(db_portfolio)
    return db_portfolio


@router.post("/{code}/close")
def close_portfolio(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if portfolio.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "PORTFOLIO_ALREADY_CLOSED", "message": "组合已关闭"},
        )

    # 检查是否有待处理交易
    pending_subs = (
        db.query(Subscription)
        .filter(Subscription.portfolio_code == code, Subscription.status == "pending")
        .count()
    )
    pending_trades = (
        db.query(Trade)
        .filter(Trade.portfolio_code == code, Trade.status == "pending")
        .count()
    )
    if pending_subs > 0 or pending_trades > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "PENDING_TRANSACTIONS_EXIST",
                "message": "存在待处理交易，需先处理完",
            },
        )

    portfolio.status = "closed"
    portfolio.closed_at = datetime.utcnow()
    db.commit()
    return {"message": "Portfolio closed successfully"}


@router.post("/{code}/reactivate")
def reactivate_portfolio(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if portfolio.status != "closed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "PORTFOLIO_NOT_CLOSED",
                "message": "仅已关闭组合可重新激活",
            },
        )

    portfolio.status = "active"
    portfolio.closed_at = None
    db.commit()
    return {"message": "Portfolio reactivated successfully"}


@router.get("/{code}/nav-history")
def get_nav_history(
    code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    query = db.query(PortfolioValueSnapshot).filter(
        PortfolioValueSnapshot.portfolio_code == code
    )
    if start_date:
        query = query.filter(PortfolioValueSnapshot.snapshot_date >= start_date)
    if end_date:
        query = query.filter(PortfolioValueSnapshot.snapshot_date <= end_date)

    snapshots = query.order_by(PortfolioValueSnapshot.snapshot_date.asc()).all()
    return {
        "portfolio_code": code,
        "data": [
            {
                "date": s.snapshot_date.isoformat(),
                "unit_price": float(s.unit_price),
                "total_value": float(s.total_value),
                "total_shares": float(s.total_shares),
            }
            for s in snapshots
        ],
    }


@router.get("/{code}/returns")
def get_portfolio_returns(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    snapshots = (
        db.query(PortfolioValueSnapshot)
        .filter(PortfolioValueSnapshot.portfolio_code == code)
        .order_by(PortfolioValueSnapshot.snapshot_date.asc())
        .all()
    )

    if not snapshots:
        return {
            "portfolio_code": code,
            "cumulative_return": None,
            "annualized_return": None,
            "initial_nav": None,
            "current_nav": None,
            "holding_days": None,
        }

    initial = snapshots[0]
    current = snapshots[-1]
    initial_nav = float(initial.unit_price)
    current_nav = float(current.unit_price)
    cumulative_return = (current_nav - initial_nav) / initial_nav * 100

    holding_days = (current.snapshot_date - initial.snapshot_date).days
    annualized_return = None
    if holding_days > 0:
        annualized_return = (
            (current_nav / initial_nav) ** (365 / holding_days) - 1
        ) * 100

    return {
        "portfolio_code": code,
        "cumulative_return": round(cumulative_return, 4),
        "annualized_return": round(annualized_return, 4) if annualized_return else None,
        "initial_nav": initial_nav,
        "current_nav": current_nav,
        "holding_days": holding_days,
    }


@router.get("/{code}/cash-flow")
def get_portfolio_cash_flow(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    subs = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == code,
            Subscription.status == "confirmed",
        )
        .all()
    )

    inflow = sum(
        float(s.amount) for s in subs if s.sub_type == "subscribe" and s.amount
    )
    outflow = sum(
        float(s.amount) for s in subs if s.sub_type == "redeem" and s.amount
    )

    return {
        "portfolio_code": code,
        "total_inflow": round(inflow, 4),
        "total_outflow": round(outflow, 4),
        "net_inflow": round(inflow - outflow, 4),
    }
