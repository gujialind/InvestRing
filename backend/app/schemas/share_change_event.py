from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class ShareChangeEventBase(BaseModel):
    portfolio_code: str
    event_type: str  # cash_dividend/reinvest_dividend/share_split/share_merge/bonus_share/forced_adjustment
    event_date: date
    entitlement_date: date
    product_code: Optional[str] = None
    market: Optional[str] = None
    shares_before: Optional[float] = None
    shares_change: Optional[float] = None
    shares_after: Optional[float] = None
    cash_change: Optional[float] = None
    div_cash: Optional[float] = None
    reinvest_nav: Optional[float] = None
    ratio: Optional[float] = None
    status: str = "pending"
    notes: Optional[str] = None


class ShareChangeEventCreate(ShareChangeEventBase):
    pass


class ShareChangeEventUpdate(BaseModel):
    event_date: Optional[date] = None
    entitlement_date: Optional[date] = None
    shares_before: Optional[float] = None
    shares_change: Optional[float] = None
    shares_after: Optional[float] = None
    cash_change: Optional[float] = None
    div_cash: Optional[float] = None
    reinvest_nav: Optional[float] = None
    ratio: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ShareChangeEventResponse(ShareChangeEventBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
