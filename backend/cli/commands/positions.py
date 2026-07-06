"""
ir position - 持仓管理命令组
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
def list_positions(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
    snapshot_date: str = typer.Option(None, "--snapshot-date", help="YYYY-MM-DD"),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
):
    """查看持仓（默认最新快照）"""
    with cli_context() as db:
        from app.models.portfolio_position import PortfolioPosition

        sd = parse_date(snapshot_date) if snapshot_date else None
        query = db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == portfolio_code
        )
        if sd:
            query = query.filter(PortfolioPosition.snapshot_date == sd)
        else:
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
        items, total, page, page_size = paginate(query, page, page_size, False)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("available-cash")
def available_cash(
    portfolio_code: str = typer.Argument(...),
):
    """查看组合可用现金（实时计算）"""
    with cli_context() as db:
        from app.services.position_service import calculate_available_cash

        cash = calculate_available_cash(db, portfolio_code)
        success(data={"portfolio_code": portfolio_code, "available_cash": float(cash)})


@app.command("available-shares")
def available_shares(
    portfolio_code: str = typer.Argument(...),
    product_code: str = typer.Argument(...),
    market: Optional[str] = typer.Option(None, "--market"),
):
    """查看产品可用份额（实时计算）"""
    with cli_context() as db:
        from app.services.position_service import calculate_available_shares

        shares = calculate_available_shares(db, portfolio_code, product_code, market)
        success(data={
            "portfolio_code": portfolio_code,
            "product_code": product_code,
            "market": market,
            "available_shares": float(shares),
        })


@app.command("update-cash")
def update_cash_position(
    portfolio_code: str = typer.Argument(...),
    platform_code: str = typer.Option(..., "--platform-code"),
    amount: float = typer.Option(..., "--amount"),
    update_date: str = typer.Option(None, "--update-date", help="YYYY-MM-DD"),
):
    """更新现金持仓"""
    with cli_context() as db:
        from app.models.portfolio import Portfolio
        from app.models.platform import Platform
        from app.models.portfolio_position import PortfolioPosition
        from app.services.trading_utils import is_trading_day

        portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
        if not portfolio:
            error("NOT_FOUND", "组合不存在")

        platform = db.query(Platform).filter(Platform.code == platform_code).first()
        if not platform:
            error("NOT_FOUND", f"平台 {platform_code} 不存在")

        target_date = parse_date(update_date) if update_date else date.today()
        if not is_trading_day(db, target_date):
            error("NON_TRADING_DAY", "非交易日，请等待交易日再提交")

        cash_pos = db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == portfolio_code,
            PortfolioPosition.product_code == "CASH",
            PortfolioPosition.market == "",
            PortfolioPosition.platform_code == platform_code,
            PortfolioPosition.snapshot_date == target_date,
        ).first()

        if cash_pos:
            cash_pos.amount = Decimal(str(amount))
        else:
            cash_pos = PortfolioPosition(
                portfolio_code=portfolio_code, product_code="CASH",
                market="", platform_code=platform_code,
                amount=Decimal(str(amount)), shares=None,
                snapshot_date=target_date,
            )
            db.add(cash_pos)

        db.flush()
        db.refresh(cash_pos)
        success(data={
            "message": "非净值资产更新成功",
            "portfolio_code": portfolio_code,
            "platform_code": platform_code,
            "amount": float(cash_pos.amount),
            "update_date": target_date.isoformat(),
        })
