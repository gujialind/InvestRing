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


class SnapshotCatchUpRequest(BaseModel):
    """快照追平请求（issue #84）"""
    portfolio_code: str
    to_date: date


class SnapshotGenerateNextRequest(BaseModel):
    """生成下一交易日快照请求（issue #84）"""
    portfolio_code: str


class SnapshotCatchUpResult(BaseModel):
    """快照追平结果（issue #84）

    逐日 checkpoint 语义：失败时 generated_dates 中已成功的日子已落库，
    failed_date/error 标记中断点。
    """
    portfolio_code: str
    to_date: str  # ISO格式
    generated_count: int
    generated_dates: List[str]  # ISO格式日期列表（升序）
    latest_snapshot_date: Optional[str] = None
    message: Optional[str] = None
    failed_date: Optional[str] = None
    error: Optional[str] = None


class SnapshotGenerateNextResult(BaseModel):
    """生成下一交易日快照结果（issue #84）"""
    success: bool
    message: str
    portfolio_code: str
    generated_date: str  # ISO格式
    total_value: Optional[float] = None
    total_shares: Optional[float] = None
    unit_price: Optional[float] = None
    warnings: Optional[List[Dict[str, Any]]] = None


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
    # issue #71：负现金等非阻断性告警（无告警时为 None，旧客户端可忽略）
    warnings: Optional[List[Dict[str, Any]]] = None


class RecalculationPortfolioResult(BaseModel):
    """单个组合的重算结果"""
    portfolio_code: str
    processed_dates: List[str]  # ISO格式日期列表
    total_processed: int
    errors: List[Dict[str, Any]]
    # issue #71：逐日重建累积的负现金告警（与 errors 聚合风格一致）
    warnings: Optional[List[Dict[str, Any]]] = None


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
    # issue #71：最新快照日 CASH 持仓 cash_amount < 0 的平台清单（正常为空）
    negative_cash_platforms: List[str] = []
