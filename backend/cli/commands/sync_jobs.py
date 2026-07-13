"""
ir sync-job - 价格同步任务命令组
"""
import typer

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model

app = typer.Typer(no_args_is_help=True)


@app.command("status")
def status(job_id: int = typer.Argument(...)):
    """查询同步任务状态与进度"""
    with cli_context() as db:
        from app.models.sync_job import SyncJob
        job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not job:
            error("NOT_FOUND", f"任务 {job_id} 不存在")
        success(data=serialize_model(job))


@app.command("details")
def details(job_id: int = typer.Argument(...)):
    """查询同步任务逐产品明细"""
    with cli_context() as db:
        from app.models.sync_job import SyncJob
        from app.models.nav_sync_detail import NavSyncDetail
        job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not job:
            error("NOT_FOUND", f"任务 {job_id} 不存在")
        items = db.query(NavSyncDetail).filter(NavSyncDetail.job_id == job_id).all()
        success(data={
            "job": serialize_model(job),
            "details": [serialize_model(i) for i in items],
        })
