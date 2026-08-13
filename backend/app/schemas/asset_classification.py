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


class AssetClassificationDetail(AssetClassificationItem):
    """单条详情：asset_class 维度值附其维度规则（其余维度恒空 dict）"""
    dimension_rules: dict[str, str] = {}


class AssetClassificationListResponse(BaseModel):
    """维度字典全量响应。dimension_rules 为维度级适用矩阵（#135 矩阵落库）：
    {asset_class: {dimension: rule}}，rule ∈ required/optional，未出现的
    (大类, 维度) = forbidden；未出现的大类 = 全 forbidden（现金型语义）。"""
    items: list[AssetClassificationItem]
    dimension_rules: dict[str, dict[str, str]]
    total: int


class AssetClassificationCreate(BaseModel):
    """新建维度值（#135）。code 前缀须与 dimension 匹配（ASSET_/REGION_/STYLE_/
    SIZE_/SEG_，全大写）；非 asset_class 维度必须指定 ≥1 适用大类；
    dimension=asset_class 时可带 dimension_rules（缺省 = 现金型全 forbidden）。"""
    code: str
    dimension: str
    name: str
    sort_order: int = 0
    description: Optional[str] = None
    applicable_asset_classes: Optional[list[str]] = None
    dimension_rules: Optional[dict[str, str]] = None


class AssetClassificationUpdate(BaseModel):
    """更新维度值（#135）。code/dimension 不可改（被 product 五列 FK 与维度匹配
    语义引用），故不在本模型中。applicable_asset_classes / dimension_rules 为
    全量替换语义（None = 不动）。"""
    name: Optional[str] = None
    sort_order: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    applicable_asset_classes: Optional[list[str]] = None
    dimension_rules: Optional[dict[str, str]] = None
