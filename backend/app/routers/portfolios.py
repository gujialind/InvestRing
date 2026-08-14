from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.portfolio import Portfolio
from app.schemas.portfolio import (
    NavHistoryRecord,
    PaginatedPortfolioResponse,
    PortfolioCreate,
    PortfolioInvestorItem,
    PortfolioPerformance,
    PortfolioUpdate,
    PortfolioResponse,
    PortfolioValueSnapshotResponse,
)
from app.dependencies import get_current_user, get_current_admin
from app.services import performance_service, portfolio_service

router = APIRouter()


@router.get("", response_model=PaginatedPortfolioResponse)
def get_portfolios(
    status: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return portfolio_service.list_portfolios(db, status=status, page=page, page_size=page_size)


@router.post("", response_model=PortfolioResponse)
def create_portfolio(
    portfolio: PortfolioCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    new_portfolio = portfolio_service.create_portfolio(
        db,
        code=portfolio.code,
        name=portfolio.name,
        description=portfolio.description,
        display_config=portfolio.display_config,
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
    # 并入读侧派生字段（issue #99）：total_value / total_profit，无快照时为 None
    totals = portfolio_service._derive_portfolio_totals(db, code)
    portfolio.total_value = totals["total_value"]
    portfolio.total_profit = totals["total_profit"]
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
        db,
        code=code,
        name=updates.get("name"),
        description=updates.get("description"),
        # display_config 区分「不传 = 不修改」与「显式 null = 清空」（issue #144）
        display_config=(
            updates["display_config"]
            if "display_config" in updates
            else portfolio_service.UNSET
        ),
        auto_snapshot_enabled=updates.get("auto_snapshot_enabled"),
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


@router.get("/{code}/snapshots/latest", response_model=PortfolioValueSnapshotResponse)
def get_latest_snapshot(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return portfolio_service.get_latest_value_snapshot(db, code)


@router.get("/{code}/investors", response_model=list[PortfolioInvestorItem])
def get_portfolio_investors(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return portfolio_service.get_portfolio_investors(db, code)


@router.get("/{code}/returns")
def get_portfolio_returns(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return portfolio_service.get_returns(db, code)


@router.get("/{code}/performance", response_model=PortfolioPerformance)
def get_portfolio_performance(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """组合绩效全指标：TWR / MWR(XIRR) / 区间收益 / 最大回撤 / 年化波动率。

    与 /returns 的关系：/returns 保留为轻量口径（累计+年化）供列表页复用，
    本端点提供详情页所需的全量绩效与风险指标。
    """
    return performance_service.get_performance(db, code)


@router.get("/{code}/cash-flow")
def get_portfolio_cash_flow(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return portfolio_service.get_cash_flow(db, code)
