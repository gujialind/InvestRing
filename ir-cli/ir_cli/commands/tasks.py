"""任务管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success
from ir_cli.utils import run_list

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_tasks(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
    all_pages: bool = typer.Option(False, "--all", help="自动翻页获取全部记录"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
):
    """获取任务列表"""
    client = APIClient.from_config()
    run_list(client, "/api/system/tasks", page=page, page_size=page_size, all_pages=all_pages, fields=fields)


@app.command("describe")
def describe(code: str = typer.Argument(..., help="任务代码")):
    """查看任务详情（含作用说明与最近一次执行记录）"""
    client = APIClient.from_config()
    result = client.get(f"/api/system/tasks/{code}")
    success(data=result["data"])


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
    all_pages: bool = typer.Option(False, "--all", help="自动翻页获取全部记录"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
):
    """查看任务执行日志"""
    client = APIClient.from_config()
    run_list(client, f"/api/system/tasks/{code}/logs", page=page, page_size=page_size, all_pages=all_pages, fields=fields)
