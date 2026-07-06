"""市场数据命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("price")
def price(
    code: str = typer.Argument(..., help="产品代码"),
    market: str = typer.Argument(..., help="市场类型(CN_EXCHANGE/CN_OTC)"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="开始日期(YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="结束日期(YYYY-MM-DD)"),
    limit: int = typer.Option(30, "--limit", help="返回条数"),
):
    """查询产品价格数据"""
    client = APIClient.from_config()
    params = {"limit": limit}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    result = client.get(f"/api/market-data/products/{code}/{market}/price-data", params=params)
    success(data=result["data"])


@app.command("sync")
def sync(
    code: str = typer.Argument(..., help="产品代码"),
    market: str = typer.Argument(..., help="市场类型"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="开始日期(YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="结束日期(YYYY-MM-DD)"),
):
    """同步产品价格数据"""
    client = APIClient.from_config()
    body = {}
    if start_date is not None:
        body["start_date"] = start_date
    if end_date is not None:
        body["end_date"] = end_date
    result = client.post(f"/api/market-data/products/{code}/{market}/sync-price-data", json_data=body)
    success(data=result["data"])


@app.command("sync-history")
def sync_history(
    code: str = typer.Argument(..., help="产品代码"),
    market: str = typer.Argument(..., help="市场类型"),
):
    """同步产品完整历史数据"""
    client = APIClient.from_config()
    result = client.post(f"/api/market-data/products/{code}/{market}/sync-history")
    success(data=result["data"])


@app.command("sync-nav")
def sync_nav(
    portfolio_code: str = typer.Argument(..., help="组合代码"),
):
    """同步组合净值"""
    client = APIClient.from_config()
    result = client.post(f"/api/market-data/portfolios/{portfolio_code}/sync-nav")
    success(data=result["data"])
