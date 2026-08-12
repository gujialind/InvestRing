"""
产品管理服务

confirm_days 计算（单一实现）与产品 CRUD，从路由层提取供 REST 与 CLI 共用。
service 层只抛领域异常，不 commit。
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.asset_classification import AssetClassification
from app.models.product import Product
from app.services.exceptions import BusinessError, NotFoundError

# 维度字段 → 字典 dimension（issue #128）
DIMENSION_FIELDS = ("asset_class_code", "region_code", "style_code", "size_code", "segment_code")
_DIMENSION_OF_FIELD = {
    "asset_class_code": "asset_class",
    "region_code": "region",
    "style_code": "style",
    "size_code": "size",
    "segment_code": "segment",
}


def validate_dimension_tags(db: Session, dims: dict) -> None:
    """校验五维度标签（create 传入值 / update 合并值）：

    1. 每个非 NULL code 必须存在于维度字典且 dimension 匹配字段；
    2. 适用矩阵：股票必填 region/style/size；债券必填 region+segment 且
       style/size 为 NULL；商品/现金的 region/style/size 必须为 NULL；
       asset_class 为 NULL（虚拟产品）时其余维度必须全 NULL；
    3. asset_class 为字典中已存在、但适用矩阵未登记的新大类（YAGNI 扩展
       遗漏）时显式 422，不得 KeyError → 500。
    非法组合抛 INVALID_DIMENSION_TAGS（422）。
    """
    for field in DIMENSION_FIELDS:
        code = dims.get(field)
        if code is None:
            continue
        ac = db.query(AssetClassification).filter(AssetClassification.code == code).first()
        if not ac or ac.dimension != _DIMENSION_OF_FIELD[field]:
            raise BusinessError(
                "INVALID_DIMENSION_TAGS",
                f"维度值 {code} 不存在或不属于 {_DIMENSION_OF_FIELD[field]} 维度",
                details={"field": field, "code": code},
            )

    asset = dims.get("asset_class_code")
    if asset is None:
        extra = [f for f in DIMENSION_FIELDS if f != "asset_class_code" and dims.get(f)]
        if extra:
            raise BusinessError(
                "INVALID_DIMENSION_TAGS",
                "未指定 asset_class 时其余维度必须为空",
                details={"fields": extra},
            )
        return

    # 适用矩阵（单一事实来源）：大类 → (必填维度, 禁止维度)。
    # 字典新增大类值时必须同步在此登记，否则使用该大类的请求显式 422。
    matrix = {
        "ASSET_STOCK": (("region_code", "style_code", "size_code"), ()),
        "ASSET_BOND": (("region_code", "segment_code"), ("style_code", "size_code")),
        "ASSET_COMMODITY": ((), ("region_code", "style_code", "size_code")),
        "ASSET_CASH": ((), ("region_code", "style_code", "size_code")),
    }.get(asset)
    if matrix is None:
        raise BusinessError(
            "INVALID_DIMENSION_TAGS",
            f"大类 {asset} 的维度适用矩阵未定义",
            details={"asset_class_code": asset},
        )
    required, forbidden = matrix
    missing = [f for f in required if not dims.get(f)]
    if missing:
        raise BusinessError(
            "INVALID_DIMENSION_TAGS",
            f"{asset} 缺少必填维度：{', '.join(missing)}",
            details={"asset_class_code": asset, "missing": missing},
        )
    present = [f for f in forbidden if dims.get(f)]
    if present:
        raise BusinessError(
            "INVALID_DIMENSION_TAGS",
            f"{asset} 不允许维度：{', '.join(present)}",
            details={"asset_class_code": asset, "forbidden": present},
        )


def calculate_confirm_days(market: Optional[str], is_qdii: bool) -> int:
    """确认天数计算（唯一实现）：
    - CN_EXCHANGE: 0（场内当天）
    - CN_OTC 且非 QDII: 1（T+1）
    - CN_OTC 且 QDII: 2（T+2）
    - 其他: 1
    """
    if market == "CN_EXCHANGE":
        return 0
    if market == "CN_OTC":
        return 2 if is_qdii else 1
    return 1


def resolve_product_market(
    db: Session, product_code: str, market: Optional[str] = None
) -> tuple:
    """解析产品市场（issue #83，单一实现，供 trade/product 各入口复用）：
    - market 非空：原样返回 (product_code, market)
    - 省略且该 code 仅存在一个市场：自动补全
    - 省略且存在多个市场（LOF 一码多市场）：抛 MARKET_AMBIGUOUS（422）
    - code 不存在：抛 PRODUCT_NOT_FOUND（404）
    """
    if market:
        return product_code, market
    markets = sorted(
        row[0] or ""
        for row in db.query(Product.market).filter(Product.code == product_code).all()
    )
    if not markets:
        raise NotFoundError(
            "PRODUCT_NOT_FOUND",
            f"产品 {product_code} 不存在",
            details={"product_code": product_code},
        )
    if len(markets) > 1:
        raise BusinessError(
            "MARKET_AMBIGUOUS",
            f"产品 {product_code} 存在多个市场，请指定 market",
            details={"product_code": product_code, "available_markets": markets},
        )
    return product_code, markets[0]


def create_product(
    db: Session,
    *,
    code: str,
    market: Optional[str],
    name: str,
    product_type: str,
    asset_class_code: Optional[str] = None,
    region_code: Optional[str] = None,
    style_code: Optional[str] = None,
    size_code: Optional[str] = None,
    segment_code: Optional[str] = None,
    is_qdii: bool = False,
    data_source: Optional[str] = None,
    sync_history: bool = False,
) -> Product:
    """创建产品（自动计算 confirm_days，校验五维度适用矩阵）。不 commit。

    sync_history=True 时（issue #90）创建后立即回填历史净值；
    同步失败不回滚产品创建，结果挂在返回对象的瞬态属性 sync_result。
    """
    existing = db.query(Product).filter(
        Product.code == code, Product.market == market
    ).first()
    if existing:
        raise BusinessError("ALREADY_EXISTS", f"产品 {code}({market}) 已存在", http_status=400)

    dims = {
        "asset_class_code": asset_class_code, "region_code": region_code,
        "style_code": style_code, "size_code": size_code, "segment_code": segment_code,
    }
    validate_dimension_tags(db, dims)

    confirm_days = calculate_confirm_days(market or "CN_OTC", is_qdii)
    product = Product(
        code=code,
        market=market or "",
        name=name,
        product_type=product_type,
        confirm_days=confirm_days,
        is_qdii=is_qdii,
        data_source=data_source,
        **dims,
    )
    db.add(product)

    if sync_history:
        from datetime import date as _date
        from app.services.market_data_service import sync_price_data

        db.flush()
        try:
            result = sync_price_data(db, code, product.market, None, _date.today())
            product.sync_result = {
                "success": bool(result.get("success")),
                "message": result.get("message"),
                "synced_count": result.get("synced_count"),
            }
        except Exception as e:  # 同步失败不阻断创建，用户可事后 sync-history 补回填
            product.sync_result = {"success": False, "message": str(e), "synced_count": 0}

    return product


def update_product(
    db: Session,
    *,
    code: str,
    market: str,
    updates: dict,
) -> Product:
    """更新产品信息（market/is_qdii 变更时自动重算 confirm_days）。不 commit。"""
    product = db.query(Product).filter(
        Product.code == code, Product.market == market
    ).first()
    if not product:
        raise NotFoundError("NOT_FOUND", f"产品 {code}({market}) 不存在")

    new_market = updates.get("market", product.market)
    new_is_qdii = updates.get("is_qdii", product.is_qdii)
    if "market" in updates or "is_qdii" in updates:
        updates = {**updates, "confirm_days": calculate_confirm_days(new_market or "CN_OTC", new_is_qdii)}

    # 维度标签按合并后结果校验适用矩阵（部分更新不允许造成非法组合）
    if any(f in updates for f in DIMENSION_FIELDS):
        merged = {f: updates.get(f, getattr(product, f)) for f in DIMENSION_FIELDS}
        validate_dimension_tags(db, merged)

    for field, value in updates.items():
        setattr(product, field, value)
    return product
