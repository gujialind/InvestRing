"""
组合管理服务

组合的创建、更新、关闭/重新激活状态机，以及净值历史/收益率/资金流查询，
从路由层提取供 REST 与 CLI 共用。service 层只抛领域异常，不 commit。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.subscription import Subscription
from app.models.trade import Trade
from app.services.exceptions import BusinessError, NotFoundError


def _get_portfolio_or_404(db: Session, code: str) -> Portfolio:
    portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
    if not portfolio:
        raise NotFoundError("NOT_FOUND", f"组合 {code} 不存在")
    return portfolio


def create_portfolio(
    db: Session,
    *,
    code: str,
    name: str,
    description: Optional[str] = None,
) -> Portfolio:
    """创建组合（初始状态 draft）。不 commit。"""
    if db.query(Portfolio).filter(Portfolio.code == code).first():
        raise BusinessError("ALREADY_EXISTS", f"组合 {code} 已存在", http_status=400)
    portfolio = Portfolio(code=code, name=name, description=description, status="draft")
    db.add(portfolio)
    return portfolio


def update_portfolio(
    db: Session,
    *,
    code: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Portfolio:
    """更新组合信息。不 commit。"""
    portfolio = _get_portfolio_or_404(db, code)
    if name is not None:
        portfolio.name = name
    if description is not None:
        portfolio.description = description
    return portfolio


def close_portfolio(db: Session, code: str) -> Portfolio:
    """关闭组合（存在 pending 交易或已关闭则拒绝）。不 commit。"""
    portfolio = _get_portfolio_or_404(db, code)
    if portfolio.status == "closed":
        raise BusinessError("PORTFOLIO_ALREADY_CLOSED", "组合已关闭")

    pending_subs = db.query(Subscription).filter(
        Subscription.portfolio_code == code, Subscription.status == "pending"
    ).count()
    pending_trades = db.query(Trade).filter(
        Trade.portfolio_code == code, Trade.status == "pending"
    ).count()
    if pending_subs > 0 or pending_trades > 0:
        raise BusinessError(
            "PENDING_TRANSACTIONS_EXIST",
            f"存在待处理交易: {pending_subs} 笔申赎, {pending_trades} 笔调仓",
        )

    portfolio.status = "closed"
    portfolio.closed_at = datetime.utcnow()
    return portfolio


def reactivate_portfolio(db: Session, code: str) -> Portfolio:
    """重新激活已关闭组合（仅 closed 可激活）。不 commit。"""
    portfolio = _get_portfolio_or_404(db, code)
    if portfolio.status != "closed":
        raise BusinessError(
            "PORTFOLIO_NOT_CLOSED",
            f"仅已关闭组合可激活，当前状态: {portfolio.status}",
        )
    portfolio.status = "active"
    portfolio.closed_at = None
    return portfolio


def get_nav_history(
    db: Session,
    code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """查看组合净值历史。"""
    _get_portfolio_or_404(db, code)
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
                "unit_price": float(s.unit_price) if s.unit_price is not None else None,
                "total_value": float(s.total_value) if s.total_value is not None else None,
                "total_shares": float(s.total_shares) if s.total_shares is not None else None,
            }
            for s in snapshots
        ],
    }


def get_returns(db: Session, code: str) -> dict:
    """查看组合收益率（快照不足返回 None 字段）。"""
    _get_portfolio_or_404(db, code)
    snapshots = db.query(PortfolioValueSnapshot).filter(
        PortfolioValueSnapshot.portfolio_code == code
    ).order_by(PortfolioValueSnapshot.snapshot_date.asc()).all()

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
        annualized_return = ((current_nav / initial_nav) ** (365 / holding_days) - 1) * 100

    return {
        "portfolio_code": code,
        "cumulative_return": round(cumulative_return, 4),
        "annualized_return": round(annualized_return, 4) if annualized_return is not None else None,
        "initial_nav": initial_nav,
        "current_nav": current_nav,
        "holding_days": holding_days,
    }


def get_cash_flow(db: Session, code: str) -> dict:
    """查看组合资金流（confirmed 申赎汇总）。"""
    _get_portfolio_or_404(db, code)
    subs = db.query(Subscription).filter(
        Subscription.portfolio_code == code,
        Subscription.status == "confirmed",
    ).all()
    inflow = sum(float(s.amount) for s in subs if s.sub_type == "subscribe" and s.amount)
    outflow = sum(float(s.amount) for s in subs if s.sub_type == "redeem" and s.amount)
    return {
        "portfolio_code": code,
        "total_inflow": round(inflow, 4),
        "total_outflow": round(outflow, 4),
        "net_inflow": round(inflow - outflow, 4),
    }
