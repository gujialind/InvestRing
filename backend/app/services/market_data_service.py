from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.price_record import PriceRecord
from app.models.product import Product
from app.models.portfolio import Portfolio
from app.models.portfolio_position import PortfolioPosition
from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.investor_holding import InvestorHolding
from app.services.tushare_client import get_fund_daily, get_fund_nav, TushareAPIError


def get_price_records(
    db: Session,
    product_code: str,
    market: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: Optional[int] = None,
) -> List[PriceRecord]:
    """
    查询价格记录

    Args:
        db: 数据库会话
        product_code: 产品代码
        market: 市场类型
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        limit: 限制返回数量（可选）

    Returns:
        价格记录列表
    """
    query = db.query(PriceRecord).filter(
        and_(
            PriceRecord.product_code == product_code,
            PriceRecord.market == market,
        )
    )

    if start_date:
        query = query.filter(PriceRecord.date >= start_date)
    if end_date:
        query = query.filter(PriceRecord.date <= end_date)

    query = query.order_by(PriceRecord.date.desc())

    if limit:
        query = query.limit(limit)

    return query.all()


def get_latest_price(
    db: Session,
    product_code: str,
    market: str,
    target_date: Optional[date] = None,
) -> Optional[PriceRecord]:
    """
    获取指定日期或之前的最新价格

    Args:
        db: 数据库会话
        product_code: 产品代码
        market: 市场类型
        target_date: 目标日期，如果为None则获取最新一条

    Returns:
        价格记录或None
    """
    query = db.query(PriceRecord).filter(
        and_(
            PriceRecord.product_code == product_code,
            PriceRecord.market == market,
        )
    )

    if target_date:
        query = query.filter(PriceRecord.date <= target_date)

    return query.order_by(PriceRecord.date.desc()).first()


