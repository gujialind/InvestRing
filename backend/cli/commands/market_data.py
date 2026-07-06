"""
ir market - 市场数据命令组
"""
import typer
from typing import Optional

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, parse_date

app = typer.Typer(no_args_is_help=True)


@app.command("price")
def get_price(
    product_code: str = typer.Argument(...),
    market: str = typer.Argument(...),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="YYYY-MM-DD"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="YYYY-MM-DD"),
    limit: int = typer.Option(50, "--limit"),
):
    """查询产品价格数据"""
    with cli_context() as db:
        from app.services.market_data_service import get_price_records

        sd = parse_date(start_date) if start_date else None
        ed = parse_date(end_date) if end_date else None
        records = get_price_records(
            db, product_code, market, sd, ed, limit
        )
        success(data=[serialize_model(r) for r in records])


@app.command("sync")
def sync_price(
    product_code: str = typer.Argument(...),
    market: str = typer.Argument(...),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="YYYY-MM-DD"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="YYYY-MM-DD"),
):
    """同步产品价格数据（Tushare）"""
    with cli_context() as db:
        from app.services.market_data_service import sync_price_data

        sd = parse_date(start_date) if start_date else None
        ed = parse_date(end_date) if end_date else None
        result = sync_price_data(db, product_code, market, sd, ed)
        if result.get("success"):
            success(data=result)
        else:
            error("DATA_SOURCE_ERROR", result.get("message", "同步失败"))


@app.command("sync-history")
def sync_history(
    product_code: str = typer.Argument(...),
    market: str = typer.Argument(...),
):
    """同步产品近90天历史数据"""
    with cli_context() as db:
        from datetime import date, timedelta
        from app.services.market_data_service import sync_price_data

        end_date = date.today()
        start_date = end_date - timedelta(days=90)
        result = sync_price_data(db, product_code, market, start_date, end_date)
        if result.get("success"):
            success(data=result)
        else:
            error("DATA_SOURCE_ERROR", result.get("message", "同步失败"))


@app.command("sync-nav")
def sync_nav(
    portfolio_code: str = typer.Argument(...),
):
    """同步组合净值"""
    with cli_context() as db:
        from app.services.market_data_service import sync_portfolio_nav

        result = sync_portfolio_nav(db, portfolio_code)
        success(data=result)
