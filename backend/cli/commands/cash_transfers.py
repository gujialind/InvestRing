"""
ir cash-transfer - 平台间现金转移命令组
"""
import typer
from typing import Optional
from decimal import Decimal

from cli.context import cli_context
from cli.output import success, error
from cli.utils import parse_date


app = typer.Typer(no_args_is_help=True)


@app.command("create")
def create_cash_transfer(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
    from_platform: str = typer.Option(..., "--from", help="转出平台代码"),
    to_platform: str = typer.Option(..., "--to", help="转入平台代码"),
    amount: float = typer.Option(..., "--amount", help="转移金额"),
    transfer_date: str = typer.Option(..., "--date", help="转出日期 YYYY-MM-DD"),
    cross_day: bool = typer.Option(False, "--cross-day", help="跨天到账（T+1确认）"),
    notes: Optional[str] = typer.Option(None, "--notes"),
):
    """创建平台间现金转移（对称状态模型由服务层统一处理）"""
    with cli_context() as db:
        from app.services.cash_transfer_service import (
            create_cash_transfer as create_transfer_service,
        )

        result = create_transfer_service(
            db,
            portfolio_code=portfolio_code,
            from_platform=from_platform,
            to_platform=to_platform,
            amount=Decimal(str(amount)),
            transfer_date=parse_date(transfer_date),
            cross_day=cross_day,
            notes=notes,
        )
        db.flush()
        success(data=result)


@app.command("list")
def list_cash_transfers(
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
):
    """查询现金转移记录"""
    with cli_context() as db:
        from app.services.cash_transfer_service import (
            list_cash_transfers as list_transfers_service,
        )

        items = list_transfers_service(db, portfolio_code)
        success(data=items, meta={"total": len(items)})


@app.command("confirm")
def confirm_cash_transfer(
    transfer_group: str = typer.Argument(..., help="转移组标识"),
    portfolio_code: str = typer.Option(..., "--portfolio-code"),
):
    """确认跨天转移（对称状态：两腿同时确认）"""
    with cli_context() as db:
        from app.services.cash_transfer_service import (
            confirm_cash_transfer as confirm_transfer_service,
        )

        result = confirm_transfer_service(
            db, portfolio_code=portfolio_code, transfer_group=transfer_group
        )
        db.flush()
        success(data={
            "message": "跨天转移确认成功",
            "transfer_group": result["transfer_group"],
            "confirmed_count": result["confirmed_count"],
            "confirm_date": result["confirm_date"],
        })
