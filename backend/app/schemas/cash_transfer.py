from pydantic import BaseModel
from typing import Optional
from datetime import date


class CashTransferCreate(BaseModel):
    """平台间现金转移请求"""
    from_platform: str      # 转出平台
    to_platform: str        # 转入平台
    amount: float           # 转移金额
    cross_day: bool = False # False=当天完成，True=T+1到账
    transfer_date: date     # 转出日期
    notes: Optional[str] = None


class CashTransferResponse(BaseModel):
    """现金转移响应"""
    transfer_group: str
    from_platform: str
    to_platform: str
    amount: float
    cross_day: bool
    sell_trade_id: int      # 转出交易ID
    buy_trade_id: int       # 转入交易ID
    sell_status: str        # 转出交易状态
    buy_status: str         # 转入交易状态
    transfer_date: date


class CashTransferListItem(BaseModel):
    """现金转移列表项"""
    transfer_group: str
    from_platform: str
    to_platform: str
    amount: float
    cross_day: bool
    sell_status: str
    buy_status: str
    transfer_date: date
    sell_confirm_date: Optional[date] = None
    buy_confirm_date: Optional[date] = None
    notes: Optional[str] = None
