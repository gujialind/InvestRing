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
) -> Product:
    """创建产品（自动计算 confirm_days）。不 commit。"""
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
