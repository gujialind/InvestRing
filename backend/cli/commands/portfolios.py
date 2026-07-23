"""
ir portfolio - 组合管理命令组
"""
import typer
from typing import Optional

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
        from app.services import portfolio_service

        portfolio = portfolio_service.create_portfolio(
            db, code=code, name=name, description=description
        )
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
        from app.services import portfolio_service

        portfolio = portfolio_service.update_portfolio(
            db, code=code, name=name, description=description
        )
        db.flush()
        db.refresh(portfolio)
        success(data=serialize_model(portfolio))


@app.command("close")
def close_portfolio(
    code: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes"),
):
    """关闭组合（存在 pending 交易则拒绝）"""
    with cli_context() as db:
        from app.services import portfolio_service

        portfolio = portfolio_service.close_portfolio(db, code)
        db.flush()
        db.refresh(portfolio)
        success(data=serialize_model(portfolio))


@app.command("reactivate")
def reactivate_portfolio(
    code: str = typer.Argument(...),
):
    """重新激活已关闭组合"""
    with cli_context() as db:
        from app.services import portfolio_service

        portfolio = portfolio_service.reactivate_portfolio(db, code)
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
        from app.services import portfolio_service

        result = portfolio_service.get_nav_history(
            db,
            code,
            parse_date(start_date) if start_date else None,
            parse_date(end_date) if end_date else None,
        )
        success(data=result)


@app.command("returns")
def get_returns(
    code: str = typer.Argument(...),
):
    """查看组合收益率"""
    with cli_context() as db:
        from app.services import portfolio_service

        success(data=portfolio_service.get_returns(db, code))


@app.command("cash-flow")
def get_cash_flow(
    code: str = typer.Argument(...),
):
    """查看组合资金流"""
    with cli_context() as db:
        from app.services import portfolio_service

        success(data=portfolio_service.get_cash_flow(db, code))
