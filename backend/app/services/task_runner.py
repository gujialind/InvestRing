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


def run_nav_sync(db: Session, log_id: Optional[int] = None) -> dict:
    """执行净值同步任务（§4.7 四步：基金列表→逐只净值→分红检测→快照生成）。"""
    from app.services.market_data_service import sync_product_prices
    from app.services.snapshot_service import generate_daily_snapshots, auto_confirm_after_snapshot
    from app.models.trading_calendar import TradingCalendar
    from app.models.price_record import PriceRecord
    from sqlalchemy import func

    target_date = (datetime.now().date() - timedelta(days=1))

    products = db.query(Product).filter(
        Product.market.in_(["CN_EXCHANGE", "CN_OTC", "HK_MUTUAL"]),
        Product.data_source.in_(["tushare", "akshare"]),
    ).all()

    if not products:
        return {
            "synced_count": 0,
            "products_count": 0,
            "failed_products": [],
            "snapshots_generated": 0,
            "target_date": target_date.isoformat(),
        }

    total_synced = 0
    failed_products = []

    for product in products:
        try:
            latest = db.query(func.max(PriceRecord.date)).filter(
                PriceRecord.product_code == product.code,
                PriceRecord.market == product.market,
            ).scalar()
            start_date = (latest + timedelta(days=1)) if latest else None

            result = sync_product_prices(
                db=db,
                product_code=product.code,
                market=product.market,
                start_date=start_date,
                end_date=target_date,
            )

            if result["success"]:
                total_synced += result.get("synced_count", 0)
                db.add(NavSyncDetail(
                    task_log_id=log_id,
                    product_code=product.code,
                    market=product.market,
                    nav_date=target_date.strftime("%Y-%m-%d"),
                    status="success",
                    synced_count=result.get("synced_count", 0),
                    source=result.get("source"),
                ))
            else:
                failed_products.append(product.code)
                db.add(NavSyncDetail(
                    task_log_id=log_id,
                    product_code=product.code,
                    market=product.market,
                    nav_date=target_date.strftime("%Y-%m-%d"),
                    status="failed",
                    error_message=result.get("message", "未知错误"),
                ))
        except Exception as e:
            failed_products.append(product.code)
            db.add(NavSyncDetail(
                task_log_id=log_id,
                product_code=product.code,
                market=product.market,
                nav_date=target_date.strftime("%Y-%m-%d"),
                status="failed",
                error_message=str(e)[:500],
            ))

    db.commit()

    dividends_detected = _detect_dividends(db, products)

    snapshots_generated = _generate_snapshots_for_date(db, target_date)

    return {
        "synced_count": total_synced,
        "products_count": len(products),
        "failed_products": failed_products,
        "dividends_detected": dividends_detected,
        "snapshots_generated": snapshots_generated,
        "target_date": target_date.isoformat(),
    }


def _generate_snapshots_for_date(db: Session, target_date) -> int:
    """为 target_date 生成所有活跃组合快照，并复用 auto_confirm_after_snapshot。"""
    from app.services.snapshot_service import generate_daily_snapshots, auto_confirm_after_snapshot
    from app.models.trading_calendar import TradingCalendar

    cal = db.query(TradingCalendar).filter(TradingCalendar.date == target_date).first()
    if not cal or not cal.is_open:
        return 0

    active_portfolios = db.query(Portfolio).filter(Portfolio.status == "active").all()
    count = 0
    for portfolio in active_portfolios:
        try:
            generate_daily_snapshots(db=db, portfolio_code=portfolio.code, target_date=target_date)
            auto_confirm_after_snapshot(db=db, portfolio_code=portfolio.code, snapshot_date=target_date)
            db.commit()
            count += 1
        except Exception as e:
            db.rollback()
            logger.error(f"组合 {portfolio.code} 快照生成失败: {str(e)}")
    return count


def _detect_dividends(db: Session, products: list) -> int:
    """分红检测：从 tushare fund_div 获取分红数据，自动创建 pending reinvest_dividend 事件。"""
    from app.services.tushare_client import get_fund_div, TushareNotConfiguredError, TushareAPIError
    from app.models.share_change_event import ShareChangeEvent
    from app.models.portfolio_position import PortfolioPosition
    from sqlalchemy import func as sa_func, and_

    detected = 0
    otc_products = [p for p in products if p.market == "CN_OTC" and (p.data_source or "tushare") == "tushare"]

    for product in otc_products:
        try:
            ts_code = f"{product.code}.OF"
            dividends = get_fund_div(ts_code)

            for div in dividends:
                if div.get("div_proc") and div["div_proc"] != "实施":
                    continue

                ex_date_str = div.get("ex_date", "")
                record_date_str = div.get("record_date", "")
                if not ex_date_str or not record_date_str:
                    continue

                try:
                    ex_date = datetime.strptime(ex_date_str, "%Y%m%d").date()
                    entitlement_date = datetime.strptime(record_date_str, "%Y%m%d").date()
                except ValueError:
                    continue

                if ex_date <= entitlement_date:
                    continue

                latest_dates = db.query(
                    PortfolioPosition.portfolio_code,
                    sa_func.max(PortfolioPosition.snapshot_date).label("max_date"),
                ).group_by(PortfolioPosition.portfolio_code).subquery()

                positions = db.query(PortfolioPosition).join(
                    latest_dates,
                    and_(
                        PortfolioPosition.portfolio_code == latest_dates.c.portfolio_code,
                        PortfolioPosition.snapshot_date == latest_dates.c.max_date,
                    ),
                ).filter(
                    PortfolioPosition.product_code == product.code,
                    PortfolioPosition.market == product.market,
                    PortfolioPosition.shares > 0,
                ).all()

                for pos in positions:
                    if not pos.platform_code:
                        continue
                    if ex_date <= pos.snapshot_date:
                        continue

                    existing = db.query(ShareChangeEvent).filter(
                        ShareChangeEvent.portfolio_code == pos.portfolio_code,
                        ShareChangeEvent.product_code == product.code,
                        ShareChangeEvent.ex_date == ex_date,
                        ShareChangeEvent.platform_code == pos.platform_code,
                    ).first()

                    if existing:
                        continue

                    event = ShareChangeEvent(
                        portfolio_code=pos.portfolio_code,
                        product_code=product.code,
                        market=product.market,
                        event_type="reinvest_dividend",
                        ex_date=ex_date,
                        entitlement_date=entitlement_date,
                        platform_code=pos.platform_code,
                        event_source="tushare",
                        div_cash=div.get("div_cash"),
                        status="pending",
                        notes=f"自动检测：tushare fund_div {ts_code}",
                    )
                    db.add(event)
                    detected += 1

            db.commit()

        except (TushareNotConfiguredError, TushareAPIError) as e:
            logger.warning(f"分红检测跳过 {product.code}: {e}")
            db.rollback()
        except Exception as e:
            logger.error(f"分红检测失败 {product.code}: {e}")
            db.rollback()

    return detected


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
