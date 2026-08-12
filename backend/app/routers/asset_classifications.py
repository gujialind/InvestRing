from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.asset_classification import AssetClassification

router = APIRouter()


@router.get("")
def list_asset_classifications(
    dimension: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """维度值字典只读端点（issue #128）。

    前端大类颜色/展示顺序由此驱动（asset_class 维度的 sort_order 即色板序位）；
    管理面 CRUD 归 #111，本期只读。返回按 dimension+sort_order 排序的全量维度值。
    """
    query = db.query(AssetClassification)
    if dimension:
        query = query.filter(AssetClassification.dimension == dimension)
    items = query.order_by(
        AssetClassification.dimension, AssetClassification.sort_order
    ).all()
    return {
        "items": [
            {
                "code": ac.code,
                "dimension": ac.dimension,
                "name": ac.name,
                "sort_order": ac.sort_order,
                "description": ac.description,
            }
            for ac in items
        ],
        "total": len(items),
    }
