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
    asset_type: Optional[str] = None
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
    # 读侧派生字段（issue：前端持仓表产品名称/盈亏/收益率三列）：
    # product_name 来自 product 表；盈亏 = market_value − shares×cost_price（仅净值型资产）
    product_name: Optional[str] = None
    profit_loss: Optional[float] = None
    profit_loss_percent: Optional[float] = None
    # 读侧派生字段（issue #99）：asset_name 来自 asset_classification（聚合展示短名目）；
    # daily_profit 为当日收益（首个快照日 / IN_TRANSIT 在途行 → None）；
    # is_qdii 来自 product 表（QDII 按 T-1 净值估值，前端提示日收益滞后一天）
    asset_name: Optional[str] = None
    daily_profit: Optional[float] = None
    is_qdii: Optional[bool] = None

    class Config:
        from_attributes = True


class CashPositionUpdate(BaseModel):
    """非净值型资产（现金）更新请求"""
    cash_amount: float
    platform_code: str  # 必填：平台代码
    update_date: Optional[date] = None  # 可选，默认为今天
