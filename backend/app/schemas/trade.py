from pydantic import BaseModel
from typing import List, Optional
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
    # 自然键防重（#82）：命中同参数 pending/confirmed 交易时需显式传 True 强制创建
    allow_duplicate: bool = False
    # 跨平台现金腿（#91）：买=扣款平台、卖=到账平台，缺省同基金腿平台
    cash_platform_code: Optional[str] = None
    # #93: CASH 腿独立确认日（卖出到账日）
    cash_confirm_date: Optional[date] = None


class TradeUpdate(BaseModel):
    # confirm_date 不开放直改：创建/unconfirm 按 confirm_days 自动维护，
    # 改 trade_date 时由 service 联动重算；补录覆盖走 confirm 端点传参
    # status 不开放直改：状态流转走 confirm/cancel/unconfirm 端点
    # amount 语义（#182 D1，与创建同口径）：buy/sell 输入均视为实际金额
    # （buy=含费现金支出、sell=到手净额），actual_amount 优先，service 联动重算
    shares: Optional[float] = None
    amount: Optional[float] = None
    price: Optional[float] = None
    fee: Optional[float] = None
    actual_amount: Optional[float] = None
    trade_date: Optional[date] = None
    notes: Optional[str] = None


class TradeResponse(TradeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # product_name 读侧派生（非 DB 列）：仅 list 端点批量 join 产品表填充，
    # create/get/update/preview 响应恒为 None；同 positions 模式（#175）
    product_name: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedTradeResponse(BaseModel):
    """交易列表分页响应（issue #183）。items 元素复用 TradeResponse：
    product_name 仅 list 端点填充，单对象端点恒为 None（见 TradeResponse 注释）。"""
    items: List[TradeResponse]
    total: int
    page: int
    page_size: int


class TradePreviewResult(BaseModel):
    """确认前预览的计算结果（与真实确认共用同一计算实现）"""
    price: Optional[float] = None
    shares: Optional[float] = None
    amount: Optional[float] = None
    actual_amount: Optional[float] = None
    fee: float = 0
    confirm_date: Optional[date] = None
    nav_date: Optional[date] = None  # OTC 净值型时取净值的 T 日
    is_otc_nav_fund: bool = False


class TradePreviewResponse(BaseModel):
    trade: TradeResponse
    preview: TradePreviewResult
    paired_cash_amount: Optional[float] = None  # 配对 CASH 腿将同步的金额
