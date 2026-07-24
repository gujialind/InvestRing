"""现金转移命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("create")
def create(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    from_platform: str = typer.Option(..., "--from", help="转出平台代码"),
    to_platform: str = typer.Option(..., "--to", help="转入平台代码"),
    amount: float = typer.Option(..., "--amount", help="转移金额"),
    transfer_date: str = typer.Option(..., "--date", help="转出日期(YYYY-MM-DD)"),
    cross_day: bool = typer.Option(False, "--cross-day", help="是否跨天到账"),
    notes: Optional[str] = typer.Option(None, "--notes", help="备注"),
):
    """创建平台间现金转移"""
    client = APIClient.from_config()
    body = {
        "from_platform": from_platform,
        "to_platform": to_platform,
        "amount": amount,
        "transfer_date": transfer_date,
        "cross_day": cross_day,
    }
    if notes is not None:
        body["notes"] = notes
    result = client.post(f"/api/portfolios/{portfolio_code}/cash-transfer", json_data=body)
    success(data=result["data"])


@app.command("list")
def list_transfers(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """获取现金转移列表"""
    client = APIClient.from_config()
    params = {"page": page, "page_size": page_size}
    result = client.get(f"/api/portfolios/{portfolio_code}/cash-transfers", params=params)
    success(data=result["data"], meta=result.get("meta"))


@app.command("confirm")
def confirm(
    transfer_group: str = typer.Argument(..., help="转移组标识"),
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
):
    """确认跨天现金转移（两腿同时确认）"""
    client = APIClient.from_config()
    result = client.post(f"/api/portfolios/{portfolio_code}/cash-transfer/{transfer_group}/confirm")
    success(data=result["data"])
