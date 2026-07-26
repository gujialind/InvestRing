"""持仓管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success
from ir_cli.utils import SUMMARY_FIELDS, build_body, run_list

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_positions(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码"),
    snapshot_date: Optional[str] = typer.Option(None, "--snapshot-date", help="快照日期(YYYY-MM-DD)"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
    all_pages: bool = typer.Option(False, "--all", help="自动翻页获取全部记录"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
    full: bool = typer.Option(False, "--full", help="输出全字段（默认仅摘要字段）"),
):
    """获取持仓列表（默认输出摘要字段，--full 全字段）"""
    client = APIClient.from_config()
    params = build_body(portfolio_code=portfolio_code, snapshot_date=snapshot_date)
    run_list(
        client, "/api/positions", params,
        page=page, page_size=page_size, all_pages=all_pages,
        fields=fields, default_fields=SUMMARY_FIELDS["position"], full=full,
    )


@app.command("get")
def get(id: int = typer.Argument(..., help="持仓ID")):
    """获取单条持仓详情"""
    client = APIClient.from_config()
    result = client.get(f"/api/positions/{id}")
    success(data=result["data"])


@app.command("available-cash")
def available_cash(
    portfolio_code: str = typer.Argument(..., help="组合代码"),
):
    """获取组合可用现金（实时）"""
    client = APIClient.from_config()
    result = client.get(f"/api/positions/portfolio/{portfolio_code}/available-cash")
    success(data=result["data"])


@app.command("available-shares")
def available_shares(
    portfolio_code: str = typer.Argument(..., help="组合代码"),
    product_code: str = typer.Argument(..., help="产品代码"),
    market: Optional[str] = typer.Option(None, "--market", help="市场类型"),
):
    """获取基金可用份额（实时）"""
    client = APIClient.from_config()
    params = {}
    if market is not None:
        params["market"] = market
    result = client.get(
        f"/api/positions/portfolio/{portfolio_code}/product/{product_code}/available-shares",
        params=params,
    )
    success(data=result["data"])


@app.command("update-cash")
def update_cash(
    portfolio_code: str = typer.Argument(..., help="组合代码"),
    platform_code: str = typer.Option(..., "--platform-code", help="平台代码"),
    amount: float = typer.Option(..., "--amount", help="现金金额"),
    update_date: Optional[str] = typer.Option(None, "--update-date", help="更新日期(YYYY-MM-DD)"),
):
    """更新组合现金持仓"""
    client = APIClient.from_config()
    body = {"platform_code": platform_code, "amount": amount}
    if update_date is not None:
        body["update_date"] = update_date
    result = client.post(f"/api/positions/portfolio/{portfolio_code}/cash-position", json_data=body)
    success(data=result["data"])
