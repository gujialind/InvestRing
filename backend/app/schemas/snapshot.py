"""快照管理相关的Schema定义"""
from datetime import date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class SnapshotGenerateRequest(BaseModel):
    """单日快照生成请求"""
    portfolio_code: str
    target_date: date


class SnapshotRecalculateRequest(BaseModel):
    """区间快照重算请求"""
    portfolio_code: Optional[str] = None  # None表示所有活跃组合
    start_date: date
    end_date: date
    force: bool = False  # 是否强制重算（跳过校验）


class ValidationCheckResult(BaseModel):
    """数据校验结果"""
    check_type: str  # "trading_day", "pending_transactions", "price_data", "share_change_events"
    status: str  # "passed", "failed", "warning"
    message: str


class SnapshotValidationResult(BaseModel):
    """快照依赖数据校验结果"""
    portfolio_code: str
    target_date: date
    is_valid: bool
    checks: List[ValidationCheckResult]


class SnapshotGenerationResult(BaseModel):
    """快照生成结果"""
    success: bool
    message: str
    portfolio_code: str
    snapshot_date: date
    total_value: Optional[float] = None
    total_shares: Optional[float] = None
    unit_price: Optional[float] = None


class RecalculationPortfolioResult(BaseModel):
    """单个组合的重算结果"""
    portfolio_code: str
    processed_dates: List[str]  # ISO格式日期列表
    total_processed: int
    errors: List[Dict[str, Any]]


class RecalculationResult(BaseModel):
    """区间重算结果"""
    success: bool
    message: str
    results: List[RecalculationPortfolioResult]


class SnapshotStatusResponse(BaseModel):
    """组合快照状态响应"""
    portfolio_code: str
    latest_snapshot_date: Optional[date] = None
    total_snapshots: int
    first_snapshot_date: Optional[date] = None
    missing_dates: List[str]  # 缺失的交易日（ISO格式）
