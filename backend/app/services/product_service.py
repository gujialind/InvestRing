"""
产品管理服务

confirm_days 计算（单一实现）与产品 CRUD，从路由层提取供 REST 与 CLI 共用。
service 层只抛领域异常，不 commit。
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.exceptions import BusinessError, NotFoundError


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
    is_qdii: bool = False,
    data_source: Optional[str] = None,
    sync_history: bool = False,
) -> Product:
    """创建产品（自动计算 confirm_days）。不 commit。

    sync_history=True 时（issue #90）创建后立即回填历史净值；
    同步失败不回滚产品创建，结果挂在返回对象的瞬态属性 sync_result。
    """
    existing = db.query(Product).filter(
        Product.code == code, Product.market == market
    ).first()
    if existing:
        raise BusinessError("ALREADY_EXISTS", f"产品 {code}({market}) 已存在", http_status=400)

    confirm_days = calculate_confirm_days(market or "CN_OTC", is_qdii)
    product = Product(
        code=code,
        market=market or "",
        name=name,
        product_type=product_type,
        asset_class_code=asset_class_code,
        confirm_days=confirm_days,
        is_qdii=is_qdii,
        data_source=data_source,
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

    for field, value in updates.items():
        setattr(product, field, value)
    return product
