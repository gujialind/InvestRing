from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.dependencies import get_current_user, get_current_admin

router = APIRouter()


def _calculate_confirm_days(market: str, is_qdii: bool) -> int:
    """
    自动计算确认天数：
    - market = CN_EXCHANGE: 0（场内当天确认）
    - market = CN_OTC 且 is_qdii = False: 1（T+1）
    - market = CN_OTC 且 is_qdii = True: 2（T+2）
    - 其他: 1
    """
    if market == "CN_EXCHANGE":
        return 0
    if market == "CN_OTC":
        return 2 if is_qdii else 1
    return 1


@router.get("")
def get_products(
    product_type: Optional[str] = None,
    market: Optional[str] = None,
    data_source: Optional[str] = None,
    data_source_status: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Product)
    if product_type:
        query = query.filter(Product.product_type == product_type)
    if market:
        query = query.filter(Product.market == market)
    if data_source:
        query = query.filter(Product.data_source == data_source)
    if data_source_status:
        query = query.filter(Product.data_source_status == data_source_status)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=ProductResponse)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    db_product = db.query(Product).filter(
        Product.code == product.code,
        Product.market == product.market
    ).first()
    if db_product:
        raise HTTPException(status_code=400, detail="Product already exists")

    confirm_days = _calculate_confirm_days(product.market or "CN_OTC", product.is_qdii)

    new_product = Product(
        code=product.code,
        market=product.market,
        name=product.name,
        product_type=product.product_type,
        asset_class_code=product.asset_class_code,
        confirm_days=confirm_days,
        is_qdii=product.is_qdii,
        data_source=product.data_source,
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@router.get("/{code}/{market}", response_model=ProductResponse)
def get_product(
    code: str,
    market: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.code == code,
        Product.market == market
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/{code}/{market}", response_model=ProductResponse)
def update_product(
    code: str,
    market: str,
    product: ProductUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    db_product = db.query(Product).filter(
        Product.code == code,
        Product.market == market
    ).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product.dict(exclude_unset=True)
    # 如果市场类型或QDII状态变更，自动重新计算confirm_days
    new_market = update_data.get("market", db_product.market)
    new_is_qdii = update_data.get("is_qdii", db_product.is_qdii)
    if "market" in update_data or "is_qdii" in update_data:
        update_data["confirm_days"] = _calculate_confirm_days(new_market or "CN_OTC", new_is_qdii)

    for field, value in update_data.items():
        setattr(db_product, field, value)

    db.commit()
    db.refresh(db_product)
    return db_product


@router.delete("/{code}/{market}")
def delete_product(
    code: str,
    market: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    product = db.query(Product).filter(
        Product.code == code,
        Product.market == market
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(product)
    db.commit()
    return {"message": "Product deleted successfully"}
