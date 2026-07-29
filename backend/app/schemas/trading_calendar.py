from pydantic import BaseModel, field_serializer
from datetime import date, datetime
from typing import Optional


class TradingCalendarBase(BaseModel):
    calendar_date: date
    is_open: bool = True


class TradingCalendarCreate(TradingCalendarBase):
    pass


class TradingCalendarResponse(TradingCalendarBase):
    created_at: Optional[datetime] = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")

    class Config:
        from_attributes = True


class TradingCalendarSyncRequest(BaseModel):
    """交易日历同步请求"""
    year: int


class TradingCalendarSyncResponse(BaseModel):
    """交易日历同步响应"""
    synced_count: int
    year: int
    message: str


class TradingDayResponse(BaseModel):
    """交易日偏移查询响应（next/prev）"""
    from_date: date
    trading_day: date


class TradingDayIsOpenResponse(BaseModel):
    """是否交易日查询响应"""
    date: date
    is_open: bool
