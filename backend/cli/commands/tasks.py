"""
ir task - 任务管理命令组
"""
import typer
from typing import Optional
from datetime import datetime

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_tasks(
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
):
    """获取定时任务列表"""
    with cli_context() as db:
        from app.models.scheduled_task import ScheduledTask

        query = db.query(ScheduledTask)
        items, total, page, page_size = paginate(query, page, page_size, False)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("describe")
def describe_task(
    code: str = typer.Argument(...),
):
    """查看任务详情（含作用说明与最近一次执行记录）"""
    with cli_context() as db:
        from app.models.scheduled_task import ScheduledTask
        from app.models.task_execution_log import TaskExecutionLog

        task = db.query(ScheduledTask).filter(ScheduledTask.code == code).first()
        if not task:
            error("NOT_FOUND", f"任务 {code} 不存在")

        last_execution = (
            db.query(TaskExecutionLog)
            .filter(TaskExecutionLog.task_code == code)
            .order_by(TaskExecutionLog.created_at.desc(), TaskExecutionLog.id.desc())
            .first()
        )

        data = serialize_model(task)
        data["last_execution"] = serialize_model(last_execution) if last_execution else None
        success(data=data)


@app.command("run")
def run_task(
    code: str = typer.Argument(...),
):
    """手动执行任务（nav_sync/trading_calendar_sync/log_cleanup）"""
    with cli_context() as db:
        from app.models.scheduled_task import ScheduledTask
        from app.models.task_execution_log import TaskExecutionLog
        from app.services.task_runner import run_nav_sync, run_calendar_sync, run_log_cleanup

        task = db.query(ScheduledTask).filter(ScheduledTask.code == code).first()
        if not task:
            error("NOT_FOUND", f"任务 {code} 不存在")

        log = TaskExecutionLog(
            task_code=code, trigger_type="manual",
            status="running", started_at=datetime.now(),
        )
        db.add(log)
        db.flush()
        db.refresh(log)

        try:
            if code == "trading_calendar_sync":
                result = run_calendar_sync(db)
            elif code == "nav_sync":
                result = run_nav_sync(db, log.id)
            elif code == "log_cleanup":
                result = run_log_cleanup(db)
            else:
                error("INVALID_TASK", f"不支持的任务: {code}")
                return

            task.last_run_at = datetime.now()
            log.status = "success"
            log.finished_at = datetime.now()
            db.flush()

            success(data={
                "message": f"任务 {code} 执行成功",
                "task_code": code,
                "result": result,
            })

        except Exception as e:
            log.status = "failed"
            log.finished_at = datetime.now()
            log.error_message = str(e)
            task.last_run_at = datetime.now()
            db.flush()
            error("TASK_FAILED", f"任务执行失败: {str(e)}")


@app.command("enable")
def enable_task(
    code: str = typer.Argument(...),
):
    """启用任务"""
    with cli_context() as db:
        from app.models.scheduled_task import ScheduledTask

        task = db.query(ScheduledTask).filter(ScheduledTask.code == code).first()
        if not task:
            error("NOT_FOUND", f"任务 {code} 不存在")
        task.is_enabled = True
        db.flush()
        success(data={"message": f"任务 {code} 已启用", "task": serialize_model(task)})


@app.command("disable")
def disable_task(
    code: str = typer.Argument(...),
):
    """禁用任务"""
    with cli_context() as db:
        from app.models.scheduled_task import ScheduledTask

        task = db.query(ScheduledTask).filter(ScheduledTask.code == code).first()
        if not task:
            error("NOT_FOUND", f"任务 {code} 不存在")
        task.is_enabled = False
        db.flush()
        success(data={"message": f"任务 {code} 已禁用", "task": serialize_model(task)})


@app.command("logs")
def task_logs(
    code: str = typer.Argument(...),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
):
    """查看任务执行日志"""
    with cli_context() as db:
        from app.models.task_execution_log import TaskExecutionLog

        query = db.query(TaskExecutionLog).filter(
            TaskExecutionLog.task_code == code
        ).order_by(TaskExecutionLog.created_at.desc())
        items, total, page, page_size = paginate(query, page, page_size, False)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )
