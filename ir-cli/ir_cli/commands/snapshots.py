"""快照管理命令组（注意前缀为 /api/v1/snapshots）"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success, error

app = typer.Typer(no_args_is_help=True)

PREFIX = "/api/v1/snapshots"


@app.command("generate")
def generate(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    target_date: str = typer.Option(..., "--target-date", help="目标日期(YYYY-MM-DD)"),
):
    """生成单日快照

    \b
    示例:
      ir snapshot generate --portfolio-code PORT001 --target-date 2026-06-05
    """
    client = APIClient.from_config()
    result = client.post(f"{PREFIX}/generate", json_data={
        "portfolio_code": portfolio_code,
        "target_date": target_date,
    })
    success(data=result["data"])


@app.command("recalculate")
def recalculate(
    start_date: str = typer.Option(..., "--start-date", help="开始日期(YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end-date", help="结束日期(YYYY-MM-DD)"),
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码(不传则所有)"),
):
    """区间重算快照"""
    client = APIClient.from_config()
    body = {"start_date": start_date, "end_date": end_date}
    if portfolio_code is not None:
        body["portfolio_code"] = portfolio_code
    result = client.post(f"{PREFIX}/recalculate", json_data=body)
    success(data=result["data"])


@app.command("catch-up")
def catch_up(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    to_date: str = typer.Option(..., "--to-date", help="追平目标日期(YYYY-MM-DD)"),
):
    """逐交易日追平快照至目标日期（逐日 checkpoint，失败日之前的成果保留）"""
    client = APIClient.from_config()
    result = client.post(f"{PREFIX}/catch-up", json_data={
        "portfolio_code": portfolio_code,
        "to_date": to_date,
    })
    success(data=result["data"])


@app.command("generate-next")
def generate_next(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
):
    """生成最新快照日的下一个交易日快照（无需显式指定日期）"""
    client = APIClient.from_config()
    result = client.post(f"{PREFIX}/generate-next", json_data={
        "portfolio_code": portfolio_code,
    })
    success(data=result["data"])


@app.command("validate")
def validate(
    portfolio_code: str = typer.Option(..., "--portfolio-code", help="组合代码"),
    target_date: str = typer.Option(..., "--target-date", help="目标日期(YYYY-MM-DD)"),
):
    """校验快照依赖"""
    client = APIClient.from_config()
    result = client.get(f"{PREFIX}/validation", params={
        "portfolio_code": portfolio_code,
        "target_date": target_date,
    })
    success(data=result["data"])


@app.command("status")
def status(
    portfolio_code: str = typer.Argument(..., help="组合代码"),
):
    """查看快照状态"""
    client = APIClient.from_config()
    result = client.get(f"{PREFIX}/portfolios/{portfolio_code}/status")
    success(data=result["data"])


@app.command("delete")
def delete(
    portfolio_code: str = typer.Argument(..., help="组合代码"),
    snapshot_date: str = typer.Argument(..., help="快照日期(YYYY-MM-DD)"),
):
    """删除指定日期快照"""
    client = APIClient.from_config()
    result = client.delete(f"{PREFIX}/{portfolio_code}/{snapshot_date}")
    success(data=result["data"])


@app.command("delete-bulk")
def delete_bulk(
    portfolio_code: str = typer.Argument(..., help="组合代码"),
    from_date: str = typer.Argument(..., help="起始日期(YYYY-MM-DD)，含当日及之后全部快照"),
    yes: bool = typer.Option(False, "--yes", help="跳过确认，未提供则拒绝执行"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅预览将删除的快照日期，不执行删除"),
):
    """批量删除从 from_date 起（含当日）的所有快照，倒序级联回退"""
    if dry_run:
        # 纯预览（issue #75）：跳过 --yes 校验，零副作用
        client = APIClient.from_config()
        result = client.delete(f"{PREFIX}/{portfolio_code}/bulk/{from_date}", params={"dry_run": True})
        success(
            data=result["data"],
            hints=[f"确认无误后执行: ir snapshot delete-bulk {portfolio_code} {from_date} --yes"],
        )
    if not yes:
        error("CONFIRM_REQUIRED", "批量删除快照不可逆，请追加 --yes 确认，可先用 --dry-run 预览")
    client = APIClient.from_config()
    result = client.delete(f"{PREFIX}/{portfolio_code}/bulk/{from_date}", params={"confirm": True})
    success(data=result["data"])
