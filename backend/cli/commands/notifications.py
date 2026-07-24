"""
ir notification - 通知管理命令组
"""
import typer
from typing import Optional
from datetime import datetime

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_notifications(
    status: Optional[str] = typer.Option(None, "--status", help="状态筛选(pending/read)"),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
    all: bool = typer.Option(False, "--all"),
):
    """获取通知列表（管理上下文，返回全部收件人）"""
    with cli_context() as db:
        from app.models.notification import Notification

        query = db.query(Notification).order_by(Notification.created_at.desc())
        if status:
            query = query.filter(Notification.status == status)
        items, total, page, page_size = paginate(query, page, page_size, all)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("read")
def read_notification(
    id: int = typer.Argument(...),
):
    """标记通知为已读"""
    with cli_context() as db:
        from app.models.notification import Notification

        notification = db.query(Notification).filter(Notification.id == id).first()
        if not notification:
            error("NOT_FOUND", f"通知 {id} 不存在")
        notification.status = "read"
        notification.read_at = datetime.utcnow()
        db.flush()
        success(data={"message": "通知已标记为已读", "id": id})


@app.command("read-all")
def read_all_notifications():
    """标记全部通知为已读"""
    with cli_context() as db:
        from app.models.notification import Notification

        count = db.query(Notification).filter(Notification.status != "read").update(
            {"status": "read", "read_at": datetime.utcnow()},
            synchronize_session=False,
        )
        db.flush()
        success(data={"message": "全部通知已标记为已读", "updated_count": count})
