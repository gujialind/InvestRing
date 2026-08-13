from typing import Optional

from pydantic import BaseModel


class AssetClassificationItem(BaseModel):
    """维度值字典项（issue #128；#135 扩展 is_active 与值级适用大类）"""
    code: str
    dimension: str
    name: str
    sort_order: int
    description: Optional[str] = None
    is_active: bool
    # 值级适用 asset_class（多对多，按大类 sort_order 排序）；asset_class 维度值恒为空
    applicable_asset_classes: list[str]


class AssetClassificationListResponse(BaseModel):
    """维度字典全量响应。dimension_rules 为维度级适用矩阵（#135 矩阵落库）：
    {asset_class: {dimension: rule}}，rule ∈ required/optional，未出现的
    (大类, 维度) = forbidden；未出现的大类 = 全 forbidden（现金型语义）。"""
    items: list[AssetClassificationItem]
    dimension_rules: dict[str, dict[str, str]]
    total: int
