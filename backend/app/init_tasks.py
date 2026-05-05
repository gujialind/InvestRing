from sqlalchemy.orm import Session
from app.models.scheduled_task import ScheduledTask


def init_scheduled_tasks(db: Session) -> None:
    """
    初始化定时任务数据
    
    确保 3 个核心任务记录存在于数据库中：
    1. nav_sync - 净值同步
    2. trading_calendar_sync - 交易日历同步
    3. log_cleanup - 日志清理
    """
    tasks = [
        {
            "code": "nav_sync",
            "name": "净值同步",
            "description": "每个交易日 07:00 同步净值数据（增量同步）",
            "cron_expr": "0 7 * * 1-5",
        },
        {
            "code": "trading_calendar_sync",
            "name": "交易日历同步",
            "description": "每年 1 月 1 日 02:00 同步新年交易日历",
            "cron_expr": "0 2 1 1 *",
        },
        {
            "code": "log_cleanup",
            "name": "日志清理",
            "description": "每周日 04:00 清理过期日志",
            "cron_expr": "0 4 * * 0",
        },
    ]

    for task_data in tasks:
        existing = db.query(ScheduledTask).filter(
            ScheduledTask.code == task_data["code"]
        ).first()

        if not existing:
            task = ScheduledTask(**task_data)
            db.add(task)

    db.commit()
