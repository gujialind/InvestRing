"""
ir log - 日志管理命令组
"""
import typer
from typing import Optional

from cli.context import cli_context
from cli.output import success
from cli.utils import serialize_model, paginate, pagination_meta

app = typer.Typer(no_args_is_help=True)


@app.command("login")
def login_logs(
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
):
    """查询登录日志"""
    with cli_context() as db:
        from app.models.login_log import LoginLog

        query = db.query(LoginLog).order_by(LoginLog.created_at.desc())
        items, total, page, page_size = paginate(query, page, page_size, False)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("audit")
def audit_logs(
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
):
    """查询审计日志"""
    with cli_context() as db:
        from app.models.audit_log import AuditLog

        query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
        items, total, page, page_size = paginate(query, page, page_size, False)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("error")
def error_logs(
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
):
    """查询系统错误日志"""
    with cli_context() as db:
        from app.models.system_error_log import SystemErrorLog

        query = db.query(SystemErrorLog).order_by(SystemErrorLog.created_at.desc())
        items, total, page, page_size = paginate(query, page, page_size, False)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )
