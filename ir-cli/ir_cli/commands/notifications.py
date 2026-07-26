"""通知管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import success
from ir_cli.utils import build_body, run_list

app = typer.Typer(no_args_is_help=True)

PREFIX = "/api/system/notifications"


@app.command("list")
def list_notifications(
    status: Optional[str] = typer.Option(None, "--status", help="状态筛选(pending/read)"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
    all_pages: bool = typer.Option(False, "--all", help="自动翻页获取全部记录"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
):
    """获取通知列表"""
    client = APIClient.from_config()
    params = build_body(status=status)
    run_list(client, PREFIX, params, page=page, page_size=page_size, all_pages=all_pages, fields=fields)


@app.command("read")
def read(id: int = typer.Argument(..., help="通知ID")):
    """标记通知为已读"""
    client = APIClient.from_config()
    result = client.post(f"{PREFIX}/{id}/read")
    success(data=result["data"])


@app.command("read-all")
def read_all():
    """标记全部通知为已读"""
    client = APIClient.from_config()
    result = client.post(f"{PREFIX}/read-all")
    success(data=result["data"])
