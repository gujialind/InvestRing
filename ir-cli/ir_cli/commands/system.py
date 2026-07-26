"""系统管理命令组"""
import typer
from typing import Optional
from ir_cli import config
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)

# 整年日历基本不变，本地缓存 7 天，calendar-sync 后自动失效
CALENDAR_CACHE_TTL = 7 * 86400


@app.command("calendar")
def calendar(
    year: Optional[int] = typer.Option(None, "--year", help="年份"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="开始日期(YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="结束日期(YYYY-MM-DD)"),
    is_open: Optional[bool] = typer.Option(None, "--is-open/--is-closed", help="是否交易日"),
    no_cache: bool = typer.Option(False, "--no-cache", help="跳过本地缓存直接请求后端"),
):
    """查询交易日历（按年整年查询时使用本地缓存，--no-cache 可绕过）"""
    # 仅缓存无其他筛选条件的整年查询（结果稳定且命中率高）
    cacheable = year is not None and start_date is None and end_date is None and is_open is None
    cache_key = f"calendar_{year}"
    if cacheable and not no_cache:
        cached = config.load_cache(cache_key, CALENDAR_CACHE_TTL)
        if cached is not None:
            success(data=cached, meta={"cached": True})

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
    if cacheable:
        config.save_cache(cache_key, result["data"])
    success(data=result["data"])


@app.command("calendar-sync")
def calendar_sync(
    year: int = typer.Option(..., "--year", help="同步年份"),
):
    """同步交易日历（成功后自动失效对应年份的本地缓存）"""
    client = APIClient.from_config()
    result = client.post("/api/trading-calendar/sync", json_data={"year": year})
    config.clear_cache(f"calendar_{year}")
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
