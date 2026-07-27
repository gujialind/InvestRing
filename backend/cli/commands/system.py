"""
ir system - 系统管理命令组
"""
import typer
from typing import Optional

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta, parse_date

app = typer.Typer(no_args_is_help=True)


@app.command("calendar")
def get_calendar(
    year: Optional[int] = typer.Option(None, "--year"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="YYYY-MM-DD"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="YYYY-MM-DD"),
    is_open: Optional[bool] = typer.Option(None, "--is-open"),
):
    """查询交易日历"""
    with cli_context() as db:
        from app.models.trading_calendar import TradingCalendar

        query = db.query(TradingCalendar).order_by(TradingCalendar.date)
        if year:
            query = query.filter(TradingCalendar.date >= f"{year}-01-01",
                                 TradingCalendar.date <= f"{year}-12-31")
        if start_date:
            query = query.filter(TradingCalendar.date >= parse_date(start_date))
        if end_date:
            query = query.filter(TradingCalendar.date <= parse_date(end_date))
        if is_open is not None:
            query = query.filter(TradingCalendar.is_open == is_open)

        items = query.all()
        success(data=[serialize_model(i) for i in items])


@app.command("calendar-sync")
def sync_calendar(
    year: int = typer.Option(..., "--year"),
):
    """同步交易日历（Tushare）"""
    with cli_context() as db:
        from app.services.trading_calendar_service import sync_trading_calendar

        result = sync_trading_calendar(db, year)
        success(data=result)


@app.command("datasources")
def list_datasources():
    """查看数据源配置（API key 脱敏）"""
    with cli_context() as db:
        from app.config import get_settings

        settings = get_settings()
        token = settings.tushare_token

        masked = ""
        if token:
            if len(token) > 8:
                masked = token[:4] + "*" * (len(token) - 8) + token[-4:]
            else:
                masked = token[:2] + "***"

        success(data={
            "tushare": {"token": masked, "configured": bool(token)},
        })


@app.command("datasource-update")
def update_datasource(
    name: str = typer.Argument(..., help="tushare/akshare"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    is_enabled: Optional[bool] = typer.Option(None, "--is-enabled"),
):
    """更新数据源配置"""
    with cli_context() as db:
        import os
        from app.config import get_settings

        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

        if name == "tushare" and api_key:
            # 更新 .env 文件中的 TUSHARE_TOKEN
            lines = []
            found = False
            if os.path.exists(env_file):
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for i, line in enumerate(lines):
                    if line.startswith("TUSHARE_TOKEN="):
                        lines[i] = f"TUSHARE_TOKEN={api_key}\n"
                        found = True
                        break
            if not found:
                lines.append(f"\nTUSHARE_TOKEN={api_key}\n")
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

            get_settings.cache_clear()
            success(data={"message": f"Tushare token 已更新"})
        else:
            error("INVALID_DATASOURCE", f"不支持的数据源: {name}")
