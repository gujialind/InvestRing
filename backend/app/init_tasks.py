from sqlalchemy.orm import Session
from app.models.scheduled_task import ScheduledTask


def init_scheduled_tasks(db: Session) -> None:
    """
    初始化定时任务数据
    
    确保 3 个核心任务记录存在于数据库中：
    1. nav_sync - 净值同步
    2. trading_calendar_sync - 交易日历同步
    3. log_cleanup - 日志清理

    已存在的记录会同步最新的 name/description 文案，
    保证任务说明随代码演进更新（不覆盖启用状态、运行记录与 cron_expr）。
    """
    tasks = [
        {
            "code": "nav_sync",
            "name": "净值同步",
            "description": (
                "每交易日 07:00 增量同步产品净值，并自动回补当日组合快照；"
                "禁用将导致净值与快照数据中断，估值和收益统计停留在最后一次同步日"
            ),
            "cron_expr": "0 7 * * 1-5",
        },
        {
            "code": "trading_calendar_sync",
            "name": "交易日历同步",
            "description": (
                "每年 1 月 1 日 02:00 同步新年度交易日历；"
                "禁用将导致新年度缺少交易日数据，交易确认日与快照日期推算失败"
            ),
            "cron_expr": "0 2 1 1 *",
        },
        {
            "code": "log_cleanup",
            "name": "日志清理",
            "description": (
                "每周日 04:00 清理超过保留期的系统日志与任务执行日志；"
                "禁用不影响业务数据，但日志表会持续膨胀"
            ),
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
        else:
            existing.name = task_data["name"]
            existing.description = task_data["description"]
            # cron_expr 尊重环境自定义，不随启动重置

    db.commit()
