from pydantic import BaseModel, ConfigDict, Field
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
    # issue #228：快照估值取价滞后交易日数（0=当日、N=前第 N 个交易日）；
    # 场外 QDII / 互认基金取 1。is_qdii 仅为展示标签，不参与取价
    # issue #235：ge=0 拦截负值（此前被快照取价侧静默钳制为 0）；
    # 场内基金（CN_EXCHANGE）必须 0 的跨字段规则在 product_service 校验
    nav_lag_days: int = Field(default=0, ge=0)
    is_qdii: bool = False
    data_source: Optional[str] = "tushare"


class ProductCreate(ProductBase):
    # issue #90：创建后立即回填历史净值（同步失败不阻断创建）
    sync_history: Optional[bool] = False


class ProductUpdate(BaseModel):
    # issue #232：未知字段直接 422（此前 pydantic 静默丢弃，调用方误以为修改生效）
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    # issue #232：身份字段可纠错（枚举/守卫见 product_service），market 仅限无引用产品
    product_type: Optional[str] = None
    market: Optional[str] = None
    asset_class_code: Optional[str] = None
    region_code: Optional[str] = None
    style_code: Optional[str] = None
    size_code: Optional[str] = None
    segment_code: Optional[str] = None
    confirm_days: Optional[int] = None
    # issue #235：ge=0 拦截负值（PartialUpdate：缺省=不修改，null 由服务层拒绝）
    nav_lag_days: Optional[int] = Field(default=None, ge=0)
    is_qdii: Optional[bool] = None


class ProductResponse(ProductBase):
    data_source: Optional[str] = None
    data_source_status: str = "pending"
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # issue #90：sync_history=True 时的回填结果（success/message/synced_count）
    sync_result: Optional[dict] = None
    # issue #232：market 随行迁移后的提示（建议重新 sync-history 等）
    market_change_hint: Optional[str] = None

    class Config:
        from_attributes = True