def sync_product_prices(
    db: Session,
    product_code: str,
    market: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    单产品价格同步（改造版）。
    数据源路由 + 批量 upsert + 禁止硬编码 data_source + sync_error/source 回写。
    返回 {success, synced_count, message, source}
    """
    product = db.query(Product).filter(
        and_(Product.code == product_code, Product.market == market)
    ).first()
    if not product:
        raise ValueError(f"产品 {product_code} ({market}) 不存在")

    if not end_date:
        end_date = date.today()
    start_str = start_date.strftime("%Y%m%d") if start_date else None
    end_str = end_date.strftime("%Y%m%d")

    data_source = product.data_source or "tushare"
    raw_data: List[dict] = []
    try:
        if data_source == "tushare":
            if market == "CN_EXCHANGE":
                raw_data = get_fund_daily(product_code, start_str, end_str)
            elif market == "CN_OTC":
                raw_data = get_fund_nav(product_code, start_str, end_str)
            elif market == "HK_MUTUAL":
                _mark_skipped(db, product, "tushare 不支持 HK_MUTUAL")
                return {"success": True, "synced_count": 0, "message": "跳过：tushare 不支持 HK_MUTUAL", "source": data_source}
            else:
                raise ValueError(f"不支持的 market: {market}")
        elif data_source == "akshare":
            from app.services.akshare_client import (
                get_fund_nav_otc, get_fund_daily_exchange, get_fund_hk_mutual,
                AkshareAPIError,
            )
            if market == "CN_OTC":
                raw_data = get_fund_nav_otc(product_code, start_str, end_str)
            elif market == "CN_EXCHANGE":
                raw_data = get_fund_daily_exchange(product_code, start_str, end_str)
            elif market == "HK_MUTUAL":
                raw_data = get_fund_hk_mutual(product_code, start_str, end_str)
            else:
                _mark_skipped(db, product, f"akshare 不支持 market={market}")
                return {"success": True, "synced_count": 0, "message": "跳过", "source": data_source}
        else:
            _mark_skipped(db, product, f"未实现的数据源: {data_source}")
            return {"success": True, "synced_count": 0, "message": f"跳过：未实现 {data_source}", "source": data_source}
    except (TushareAPIError, Exception) as e:
        _mark_failed(db, product, f"{type(e).__name__}: {e}")
        return {"success": False, "message": str(e), "synced_count": 0, "source": data_source}

    if not raw_data:
        product.data_source_status = "success"
        product.last_sync_at = datetime.utcnow()
        product.sync_error = None
        db.commit()
        return {"success": True, "message": "无新数据", "synced_count": 0, "source": data_source}

    normalized = _normalize_raw(raw_data, market)
    synced_count = _bulk_upsert_prices(db, product_code, market, normalized, data_source)
    db.commit()

    product.data_source_status = "success"
    product.last_sync_at = datetime.utcnow()
    product.sync_error = None
    db.commit()

    return {"success": True, "message": f"同步 {synced_count} 条", "synced_count": synced_count, "source": data_source}


def sync_price_data(
    db: Session,
    product_code: str,
    market: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """向后兼容包装（CLI ir market sync / 现有 router 调用）"""
    return sync_product_prices(db, product_code, market, start_date, end_date)


def _mark_failed(db: Session, product: Product, msg: str):
    product.data_source_status = "failed"
    product.sync_error = msg[:1000] if msg else msg
    product.last_sync_at = datetime.utcnow()
    db.commit()


def _mark_skipped(db: Session, product: Product, reason: str):
    product.data_source_status = "skipped"
    product.sync_error = reason
    product.last_sync_at = datetime.utcnow()
    db.commit()


def _normalize_raw(raw_data: List[dict], market: str) -> List[dict]:
    """统一适配：tushare/akshare 返回 -> {trade_date(YYYYMMDD), unit_price, accumulated_nav, pre_close, pct_change}"""
    seen: dict[str, dict] = {}
    for r in raw_data:
        td = r.get("trade_date")
        if not td:
            continue
        if market == "CN_EXCHANGE":
            seen[td] = {
                "trade_date": td,
                "unit_price": r.get("close"),
                "pre_close": r.get("pre_close"),
                "pct_change": r.get("pct_chg") or r.get("pct_change"),
            }
        else:
            seen[td] = {
                "trade_date": td,
                "unit_price": r.get("unit_nav") or r.get("unit_price"),
                "accumulated_nav": r.get("accum_nav") or r.get("accumulated_nav"),
            }
    return list(seen.values())


def _bulk_upsert_prices(
    db: Session,
    product_code: str,
    market: str,
    rows: List[dict],
    source: str,
) -> int:
    """批量 upsert。MySQL 用 ON DUPLICATE KEY UPDATE，SQLite 用 ORM fallback（测试环境）。"""
    from sqlalchemy import text

    if not rows:
        return 0

    values = []
    for r in rows:
        td = r["trade_date"]
        d = date(int(td[:4]), int(td[4:6]), int(td[6:8]))
        values.append({
            "product_code": product_code,
            "market": market,
            "date": d,
            "unit_price": r.get("unit_price"),
            "accumulated_nav": r.get("accumulated_nav"),
            "pre_close": r.get("pre_close"),
            "pct_change": r.get("pct_change"),
            "source": source,
        })

    if db.bind.dialect.name == "mysql":
        sql = text("""
            INSERT INTO price_record (product_code, market, date, unit_price, accumulated_nav, pre_close, pct_change, source)
            VALUES (:product_code, :market, :date, :unit_price, :accumulated_nav, :pre_close, :pct_change, :source)
            ON DUPLICATE KEY UPDATE
              unit_price=VALUES(unit_price), accumulated_nav=VALUES(accumulated_nav),
              pre_close=VALUES(pre_close), pct_change=VALUES(pct_change), source=VALUES(source)
        """)
        db.execute(sql, values)
    else:
        for v in values:
            existing = db.query(PriceRecord).filter_by(
                product_code=v["product_code"], market=v["market"], date=v["date"]
            ).first()
            if existing:
                for k in ("unit_price", "accumulated_nav", "pre_close", "pct_change", "source"):
                    setattr(existing, k, v[k])
            else:
                db.add(PriceRecord(**v))

    return len(values)


def sync_portfolio_nav(
    db: Session,
    portfolio_code: str,
) -> Dict[str, Any]:
    """
    同步组合净值

    根据持仓和最新价格重新计算组合净值

    Args:
        db: 数据库会话
        portfolio_code: 组合代码

    Returns:
        同步结果
    """
    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise ValueError(f"组合 {portfolio_code} 不存在")

    if portfolio.status != "active":
        return {"success": False, "message": "组合未激活，无法同步净值"}

    positions = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == portfolio_code
    ).all()

    if not positions:
        return {"success": False, "message": "组合无持仓，无法计算净值"}

    total_value = 0.0
    total_shares = 0.0

    for position in positions:
        if position.asset_type == "cash":
            total_value += float(position.amount or 0)
            continue

        latest_price = get_latest_price(
            db, position.product_code, position.market
        )

        if latest_price:
            position_value = float(position.shares or 0) * float(latest_price.unit_price)
            total_value += position_value

    latest_snapshot = db.query(PortfolioValueSnapshot).filter(
        PortfolioValueSnapshot.portfolio_code == portfolio_code
    ).order_by(PortfolioValueSnapshot.snapshot_date.desc()).first()

    if latest_snapshot:
        total_shares = float(latest_snapshot.total_shares)
    else:
        total_shares = total_value

    if total_shares == 0:
        return {"success": False, "message": "组合份额为0，无法计算净值"}

    unit_price = total_value / total_shares

    today = date.today()

    existing_snapshot = db.query(PortfolioValueSnapshot).filter(
        and_(
            PortfolioValueSnapshot.portfolio_code == portfolio_code,
            PortfolioValueSnapshot.snapshot_date == today,
        )
    ).first()

    if existing_snapshot:
        existing_snapshot.total_value = total_value
        existing_snapshot.total_shares = total_shares
        existing_snapshot.unit_price = unit_price
    else:
        new_snapshot = PortfolioValueSnapshot(
            portfolio_code=portfolio_code,
            snapshot_date=today,
            total_value=total_value,
            total_shares=total_shares,
            unit_price=unit_price,
        )
        db.add(new_snapshot)

    db.commit()

    return {
        "success": True,
        "message": "组合净值已更新",
        "total_value": total_value,
        "total_shares": total_shares,
        "unit_price": unit_price,
    }


# ==================== 后台任务编排（P3.1） ====================

import threading
from concurrent.futures import ThreadPoolExecutor
from app.config import get_settings

_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


class ConflictError(Exception):
    """已有同步任务在运行中"""
    pass


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=get_settings().sync_worker_count,
                    thread_name_prefix="price-sync",
                )
    return _executor


def submit_price_sync_job(
    params: dict,
    triggered_by: str = "manual",
    db: Optional[Session] = None,
) -> int:
    """提交价格同步后台任务，立即返回 job_id。单 active 锁：已有 pending/running job 则抛 ConflictError。"""
    from app.database import SessionLocal
    from app.models.sync_job import SyncJob

    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        active = db.query(SyncJob).filter(SyncJob.status.in_(["pending", "running"])).count()
        if active > 0:
            raise ConflictError("已有价格同步任务在运行中")

        job = SyncJob(
            job_type=params.get("job_type", "price_history_sync"),
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

    _get_executor().submit(_run_price_sync_job_impl, job_id)
    return job_id


def _run_price_sync_job_impl(job_id: int):
    """后台线程执行体：每个线程独立 Session。"""
    from app.database import SessionLocal
    from app.models.sync_job import SyncJob
    from app.models.nav_sync_detail import NavSyncDetail
    from sqlalchemy import func as sa_func

    db = SessionLocal()
    try:
        job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not job:
            return
        params = job.params or {}
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        scope = params.get("scope", "all")
        if scope == "by_product":
            target = params.get("products", [])
            from sqlalchemy import or_, and_
            conditions = [and_(Product.code == c, Product.market == m) for c, m in target]
            if conditions:
                products = db.query(Product).filter(or_(*conditions)).all()
            else:
                products = []
        else:
            ds_filter = [Product.data_source.in_(["tushare", "akshare"])]
            if params.get("data_source"):
                ds_filter = [Product.data_source == params["data_source"]]
            products = db.query(Product).filter(
                Product.market.in_(["CN_EXCHANGE", "CN_OTC", "HK_MUTUAL"]),
                *ds_filter,
            ).all()

        job.total = len(products)
        db.commit()

        for product in products:
            try:
                start_date = None
                if params.get("job_type") == "price_incremental_sync":
                    latest = db.query(sa_func.max(PriceRecord.date)).filter(
                        PriceRecord.product_code == product.code,
                        PriceRecord.market == product.market,
                    ).scalar()
                    if latest:
                        start_date = latest + timedelta(days=1)
                elif params.get("start_date"):
                    start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date()

                end_date = None
                if params.get("end_date"):
                    end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date()
                else:
                    end_date = date.today() - timedelta(days=1)

                result = sync_product_prices(
                    db=db,
                    product_code=product.code,
                    market=product.market,
                    start_date=start_date,
                    end_date=end_date,
                )

                status = "success" if result["success"] else "failed"
                db.add(NavSyncDetail(
                    job_id=job_id,
                    product_code=product.code,
                    market=product.market,
                    nav_date=end_date.strftime("%Y-%m-%d"),
                    status=status,
                    synced_count=result.get("synced_count", 0),
                    source=result.get("source"),
                    error_message=None if status == "success" else result.get("message"),
                ))
                if status == "success":
                    job.success_count += 1
                else:
                    job.failed_count += 1
            except Exception as e:
                db.add(NavSyncDetail(
                    job_id=job_id,
                    product_code=product.code,
                    market=product.market,
                    nav_date=date.today().strftime("%Y-%m-%d"),
                    status="failed",
                    error_message=str(e)[:500],
                ))
                job.failed_count += 1
            job.done += 1
            db.commit()

        if job.failed_count == 0:
            job.status = "success"
        elif job.success_count > 0:
            job.status = "partial"
        else:
            job.status = "failed"
        job.finished_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        try:
            job.status = "failed"
            job.error_message = str(e)[:1000]
            job.finished_at = datetime.utcnow()
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


def recover_orphan_jobs():
    """启动时扫描 status='running' 的 sync_job，标记为 interrupted。"""
    from app.database import SessionLocal
    from app.models.sync_job import SyncJob

    db = SessionLocal()
    try:
        orphans = db.query(SyncJob).filter(SyncJob.status == "running").all()
        for job in orphans:
            job.status = "interrupted"
            job.error_message = (job.error_message or "") + " [启动时标记为 interrupted：可能上次崩溃遗留]"
            job.finished_at = datetime.utcnow()
        db.commit()
        return len(orphans)
    finally:
        db.close()