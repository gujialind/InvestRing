from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class PositionBase(BaseModel):
    portfolio_code: str
    product_code: str
    market: Optional[str] = None
    platform_code: Optional[str] = None
    shares: Optional[float] = None
    frozen_shares: Optional[float] = None
    cost_price: Optional[float] = None
    unit_price: Optional[float] = None
    market_value: Optional[float] = None
    amount: Optional[float] = None
    frozen_amount: Optional[float] = None
    snapshot_date: date


class PositionCreate(PositionBase):
    pass


class PositionUpdate(BaseModel):
    platform_code: Optional[str] = None
    shares: Optional[float] = None
    frozen_shares: Optional[float] = None
    cost_price: Optional[float] = None
    unit_price: Optional[float] = None
    market_value: Optional[float] = None
    amount: Optional[float] = None
    frozen_amount: Optional[float] = None
    snapshot_date: Optional[date] = None


class PositionResponse(PositionBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
