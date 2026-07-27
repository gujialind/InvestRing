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
    """同步产品完整历史数据（从有数据以来）"""
    with cli_context() as db:
        from datetime import date
        from app.services.market_data_service import sync_price_data

        end_date = date.today()
        result = sync_price_data(db, product_code, market, None, end_date)
        if result.get("success"):
            success(data=result)
        else:
            error("DATA_SOURCE_ERROR", result.get("message", "同步失败"))


@app.command("sync-all")
def sync_all(
    start_date: Optional[str] = typer.Option(None, "--start-date", help="YYYY-MM-DD 历史回填起点"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="YYYY-MM-DD，默认昨天"),
    scope: str = typer.Option("all", "--scope", help="all|by-product"),
    products: Optional[str] = typer.Option(None, "--products", help="逗号分隔 code|market 对，如 000051.OF|CN_OTC"),
):
    """提交批量价格同步后台任务（立即返回 job_id）"""
    with cli_context() as db:
        from app.services.market_data_service import submit_price_sync_job, ConflictError

        prod_list = []
        if products:
            for pair in products.split(","):
                code, _, mkt = pair.partition("|")
                prod_list.append([code.strip(), mkt.strip()])

        params = {
            "job_type": "price_history_sync" if start_date else "price_incremental_sync",
            "start_date": start_date,
            "end_date": end_date,
            "scope": scope,
            "products": prod_list,
        }
        try:
            job_id = submit_price_sync_job(params, triggered_by="manual", db=db)
            success(data={"job_id": job_id, "message": "任务已提交，用 ir sync-job status <id> 查看进度"})
        except ConflictError:
            error("CONFLICT", "已有价格同步任务在运行中")
