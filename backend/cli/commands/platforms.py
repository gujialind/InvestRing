"""
ir platform - 平台管理命令组
"""
import typer
from typing import Optional

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_platforms(
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
    all: bool = typer.Option(False, "--all"),
):
    """获取平台列表"""
    with cli_context() as db:
        from app.models.platform import Platform

        query = db.query(Platform).order_by(Platform.code)
        items, total, page, page_size = paginate(query, page, page_size, all)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("create")
def create_platform(
    code: str = typer.Option(..., "--code"),
    name: str = typer.Option(..., "--name"),
    platform_type: Optional[str] = typer.Option(None, "--platform-type"),
):
    """创建平台"""
    with cli_context() as db:
        from app.models.platform import Platform

        existing = db.query(Platform).filter(Platform.code == code).first()
        if existing:
            error("ALREADY_EXISTS", f"平台 {code} 已存在")

        platform = Platform(code=code, name=name, platform_type=platform_type)
        db.add(platform)
        db.flush()
        db.refresh(platform)
        success(data=serialize_model(platform))


@app.command("get")
def get_platform(
    code: str = typer.Argument(...),
):
    """查看平台详情"""
    with cli_context() as db:
        from app.models.platform import Platform

        platform = db.query(Platform).filter(Platform.code == code).first()
        if not platform:
            error("NOT_FOUND", f"平台 {code} 不存在")
        success(data=serialize_model(platform))


@app.command("update")
def update_platform(
    code: str = typer.Argument(...),
    name: Optional[str] = typer.Option(None, "--name"),
    platform_type: Optional[str] = typer.Option(None, "--platform-type"),
):
    """更新平台信息"""
    with cli_context() as db:
        from app.models.platform import Platform

        platform = db.query(Platform).filter(Platform.code == code).first()
        if not platform:
            error("NOT_FOUND", f"平台 {code} 不存在")
        if name is not None:
            platform.name = name
        if platform_type is not None:
            platform.platform_type = platform_type
        db.flush()
        db.refresh(platform)
        success(data=serialize_model(platform))


@app.command("delete")
def delete_platform(
    code: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes"),
):
    """删除平台"""
    with cli_context() as db:
        from app.models.platform import Platform

        platform = db.query(Platform).filter(Platform.code == code).first()
        if not platform:
            error("NOT_FOUND", f"平台 {code} 不存在")
        db.delete(platform)
        db.flush()
        success(data={"message": f"平台 {code} 已删除"})
