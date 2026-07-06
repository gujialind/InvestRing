"""
交易相关公共工具函数

从 routers 层提取的共享函数，供 CLI 和 router 共用。
"""
from datetime import date
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
from app.models.trading_calendar import TradingCalendar


def is_trading_day(db: Session, target_date: date) -> bool:
    """判断指定日期是否为交易日"""
    cal = db.query(TradingCalendar).filter(TradingCalendar.date == target_date).first()
    if not cal:
        return False
    return cal.is_open


def get_next_trading_day(db: Session, from_date: date, days: int = 1) -> Optional[date]:
    """
    获取 from_date 之后第 days 个交易日
    days=1 表示 T+1，days=0 表示当天
    """
    next_date = from_date
    for _ in range(max(days, 0)):
        next_date = (
            db.query(func.min(TradingCalendar.date))
            .filter(
                TradingCalendar.date > next_date,
                TradingCalendar.is_open == True,
            )
            .scalar()
        )
        if not next_date:
            break
    return next_date or from_date


def get_prev_trading_day(db: Session, from_date: date, days: int = 1) -> Optional[date]:
    """获取前 N 个交易日"""
    prev_date = from_date
    for _ in range(max(days, 0)):
        prev_date = (
            db.query(func.max(TradingCalendar.date))
            .filter(
                TradingCalendar.date < prev_date,
                TradingCalendar.is_open == True,
            )
            .scalar()
        )
        if not prev_date:
            break
    return prev_date or from_date


def get_latest_snapshot_date(db: Session, portfolio_code: str) -> Optional[date]:
    """获取组合最新快照日期"""
    result = (
        db.query(func.max(PortfolioValueSnapshot.snapshot_date))
        .filter(PortfolioValueSnapshot.portfolio_code == portfolio_code)
        .scalar()
    )
    return result
