"""
快照重算后台任务编排（issue #89）

复用 sync_job 表与 market_data_service 的线程池：
- submit_snapshot_recalc_job：落 job 记录（job_type=snapshot_recalc）并提交后台线程，
  立即返回 job_id，客户端经 GET /api/sync-jobs/{id} 轮询终态，消除 HTTP 超时后
  「已提交成功 or 已整体回滚」不可判定的问题。
- 后台执行体自持 SessionLocal（backend/AGENTS.md「分层目录与职责」节的分层例外），保持 recalculate_snapshots
  的单一事务语义：无 errors 统一 commit、任一日失败整体 rollback。

锁语义：snapshot_recalc 与价格同步任务互不阻塞，各自单 active 锁。
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.services.market_data_service import ConflictError, _get_executor
from app.services.snapshot_service import recalculate_snapshots

logger = logging.getLogger(__name__)

JOB_TYPE = "snapshot_recalc"


def submit_snapshot_recalc_job(
    params: dict,
    triggered_by: str = "manual",
    db: Optional[Session] = None,
) -> int:
    """提交快照重算后台任务，立即返回 job_id。

    params: {portfolio_code?: str, start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD"}
    单 active 锁（仅同类型）：已有 pending/running 的 snapshot_recalc job 抛 ConflictError。
    """
    from app.database import SessionLocal
    from app.models.sync_job import SyncJob

    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        active = db.query(SyncJob).filter(
            SyncJob.job_type == JOB_TYPE,
            SyncJob.status.in_(["pending", "running"]),
        ).count()
        if active > 0:
            raise ConflictError("已有快照重算任务在运行中")

        job = SyncJob(
            job_type=JOB_TYPE,
            status="pending",
            params=params,
            triggered_by=triggered_by,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        if own_db:
            db.close()

    _get_executor().submit(_run_snapshot_recalc_job_impl, job_id)
    return job_id


def _run_snapshot_recalc_job_impl(job_id: int, db: Optional[Session] = None):
    """后台线程执行体：自持 Session（db 参数仅供测试注入）。

    保持单一事务语义：recalculate_snapshots 全程不 commit，
    本执行体按 errors 决定统一 commit / rollback（与 REST 同步路径一致）。
    job 状态的写入与业务事务分离（业务 rollback 后再落 job 终态）。
    """
    from datetime import date as _date
    from app.database import SessionLocal
    from app.models.sync_job import SyncJob

    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not job:
            return
        params = job.params or {}
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        try:
            result = recalculate_snapshots(
                db=db,
                portfolio_code=params.get("portfolio_code"),
                start_date=_date.fromisoformat(params["start_date"]),
                end_date=_date.fromisoformat(params["end_date"]),
            )
        except Exception as e:
            # 预校验失败（ValueError）或意外异常：整体回滚，job 记 failed
            db.rollback()
            job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
            job.status = "failed"
            job.error_message = str(e)[:1000]
            job.finished_at = datetime.utcnow()
            db.commit()
            return

        error_entries = [e for r in result["results"] for e in r["errors"]]
        processed = sum(r["total_processed"] for r in result["results"])

        if error_entries:
            # 任一日失败：整体回滚业务事务（被删快照与级联回退完整复原）
            db.rollback()
            job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
            job.status = "failed"
            job.error_message = "; ".join(
                f"{e['date']}: {e['error']}" for e in error_entries
            )[:1000]
        else:
            db.commit()
            job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
            job.status = "success"

        job.total = processed + len(error_entries)
        job.done = processed + len(error_entries)
        job.success_count = processed
        job.failed_count = len(error_entries)
        job.finished_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        logger.error(f"快照重算任务 {job_id} 执行异常: {e}")
        try:
            db.rollback()
            job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)[:1000]
                job.finished_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        if own_db:
            db.close()
