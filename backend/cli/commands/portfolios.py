"""
ir portfolio - 组合管理命令组
"""
import typer
from typing import Optional
from datetime import date
from decimal import Decimal
from sqlalchemy import func

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta, parse_date

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_portfolios(
    status: Optional[str] = typer.Option(None, "--status", help="按状态过滤: draft/active/closed"),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
    all: bool = typer.Option(False, "--all"),
):
    """获取组合列表"""
    with cli_context() as db:
        from app.models.portfolio import Portfolio

        query = db.query(Portfolio).order_by(Portfolio.created_at.desc())
        if status:
            query = query.filter(Portfolio.status == status)
        items, total, page, page_size = paginate(query, page, page_size, all)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("create")
def create_portfolio(
    code: str = typer.Option(..., "--code"),
    name: str = typer.Option(..., "--name"),
    description: Optional[str] = typer.Option(None, "--description"),
):
    """创建组合（初始状态 draft）"""
    with cli_context() as db:
        from app.models.portfolio import Portfolio

        existing = db.query(Portfolio).filter(Portfolio.code == code).first()
        if existing:
            error("ALREADY_EXISTS", f"组合 {code} 已存在")

        portfolio = Portfolio(code=code, name=name, description=description, status="draft")
        db.add(portfolio)
        db.flush()
        db.refresh(portfolio)
        success(data=serialize_model(portfolio))


@app.command("get")
def get_portfolio(
    code: str = typer.Argument(...),
):
    """查看组合详情"""
    with cli_context() as db:
        from app.models.portfolio import Portfolio

        portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
        if not portfolio:
            error("NOT_FOUND", f"组合 {code} 不存在")
        success(data=serialize_model(portfolio))


@app.command("update")
def update_portfolio(
    code: str = typer.Argument(...),
    name: Optional[str] = typer.Option(None, "--name"),
    description: Optional[str] = typer.Option(None, "--description"),
):
    """更新组合信息"""
    with cli_context() as db:
        from app.models.portfolio import Portfolio

        portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
        if not portfolio:
            error("NOT_FOUND", f"组合 {code} 不存在")
        if name is not None:
            portfolio.name = name
        if description is not None:
            portfolio.description = description
        db.flush()
        db.refresh(portfolio)
        success(data=serialize_model(portfolio))


@app.command("close")
def close_portfolio(
    code: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes"),
):
    """关闭组合"""
    with cli_context() as db:
        from app.models.portfolio import Portfolio
        from app.models.subscription import Subscription
        from app.models.trade import Trade

        portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
        if not portfolio:
            error("NOT_FOUND", f"组合 {code} 不存在")
        if portfolio.status == "closed":
            error("INVALID_STATUS", "组合已关闭")

        pending_subs = db.query(Subscription).filter(
            Subscription.portfolio_code == code, Subscription.status == "pending"
        ).count()
        pending_trades = db.query(Trade).filter(
            Trade.portfolio_code == code, Trade.status == "pending"
        ).count()
        if pending_subs or pending_trades:
            error("PENDING_TRANSACTIONS_EXIST",
                  f"存在待处理交易: {pending_subs} 笔申赎, {pending_trades} 笔调仓")

        portfolio.status = "closed"
        portfolio.closed_at = date.today()
        db.flush()
        db.refresh(portfolio)
        success(data=serialize_model(portfolio))


@app.command("reactivate")
def reactivate_portfolio(
    code: str = typer.Argument(...),
):
    """重新激活已关闭组合"""
    with cli_context() as db:
        from app.models.portfolio import Portfolio

        portfolio = db.query(Portfolio).filter(Portfolio.code == code).first()
        if not portfolio:
            error("NOT_FOUND", f"组合 {code} 不存在")
        if portfolio.status != "closed":
            error("INVALID_STATUS", f"仅已关闭组合可激活，当前状态: {portfolio.status}")

        portfolio.status = "active"
        portfolio.closed_at = None
        db.flush()
        db.refresh(portfolio)
        success(data=serialize_model(portfolio))


@app.command("nav-history")
def get_nav_history(
    code: str = typer.Argument(...),
    start_date: str = typer.Option(None, "--start-date", help="YYYY-MM-DD"),
    end_date: str = typer.Option(None, "--end-date", help="YYYY-MM-DD"),
):
    """查看组合净值历史"""
    with cli_context() as db:
        from app.models.portfolio_value_snapshot import PortfolioValueSnapshot

        sd = parse_date(start_date) if start_date else None
        ed = parse_date(end_date) if end_date else None
        query = db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == code
        ).order_by(PortfolioValueSnapshot.snapshot_date.asc())
        if sd:
            query = query.filter(PortfolioValueSnapshot.snapshot_date >= sd)
        if ed:
            query = query.filter(PortfolioValueSnapshot.snapshot_date <= ed)

        items = query.all()
        data = [
            {
                "date": s.snapshot_date.isoformat(),
                "unit_price": float(round(s.unit_price, 4)) if s.unit_price else None,
                "total_value": float(round(s.total_value, 2)) if s.total_value else None,
                "total_shares": float(round(s.total_shares, 4)) if s.total_shares else None,
            }
            for s in items
        ]
        success(data={"portfolio_code": code, "data": data})


@app.command("returns")
def get_returns(
    code: str = typer.Argument(...),
):
    """查看组合收益率"""
    with cli_context() as db:
        from app.models.portfolio_value_snapshot import PortfolioValueSnapshot

        snapshots = db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == code
        ).order_by(PortfolioValueSnapshot.snapshot_date.asc()).all()

        if len(snapshots) < 2:
            error("NOT_ENOUGH_DATA", "快照数据不足，需要至少2条快照记录")

        initial_nav = float(snapshots[0].unit_price)
        current_nav = float(snapshots[-1].unit_price)
        holding_days = (snapshots[-1].snapshot_date - snapshots[0].snapshot_date).days

        cumulative_return = (current_nav - initial_nav) / initial_nav * 100
        annualized_return = ((current_nav / initial_nav) ** (365 / max(holding_days, 1)) - 1) * 100

        success(data={
            "portfolio_code": code,
            "cumulative_return": round(cumulative_return, 4),
            "annualized_return": round(annualized_return, 4),
            "initial_nav": initial_nav,
            "current_nav": current_nav,
            "holding_days": holding_days,
        })


@app.command("cash-flow")
def get_cash_flow(
    code: str = typer.Argument(...),
):
    """查看组合资金流"""
    with cli_context() as db:
        from app.models.subscription import Subscription

        inflow = db.query(func.sum(Subscription.amount)).filter(
            Subscription.portfolio_code == code,
            Subscription.sub_type == "subscribe",
            Subscription.status == "confirmed",
        ).scalar() or Decimal("0")

        outflow = db.query(func.sum(Subscription.amount)).filter(
            Subscription.portfolio_code == code,
            Subscription.sub_type == "redeem",
            Subscription.status == "confirmed",
        ).scalar() or Decimal("0")

        success(data={
            "portfolio_code": code,
            "total_inflow": float(round(inflow, 2)),
            "total_outflow": float(round(outflow, 2)),
            "net_inflow": float(round(inflow - outflow, 2)),
        })
