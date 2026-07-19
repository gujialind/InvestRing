from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class TradeBase(BaseModel):
    portfolio_code: str
    product_code: str
    market: Optional[str] = None
    platform_code: Optional[str] = None
    trade_type: str
    transfer_group: Optional[str] = None  # 平台间现金转移配对标识
    shares: Optional[float] = None
    amount: Optional[float] = None
    price: Optional[float] = None
    fee: float = 0
    actual_amount: Optional[float] = None
    trade_date: date
    confirm_date: Optional[date] = None
    status: str = "pending"
    notes: Optional[str] = None


class TradeCreate(TradeBase):
    pass


class TradeUpdate(BaseModel):
    shares: Optional[float] = None
    amount: Optional[float] = None
    price: Optional[float] = None
    fee: Optional[float] = None
    actual_amount: Optional[float] = None
    trade_date: Optional[date] = None
    confirm_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class TradeResponse(TradeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
