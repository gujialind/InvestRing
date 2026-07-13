from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PriceSyncRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    scope: str = "all"
    products: Optional[List[List[str]]] = None


class SyncJobResponse(BaseModel):
    id: int
    job_type: str
    status: str
    params: Optional[dict] = None
    total: int = 0
    done: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error_message: Optional[str] = None
    triggered_by: str = "manual"
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NavSyncDetailResponse(BaseModel):
    id: int
    job_id: Optional[int] = None
    task_log_id: Optional[int] = None
    product_code: str
    market: str
    nav_date: str
    status: str
    synced_count: int = 0
    source: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
