"""
ir auth - 认证命令组
"""
import typer
from typing import Optional

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model

app = typer.Typer(no_args_is_help=True)


@app.command("create-admin")
def create_admin(
    code: str = typer.Option(..., "--code", help="管理员代码"),
    name: str = typer.Option(..., "--name", help="管理员姓名"),
    password: str = typer.Option(..., "--password", help="密码"),
):
    """创建管理员账户"""
    with cli_context() as db:
        from app.models.investor import Investor
        from app.utils.security import get_password_hash

        existing = db.query(Investor).filter(Investor.code == code).first()
        if existing:
            error("ALREADY_EXISTS", f"用户 {code} 已存在")

        investor = Investor(
            code=code,
            name=name,
            role="admin",
            password_hash=get_password_hash(password),
        )
        db.add(investor)
        db.flush()
        db.refresh(investor)
        success(data=serialize_model(investor, exclude=["password_hash"]))
