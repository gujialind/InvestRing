from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class SubscriptionBase(BaseModel):
    portfolio_code: str
    investor_code: str
    platform_code: str  # 交易平台
    sub_type: str  # subscribe/redeem
    amount: Optional[float] = None
    shares: Optional[float] = None
    unit_price: Optional[float] = None
    apply_date: date
    confirm_date: Optional[date] = None
    status: str = "pending"
    notes: Optional[str] = None


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(BaseModel):
    # confirm_date 不开放直改：创建/unconfirm 时由服务层按 T+1 自动维护
    # status 不开放直改：状态流转走 confirm/cancel/unconfirm 端点
    platform_code: Optional[str] = None
    amount: Optional[float] = None
    shares: Optional[float] = None
    unit_price: Optional[float] = None
    notes: Optional[str] = None


class SubscriptionResponse(SubscriptionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
