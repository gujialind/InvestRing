from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.scheduled_task import ScheduledTask
from app.models.task_execution_log import TaskExecutionLog
from app.models.nav_sync_detail import NavSyncDetail
from app.models.product import Product
from app.schemas.task import TaskResponse, TaskExecutionLogResponse
from app.dependencies import get_current_admin
from app.services.trading_calendar_service import sync_trading_calendar
from app.services.market_data_service import sync_price_data, sync_portfolio_nav
from app.models.portfolio import Portfolio

router = APIRouter()


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

    try:
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
    except Exception as e:
        db.rollback()
        raise e


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
        if code == "trading_calendar_sync":
            current_year = datetime.now().year
            result = sync_trading_calendar(db=db, year=current_year)

            task.last_run_at = datetime.now()
            log.status = "success"
            log.finished_at = datetime.now()
            db.commit()

            return {
                "message": f"任务 {code} 执行成功",
                "synced_count": result["synced_count"],
                "year": result["year"],
            }

        elif code == "nav_sync":
            products = db.query(Product).filter(
                Product.market.in_(["CN_EXCHANGE", "CN_OTC"])
            ).all()

            if not products:
                log.status = "success"
                log.finished_at = datetime.now()
                task.last_run_at = datetime.now()
                db.commit()
                return {
                    "message": "净值同步完成",
                    "synced_count": 0,
                    "products_count": 0,
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
                            task_log_id=log.id,
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
                            task_log_id=log.id,
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
                        task_log_id=log.id,
                        product_code=product.code,
                        market=product.market,
                        nav_date=datetime.now().strftime("%Y-%m-%d"),
                        status="failed",
                        error_message=str(e),
                    )
                    db.add(sync_detail)

            task.last_run_at = datetime.now()
            log.status = "success" if not failed_products else "partial_success"
            log.finished_at = datetime.now()
            db.commit()

            # 净值同步完成后，自动触发当日快照生成
            snapshots_generated = 0
            if not failed_products:
                try:
                    from app.services.snapshot_service import generate_daily_snapshots
                    from app.models import TradingCalendar
                    
                    today = datetime.now().date()
                    
                    # 检查今天是否为交易日
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
                "message": f"任务 {code} 执行完成",
                "synced_count": total_synced,
                "products_count": len(products),
                "failed_products": failed_products,
                "snapshots_generated": snapshots_generated,
            }

        elif code == "log_cleanup":
            result = cleanup_old_logs(db)

            task.last_run_at = datetime.now()
            log.status = "success"
            log.finished_at = datetime.now()
            db.commit()

            return {
                "message": f"任务 {code} 执行成功",
                "deleted_logs": result,
            }

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


@router.get("/{code}/logs", response_model=List[TaskExecutionLogResponse])
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
