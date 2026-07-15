"""同步任务命令组"""
import typer
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("status")
def status(
    job_id: int = typer.Argument(..., help="任务ID"),
):
    """查询同步任务状态"""
    client = APIClient.from_config()
    result = client.get(f"/api/sync-jobs/{job_id}")
    success(data=result["data"])


@app.command("details")
def details(
    job_id: int = typer.Argument(..., help="任务ID"),
):
    """查询同步任务逐产品明细"""
    client = APIClient.from_config()
    result = client.get(f"/api/sync-jobs/{job_id}/details")
    success(data=result["data"])
