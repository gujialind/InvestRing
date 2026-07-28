from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.portfolio import Portfolio
from app.schemas.portfolio import (
    NavHistoryRecord,
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
)
from app.dependencies import get_current_user, get_current_admin
from app.services import portfolio_service

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
    new_portfolio = portfolio_service.create_portfolio(
        db, code=portfolio.code, name=portfolio.name, description=portfolio.description
    )
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
    updates = portfolio.dict(exclude_unset=True)
    db_portfolio = portfolio_service.update_portfolio(
        db, code=code, name=updates.get("name"), description=updates.get("description")
    )
    db.commit()
    db.refresh(db_portfolio)
    return db_portfolio


@router.post("/{code}/close")
def close_portfolio(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    portfolio_service.close_portfolio(db, code)
    db.commit()
    return {"message": "Portfolio closed successfully"}


@router.post("/{code}/reactivate")
def reactivate_portfolio(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    portfolio_service.reactivate_portfolio(db, code)
    db.commit()
    return {"message": "Portfolio reactivated successfully"}


@router.get("/{code}/nav-history", response_model=list[NavHistoryRecord])
def get_nav_history(
    code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return portfolio_service.get_nav_history(db, code, start_date, end_date)


@router.get("/{code}/returns")
def get_portfolio_returns(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return portfolio_service.get_returns(db, code)


@router.get("/{code}/cash-flow")
def get_portfolio_cash_flow(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return portfolio_service.get_cash_flow(db, code)
