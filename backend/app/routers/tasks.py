from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.scheduled_task import ScheduledTask
from app.models.task_execution_log import TaskExecutionLog
from app.schemas.task import (
    TaskResponse,
    TaskExecutionLogResponse,
    TaskDetailResponse,
    PaginatedTaskLogResponse,
)
from app.dependencies import get_current_admin
from app.services.trading_calendar_service import sync_trading_calendar

router = APIRouter()


@router.get("")
def get_tasks(
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    query = db.query(ScheduledTask)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{code}/run")
def run_task(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    task = db.query(ScheduledTask).filter(ScheduledTask.code == code).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.is_enabled:
        raise HTTPException(status_code=400, detail="Task is disabled")

    log = TaskExecutionLog(
        task_code=code,
        trigger_type="manual",
        status="running",
        started_at=datetime.now(),
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    try:
        from app.services.task_runner import run_nav_sync, run_calendar_sync, run_log_cleanup

        if code == "trading_calendar_sync":
            result = run_calendar_sync(db)
            task.last_run_at = datetime.now()
            log.status = "success"
            log.finished_at = datetime.now()
            db.commit()
            return {"message": f"任务 {code} 执行成功", **result}

        elif code == "nav_sync":
            result = run_nav_sync(db, log.id)
            task.last_run_at = datetime.now()
            log.status = "success" if not result.get("failed_products") else "partial_success"
            log.finished_at = datetime.now()
            db.commit()
            return {"message": f"任务 {code} 执行完成", **result}

        elif code == "log_cleanup":
            result = run_log_cleanup(db)
            task.last_run_at = datetime.now()
            log.status = "success"
            log.finished_at = datetime.now()
            db.commit()
            return {"message": f"任务 {code} 执行成功", "deleted_logs": result}

        else:
            log.status = "failed"
            log.finished_at = datetime.now()
            log.error_message = f"未知任务: {code}"
            db.commit()
            raise HTTPException(status_code=404, detail=f"未知任务: {code}")

    except HTTPException:
        raise
    except Exception as e:
        log.status = "failed"
        log.finished_at = datetime.now()
        log.error_message = str(e)
        task.last_run_at = datetime.now()
        db.commit()
        raise HTTPException(status_code=500, detail=f"任务执行失败: {str(e)}")


@router.post("/{code}/enable")
def enable_task(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    task = db.query(ScheduledTask).filter(ScheduledTask.code == code).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_enabled = True
    db.commit()
    return {"message": f"Task {code} enabled"}


@router.post("/{code}/disable")
def disable_task(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    task = db.query(ScheduledTask).filter(ScheduledTask.code == code).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_enabled = False
    db.commit()
    return {"message": f"Task {code} disabled"}


@router.get("/{code}/logs", response_model=PaginatedTaskLogResponse)
def get_task_logs(
    code: str,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    query = (
        db.query(TaskExecutionLog)
        .filter(TaskExecutionLog.task_code == code)
        .order_by(TaskExecutionLog.created_at.desc())
    )

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{code}", response_model=TaskDetailResponse)
def get_task(
    code: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """查看任务详情：任务全字段 + 最近一次执行记录（last_execution 可为 null）"""
    task = db.query(ScheduledTask).filter(ScheduledTask.code == code).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    last_execution = (
        db.query(TaskExecutionLog)
        .filter(TaskExecutionLog.task_code == code)
        .order_by(TaskExecutionLog.created_at.desc(), TaskExecutionLog.id.desc())
        .first()
    )

    return TaskDetailResponse(
        **TaskResponse.model_validate(task).model_dump(),
        last_execution=(
            TaskExecutionLogResponse.model_validate(last_execution)
            if last_execution
            else None
        ),
    )
