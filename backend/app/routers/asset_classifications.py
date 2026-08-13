from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.asset_classification import (
    AssetClassification,
    AssetClassDimensionRule,
    AssetDimensionApplicability,
)
from app.schemas.asset_classification import (
    AssetClassificationItem,
    AssetClassificationListResponse,
)

router = APIRouter()


@router.get("", response_model=AssetClassificationListResponse)
def list_asset_classifications(
    dimension: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """维度值字典只读端点（issue #128；#135 扩展适用关系与 is_active）。

    前端大类颜色/展示顺序由此驱动（asset_class 维度的 sort_order 即色板序位）；
    管理面 CRUD 归 #135。返回按 dimension+sort_order+code 排序的全量维度值
    （含停用值，消费方按 is_active 自行过滤）；每项附 applicable_asset_classes
    （值级适用大类，asset_class 维度值恒为空 list）；顶层 dimension_rules 为
    维度级适用矩阵（缺省维度 = forbidden），驱动产品表单必填/禁用与管理页。
    """
    query = db.query(AssetClassification)
    if dimension:
        query = query.filter(AssetClassification.dimension == dimension)
    items = query.order_by(
        AssetClassification.dimension,
        AssetClassification.sort_order,
        AssetClassification.code,
    ).all()

    # 值级适用关联：value → [asset_class]（按大类色板序位排序，code 兜底）
    class_order = dict(
        db.query(AssetClassification.code, AssetClassification.sort_order)
        .filter(AssetClassification.dimension == "asset_class")
        .all()
    )
    applicability: dict[str, list[str]] = {}
    for row in db.query(AssetDimensionApplicability).all():
        applicability.setdefault(row.dimension_value_code, []).append(row.asset_class_code)
    for classes in applicability.values():
        classes.sort(key=lambda c: (class_order.get(c, 999), c))

    # 维度级规则：asset_class → {dimension: rule}
    dimension_rules: dict[str, dict[str, str]] = {}
    for row in db.query(AssetClassDimensionRule).all():
        dimension_rules.setdefault(row.asset_class_code, {})[row.dimension] = row.rule

    return {
        "items": [
            AssetClassificationItem(
                code=ac.code,
                dimension=ac.dimension,
                name=ac.name,
                sort_order=ac.sort_order,
                description=ac.description,
                is_active=ac.is_active,
                applicable_asset_classes=applicability.get(ac.code, []),
            )
            for ac in items
        ],
        "dimension_rules": dimension_rules,
        "total": len(items),
    }
