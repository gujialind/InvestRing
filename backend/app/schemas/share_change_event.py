from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime


class ShareChangeEventBase(BaseModel):
    portfolio_code: str
    event_type: str  # cash_dividend/reinvest_dividend/share_split/share_merge/bonus_share/forced_adjustment
    ex_date: date
    entitlement_date: date
    platform_code: Optional[str] = None
    parent_event_id: Optional[int] = None
    product_code: Optional[str] = None
    market: Optional[str] = None
    event_source: str = "manual"
    entitlement_shares: Optional[float] = None
    shares_before: Optional[float] = None
    shares_change: Optional[float] = None
    shares_after: Optional[float] = None
    cash_change: Optional[float] = None
    cash_product_code: Optional[str] = None
    div_cash: Optional[float] = None
    reinvest_nav: Optional[float] = None
    ratio: Optional[float] = None
    status: str = "pending"
    tushare_event_id: Optional[str] = None
    notes: Optional[str] = None


class ShareChangeEventCreate(ShareChangeEventBase):
    pass


class ShareChangeEventUpdate(BaseModel):
    # status 不开放直改：状态流转走 confirm/cancel/unconfirm 端点
    ex_date: Optional[date] = None
    entitlement_date: Optional[date] = None
    shares_before: Optional[float] = None
    shares_change: Optional[float] = None
    shares_after: Optional[float] = None
    cash_change: Optional[float] = None
    div_cash: Optional[float] = None
    reinvest_nav: Optional[float] = None
    ratio: Optional[float] = None
    notes: Optional[str] = None


class ShareChangeEventResponse(ShareChangeEventBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # product_name 读侧派生（非 DB 列）：仅 list 端点批量 join 产品表填充，
    # create/get/update/confirm/unconfirm 响应恒为 None；同 positions 模式（#175/#342）
    product_name: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedShareEventResponse(BaseModel):
    """份额变动事件列表分页响应（#342）。items 元素复用 ShareChangeEventResponse：
    product_name 仅 list 端点填充，单对象端点恒为 None（见 ShareChangeEventResponse 注释）。"""
    items: List[ShareChangeEventResponse]
    total: int
    page: int
    page_size: int
