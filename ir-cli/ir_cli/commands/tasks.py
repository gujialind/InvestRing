"""任务管理命令组"""
import typer
from ir_cli.client import APIClient
from ir_cli.output import success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_tasks(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """获取任务列表"""
    client = APIClient.from_config()
    result = client.get("/api/system/tasks", params={"page": page, "page_size": page_size})
    success(data=result["data"], meta=result.get("meta"))


@app.command("run")
def run(code: str = typer.Argument(..., help="任务代码")):
    """手动执行任务"""
    client = APIClient.from_config()
    result = client.post(f"/api/system/tasks/{code}/run")
    success(data=result["data"])


@app.command("enable")
def enable(code: str = typer.Argument(..., help="任务代码")):
    """启用任务"""
    client = APIClient.from_config()
    result = client.post(f"/api/system/tasks/{code}/enable")
    success(data=result["data"])


@app.command("disable")
def disable(code: str = typer.Argument(..., help="任务代码")):
    """禁用任务"""
    client = APIClient.from_config()
    result = client.post(f"/api/system/tasks/{code}/disable")
    success(data=result["data"])


@app.command("logs")
def logs(
    code: str = typer.Argument(..., help="任务代码"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
):
    """查看任务执行日志"""
    client = APIClient.from_config()
    result = client.get(f"/api/system/tasks/{code}/logs", params={"page": page, "page_size": page_size})
    success(data=result["data"], meta=result.get("meta"))
