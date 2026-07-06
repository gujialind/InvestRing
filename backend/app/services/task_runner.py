"""
定时任务执行体

从 routers/tasks.py 提取的任务执行逻辑，供 CLI 和 router 共用。
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.scheduled_task import ScheduledTask
from app.models.task_execution_log import TaskExecutionLog
from app.models.nav_sync_detail import NavSyncDetail
from app.models.product import Product
from app.models.portfolio import Portfolio

logger = logging.getLogger(__name__)


def cleanup_old_logs(db: Session) -> dict:
    """
    清理过期日志

    清理策略：
    - 登录日志：保留 30 天
    - 审计日志：保留 90 天
    - 任务执行日志：保留 90 天
    - 净值同步明细：保留 90 天
    - 系统错误日志：保留 30 天
    """
    from app.models.login_log import LoginLog
    from app.models.audit_log import AuditLog
    from app.models.system_error_log import SystemErrorLog

    cutoff_login = datetime.now() - timedelta(days=30)
    cutoff_audit = datetime.now() - timedelta(days=90)
    cutoff_task = datetime.now() - timedelta(days=90)
    cutoff_error = datetime.now() - timedelta(days=30)

    deleted = {
        "login_logs": 0,
        "audit_logs": 0,
        "task_logs": 0,
        "error_logs": 0,
    }

    deleted["login_logs"] = db.query(LoginLog).filter(
        LoginLog.created_at < cutoff_login
    ).delete()

    deleted["audit_logs"] = db.query(AuditLog).filter(
        AuditLog.created_at < cutoff_audit
    ).delete()

    deleted["task_logs"] = db.query(TaskExecutionLog).filter(
        TaskExecutionLog.created_at < cutoff_task
    ).delete()

    deleted["error_logs"] = db.query(SystemErrorLog).filter(
        SystemErrorLog.created_at < cutoff_error
    ).delete()

    db.commit()
    return deleted


def run_nav_sync(db: Session, log_id: int) -> dict:
    """执行净值同步任务"""
    from app.services.market_data_service import sync_price_data
    from app.services.snapshot_service import generate_daily_snapshots
    from app.models.trading_calendar import TradingCalendar

    products = db.query(Product).filter(
        Product.market.in_(["CN_EXCHANGE", "CN_OTC"])
    ).all()

    if not products:
        return {
            "synced_count": 0,
            "products_count": 0,
            "failed_products": [],
            "snapshots_generated": 0,
        }

    total_synced = 0
    failed_products = []

    for product in products:
        try:
            result = sync_price_data(
                db=db,
                product_code=product.code,
                market=product.market,
                start_date=(datetime.now() - timedelta(days=7)).date(),
                end_date=datetime.now().date(),
            )

            if result["success"]:
                total_synced += result.get("synced_count", 0)
                sync_detail = NavSyncDetail(
                    task_log_id=log_id,
                    product_code=product.code,
                    market=product.market,
                    nav_date=datetime.now().strftime("%Y-%m-%d"),
                    status="success",
                    nav_value=0,
                )
                db.add(sync_detail)
            else:
                failed_products.append(product.code)
                sync_detail = NavSyncDetail(
                    task_log_id=log_id,
                    product_code=product.code,
                    market=product.market,
                    nav_date=datetime.now().strftime("%Y-%m-%d"),
                    status="failed",
                    error_message=result.get("message", "未知错误"),
                )
                db.add(sync_detail)

        except Exception as e:
            failed_products.append(product.code)
            sync_detail = NavSyncDetail(
                task_log_id=log_id,
                product_code=product.code,
                market=product.market,
                nav_date=datetime.now().strftime("%Y-%m-%d"),
                status="failed",
                error_message=str(e),
            )
            db.add(sync_detail)

    db.commit()

    # 净值同步完成后，自动触发当日快照生成
    snapshots_generated = 0
    if not failed_products:
        try:
            today = datetime.now().date()
            cal = db.query(TradingCalendar).filter(
                TradingCalendar.date == today
            ).first()

            if cal and cal.is_open:
                active_portfolios = db.query(Portfolio).filter(
                    Portfolio.status == "active"
                ).all()

                for portfolio in active_portfolios:
                    try:
                        generate_daily_snapshots(
                            db=db,
                            portfolio_code=portfolio.code,
                            target_date=today
                        )
                        snapshots_generated += 1
                    except Exception as e:
                        logger.error(f"组合 {portfolio.code} 快照生成失败: {str(e)}")
        except Exception as e:
            logger.error(f"自动快照生成失败: {str(e)}")

    return {
        "synced_count": total_synced,
        "products_count": len(products),
        "failed_products": failed_products,
        "snapshots_generated": snapshots_generated,
    }


def run_calendar_sync(db: Session, year: Optional[int] = None) -> dict:
    """执行交易日历同步任务"""
    from app.services.trading_calendar_service import sync_trading_calendar

    if year is None:
        year = datetime.now().year

    result = sync_trading_calendar(db=db, year=year)
    return {
        "synced_count": result["synced_count"],
        "year": result["year"],
    }


def run_log_cleanup(db: Session) -> dict:
    """执行日志清理任务"""
    return cleanup_old_logs(db)
