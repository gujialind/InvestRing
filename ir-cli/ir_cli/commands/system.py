"""系统管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("calendar")
def calendar(
    year: Optional[int] = typer.Option(None, "--year", help="年份"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="开始日期(YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="结束日期(YYYY-MM-DD)"),
    is_open: Optional[bool] = typer.Option(None, "--is-open/--is-closed", help="是否交易日"),
):
    """查询交易日历"""
    client = APIClient.from_config()
    params = {}
    if year is not None:
        params["year"] = year
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    if is_open is not None:
        params["is_open"] = is_open
    result = client.get("/api/trading-calendar", params=params)
    success(data=result["data"])


@app.command("calendar-sync")
def calendar_sync(
    year: int = typer.Option(..., "--year", help="同步年份"),
):
    """同步交易日历"""
    client = APIClient.from_config()
    result = client.post("/api/trading-calendar/sync", json_data={"year": year})
    success(data=result["data"])


@app.command("datasources")
def datasources():
    """查看数据源配置"""
    client = APIClient.from_config()
    result = client.get("/api/system/data-sources")
    success(data=result["data"])


@app.command("datasource-update")
def datasource_update(
    name: str = typer.Argument(..., help="数据源名称(tushare/akshare)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API Key"),
    is_enabled: Optional[bool] = typer.Option(None, "--is-enabled/--is-disabled", help="是否启用"),
):
    """更新数据源配置"""
    client = APIClient.from_config()
    body = {}
    if api_key is not None:
        body["api_key"] = api_key
    if is_enabled is not None:
        body["is_enabled"] = is_enabled
    result = client.put(f"/api/system/data-sources/{name}", json_data=body)
    success(data=result["data"])
