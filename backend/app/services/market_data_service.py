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


def sync_price_data(
    db: Session,
    product_code: str,
    market: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    同步产品价格数据

    Args:
        db: 数据库会话
        product_code: 产品代码
        market: 市场类型
        start_date: 开始日期，不传则从有数据以来全部同步
        end_date: 结束日期，默认今天

    Returns:
        同步结果统计
    """
    product = db.query(Product).filter(
        and_(
            Product.code == product_code,
            Product.market == market,
        )
    ).first()

    if not product:
        raise ValueError(f"产品 {product_code} ({market}) 不存在")

    if not end_date:
        end_date = date.today()

    start_str = start_date.strftime("%Y%m%d") if start_date else None
    end_str = end_date.strftime("%Y%m%d")

    raw_data = []
    error_detail = None
    try:
        if market == "CN_EXCHANGE":
            raw_data = get_fund_daily(product_code, start_str, end_str)
        elif market == "CN_OTC":
            raw_data = get_fund_nav(product_code, start_str, end_str)
        else:
            raise ValueError(f"不支持的市场类型: {market}")
    except TushareAPIError as e:
        return {"success": False, "message": str(e), "synced_count": 0}
    except Exception as e:
        return {"success": False, "message": f"数据获取异常: {type(e).__name__}: {e}", "synced_count": 0}

    if not raw_data:
        return {
            "success": True,
            "message": f"无新数据需要同步（{start_str or 'beginning'}~{end_str}，共 0 条）",
            "synced_count": 0,
        }

    # 去重：Tushare 可能返回同一天多条记录，保留最后一条
    seen_dates: dict[str, dict] = {}
    for record in raw_data:
        td = record.get("trade_date")
        if td:
            seen_dates[td] = record
    raw_data = list(seen_dates.values())

    synced_count = 0
    try:
        # 一次性加载该产品在该市场的所有已有记录到内存字典
        filters = [
            PriceRecord.product_code == product_code,
            PriceRecord.market == market,
            PriceRecord.date <= end_date,
        ]
        if start_date:
            filters.append(PriceRecord.date >= start_date)
        existing_records = db.query(PriceRecord).filter(and_(*filters)).all()
        existing_map: dict[date, PriceRecord] = {r.date: r for r in existing_records}

        for record in raw_data:
            trade_date_str = record.get("trade_date")
            if not trade_date_str:
                continue

            trade_date = datetime.strptime(trade_date_str, "%Y%m%d").date()

            if market == "CN_EXCHANGE":
                unit_price = record.get("close")
            else:
                unit_price = record.get("unit_nav")

            if not unit_price:
                continue

            existing = existing_map.get(trade_date)
            if existing:
                existing.unit_price = unit_price
                if market == "CN_EXCHANGE":
                    existing.pre_close = record.get("pre_close")
                    existing.pct_change = record.get("pct_chg")
                elif market == "CN_OTC":
                    existing.accumulated_nav = record.get("accum_nav")
                existing.source = "tushare"
            else:
                new_record = PriceRecord(
                    product_code=product_code,
                    market=market,
                    date=trade_date,
                    unit_price=unit_price,
                    source="tushare",
                )
                if market == "CN_EXCHANGE":
                    new_record.pre_close = record.get("pre_close")
                    new_record.pct_change = record.get("pct_chg")
                elif market == "CN_OTC":
                    new_record.accumulated_nav = record.get("accum_nav")
                db.add(new_record)

            synced_count += 1

        db.commit()
    except Exception as e:
        db.rollback()
        product.data_source_status = "failed"
        db.commit()
        return {"success": False, "message": f"数据写入异常: {type(e).__name__}: {e}", "synced_count": 0}

    product.data_source_status = "success"
    product.data_source = "tushare"
    product.last_sync_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "message": f"成功同步 {synced_count} 条价格数据",
        "synced_count": synced_count,
    }


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



