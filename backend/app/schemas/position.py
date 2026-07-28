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
    cash_amount: Optional[float] = None
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
    cash_amount: Optional[float] = None
    frozen_amount: Optional[float] = None
    snapshot_date: Optional[date] = None


class PositionResponse(PositionBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CashPositionUpdate(BaseModel):
    """非净值型资产（现金）更新请求"""
    cash_amount: float
    platform_code: str  # 必填：平台代码
    update_date: Optional[date] = None  # 可选，默认为今天
