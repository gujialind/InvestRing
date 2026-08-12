from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ProductBase(BaseModel):
    code: str
    market: Optional[str] = None
    name: str
    product_type: str
    # 正交维度标签（issue #128）：适用矩阵由服务端校验（股票必填 region/style/size；
    # 债券必填 region+segment；商品/现金的 region/style/size 必须为 NULL）
    asset_class_code: Optional[str] = None
    region_code: Optional[str] = None
    style_code: Optional[str] = None
    size_code: Optional[str] = None
    segment_code: Optional[str] = None
    confirm_days: int = 1
    is_qdii: bool = False
    data_source: Optional[str] = "tushare"


class ProductCreate(ProductBase):
    # issue #90：创建后立即回填历史净值（同步失败不阻断创建）
    sync_history: Optional[bool] = False


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    asset_class_code: Optional[str] = None
    region_code: Optional[str] = None
    style_code: Optional[str] = None
    size_code: Optional[str] = None
    segment_code: Optional[str] = None
    confirm_days: Optional[int] = None
    is_qdii: Optional[bool] = None


class ProductResponse(ProductBase):
    data_source: Optional[str] = None
    data_source_status: str = "pending"
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # issue #90：sync_history=True 时的回填结果（success/message/synced_count）
    sync_result: Optional[dict] = None

    class Config:
        from_attributes = True
