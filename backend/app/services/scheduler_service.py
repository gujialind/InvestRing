"""APScheduler 定时调度服务。

多 worker 互斥：用 MySQL GET_LOCK 确保每日定时任务只在一个进程中执行。
两条独立每日 job（issue #156 剥离）：daily_nav_sync（净值同步+分红检测）与
daily_snapshot_generate（组合快照生成，仅处理开启 auto_snapshot_enabled 的
活跃组合），均直接调 task_runner 执行体，不走 sync_job 路径。
"""
import logging
from datetime import date, timedelta

from app.config import get_settings

logger = logging.getLogger(__name__)

_scheduler = None


def init_scheduler():
    """应用启动时调用：初始化 scheduler + 注册每日 job + 孤儿恢复。"""
    global _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor as APSThreadPool

    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("调度器已禁用 (scheduler_enabled=False)")
        return

    _scheduler = BackgroundScheduler(
        jobstores={
            "default": SQLAlchemyJobStore(
                url=settings.database_url,
                tablename=settings.scheduler_jobstore_table,
            )
        },
        executors={
            "default": APSThreadPool(max_workers=2),
        },
        timezone="Asia/Shanghai",
    )
    _scheduler.start()

    _scheduler.add_job(
        _trigger_daily_nav_sync,
        trigger="cron",
        **_parse_cron(settings.scheduler_cron_daily),
        id="daily_nav_sync",
        replace_existing=True,
        jobstore="default",
    )

    _scheduler.add_job(
        _trigger_daily_snapshot_generate,
        trigger="cron",
        **_parse_cron(settings.scheduler_cron_snapshot),
        id="daily_snapshot_generate",
        replace_existing=True,
        jobstore="default",
    )

    from app.services.market_data_service import recover_orphan_jobs
    recovered = recover_orphan_jobs()
    if recovered:
        logger.info(f"恢复 {recovered} 个孤儿 running job -> interrupted")


def _trigger_daily_nav_sync():
    """APScheduler 触发体：GET_LOCK 互斥 → 交易日判断 → 直接调 run_nav_sync。"""
    from app.database import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        result = db.execute(text("SELECT GET_LOCK('daily_nav_sync_lock', 0)")).scalar()
        if not result or result == 0:
            logger.info("另一个进程已持有 daily_nav_sync_lock，跳过")
            return

        today = date.today()
        from app.models.trading_calendar import TradingCalendar
        cal = db.query(TradingCalendar).filter(TradingCalendar.calendar_date == today).first()
        if not cal or not cal.is_open:
            logger.info(f"{today} 非交易日，跳过每日净值同步")
            return

        from app.services.task_runner import run_nav_sync
        result = run_nav_sync(db, log_id=None)
        logger.info(f"每日净值同步完成: {result.get('synced_count', 0)} 条")
    except Exception as e:
        logger.error(f"每日净值同步失败: {e}", exc_info=True)
    finally:
        db.execute(text("SELECT RELEASE_LOCK('daily_nav_sync_lock')"))
        db.close()


def _trigger_daily_snapshot_generate():
    """APScheduler 触发体：GET_LOCK 互斥 → 交易日判断 → 直接调 run_snapshot_generate。"""
    from app.database import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        result = db.execute(text("SELECT GET_LOCK('snapshot_generate_lock', 0)")).scalar()
        if not result or result == 0:
            logger.info("另一个进程已持有 snapshot_generate_lock，跳过")
            return

        today = date.today()
        from app.models.trading_calendar import TradingCalendar
        cal = db.query(TradingCalendar).filter(TradingCalendar.calendar_date == today).first()
        if not cal or not cal.is_open:
            logger.info(f"{today} 非交易日，跳过每日快照生成")
            return

        from app.services.task_runner import run_snapshot_generate
        result = run_snapshot_generate(db, log_id=None)
        logger.info(f"每日快照生成完成: {result.get('snapshots_generated', 0)} 个")
    except Exception as e:
        logger.error(f"每日快照生成失败: {e}", exc_info=True)
    finally:
        db.execute(text("SELECT RELEASE_LOCK('snapshot_generate_lock')"))
        db.close()


def shutdown_scheduler():
    """应用关闭时调用。"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _parse_cron(cron_str: str) -> dict:
    """'0 7 * * *' -> {minute:0, hour:7, day:'*', month:'*', day_of_week:'*'}"""
    parts = cron_str.split()
    keys = ["minute", "hour", "day", "month", "day_of_week"]
    return {k: v for k, v in zip(keys, parts)}
