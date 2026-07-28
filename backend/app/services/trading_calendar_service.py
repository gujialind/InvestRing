from datetime import date, datetime
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.trading_calendar import TradingCalendar
from app.services.tushare_client import (
    get_trade_calendar,
    TushareNotConfiguredError,
    TushareAPIError,
)


def sync_trading_calendar(db: Session, year: int) -> Dict[str, Any]:
    """
    同步指定年份的交易日历到数据库

    Args:
        db: 数据库会话
        year: 年份，如 2026

    Returns:
        同步结果，包含 synced_count 和 year
        例如: {"synced_count": 244, "year": 2026}

    Raises:
        TushareNotConfiguredError: Tushare token 未配置
        TushareAPIError: API 调用失败

    Note:
        本函数不 commit（AGENTS.md §4.1），事务边界交调用方。
    """
    # 从 Tushare 获取交易日历数据
    calendar_data = get_trade_calendar(year)

    if not calendar_data:
        return {"synced_count": 0, "year": year}

    # 查询数据库中已存在的日期
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    existing_dates = {
        row[0]
        for row in db.query(TradingCalendar.calendar_date)
        .filter(and_(TradingCalendar.calendar_date >= start_date, TradingCalendar.calendar_date <= end_date))
        .all()
    }

    # 过滤出需要新增的日期
    new_records = []
    for item in calendar_data:
        item_date = date.fromisoformat(item["date"])
        if item_date not in existing_dates:
            new_records.append({
                "calendar_date": item_date,
                "is_open": item["is_open"],
            })

    # 批量插入新记录（commit 交调用方）
    if new_records:
        db.bulk_insert_mappings(TradingCalendar, new_records)
        db.flush()

    return {
        "synced_count": len(new_records),
        "year": year,
    }


def get_calendar_query(
    db: Session,
    year: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_open: Optional[bool] = None,
):
    """
    构建交易日历查询

    Args:
        db: 数据库会话
        year: 按年份过滤
        start_date: 开始日期
        end_date: 结束日期
        is_open: 是否开盘

    Returns:
        SQLAlchemy Query 对象
    """
    query = db.query(TradingCalendar)

    if year is not None:
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        query = query.filter(
            and_(TradingCalendar.calendar_date >= year_start, TradingCalendar.calendar_date <= year_end)
        )

    if start_date is not None:
        query = query.filter(TradingCalendar.calendar_date >= start_date)

    if end_date is not None:
        query = query.filter(TradingCalendar.calendar_date <= end_date)

    if is_open is not None:
        query = query.filter(TradingCalendar.is_open == is_open)

    return query.order_by(TradingCalendar.calendar_date)


def is_trading_day(db: Session, target_date: date) -> bool:
    """
    判断指定日期是否为交易日

    Args:
        db: 数据库会话
        target_date: 目标日期

    Returns:
        True 如果是交易日，False  otherwise
    """
    cal = db.query(TradingCalendar).filter(TradingCalendar.calendar_date == target_date).first()
    if not cal:
        return False
    return cal.is_open
