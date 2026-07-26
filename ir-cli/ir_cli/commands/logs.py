"""日志管理命令组"""
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.utils import SUMMARY_FIELDS, run_list

app = typer.Typer(no_args_is_help=True)


@app.command("login")
def login_logs(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
    all_pages: bool = typer.Option(False, "--all", help="自动翻页获取全部记录"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
    full: bool = typer.Option(False, "--full", help="输出全字段（默认仅摘要字段）"),
):
    """查看登录日志（默认输出摘要字段，--full 全字段）"""
    client = APIClient.from_config()
    run_list(
        client, "/api/system/logs/login",
        page=page, page_size=page_size, all_pages=all_pages,
        fields=fields, default_fields=SUMMARY_FIELDS["log_login"], full=full,
    )


@app.command("audit")
def audit_logs(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
    all_pages: bool = typer.Option(False, "--all", help="自动翻页获取全部记录"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
    full: bool = typer.Option(False, "--full", help="输出全字段（默认仅摘要字段）"),
):
    """查看审计日志（默认输出摘要字段，--full 全字段）"""
    client = APIClient.from_config()
    run_list(
        client, "/api/system/logs/audit",
        page=page, page_size=page_size, all_pages=all_pages,
        fields=fields, default_fields=SUMMARY_FIELDS["log_audit"], full=full,
    )


@app.command("error")
def error_logs(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
    all_pages: bool = typer.Option(False, "--all", help="自动翻页获取全部记录"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
    full: bool = typer.Option(False, "--full", help="输出全字段（默认仅摘要字段）"),
):
    """查看错误日志（默认输出摘要字段，--full 全字段）"""
    client = APIClient.from_config()
    run_list(
        client, "/api/system/logs/error",
        page=page, page_size=page_size, all_pages=all_pages,
        fields=fields, default_fields=SUMMARY_FIELDS["log_error"], full=full,
    )
