"""
ir product - 产品管理命令组
"""
import typer
from typing import Optional

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta

app = typer.Typer(no_args_is_help=True)


def _calculate_confirm_days(market: str, is_qdii: bool) -> int:
    if market == "CN_EXCHANGE":
        return 0
    if market == "CN_OTC" and is_qdii:
        return 2
    if market == "CN_OTC":
        return 1
    return 0


@app.command("list")
def list_products(
    product_type: Optional[str] = typer.Option(None, "--product-type", help="ETF/OEF/LOF/CASH"),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
    all: bool = typer.Option(False, "--all"),
):
    """获取产品列表"""
    with cli_context() as db:
        from app.models.product import Product

        query = db.query(Product).order_by(Product.code)
        if product_type:
            query = query.filter(Product.product_type == product_type)
        items, total, page, page_size = paginate(query, page, page_size, all)
        success(
            data=[serialize_model(i) for i in items],
            meta=pagination_meta(total, page, page_size),
        )


@app.command("create")
def create_product(
    code: str = typer.Option(..., "--code"),
    market: str = typer.Option(..., "--market", help="CN_EXCHANGE/CN_OTC/HK_MUTUAL/空"),
    name: str = typer.Option(..., "--name"),
    product_type: str = typer.Option(..., "--product-type", help="ETF/OEF/LOF/CASH"),
    asset_class_code: Optional[str] = typer.Option(None, "--asset-class-code"),
    is_qdii: bool = typer.Option(False, "--is-qdii"),
    data_source: Optional[str] = typer.Option(None, "--data-source"),
):
    """创建产品（自动计算 confirm_days）"""
    with cli_context() as db:
        from app.models.product import Product

        existing = db.query(Product).filter(
            Product.code == code, Product.market == market
        ).first()
        if existing:
            error("ALREADY_EXISTS", f"产品 {code}({market}) 已存在")

        confirm_days = _calculate_confirm_days(market, is_qdii)
        product = Product(
            code=code, market=market or "", name=name,
            product_type=product_type, asset_class_code=asset_class_code,
            is_qdii=is_qdii, confirm_days=confirm_days,
            data_source=data_source,
        )
        db.add(product)
        db.flush()
        db.refresh(product)
        success(data=serialize_model(product))


@app.command("get")
def get_product(
    code: str = typer.Argument(...),
    market: str = typer.Argument(..., help="市场类型"),
):
    """查看产品详情"""
    with cli_context() as db:
        from app.models.product import Product

        product = db.query(Product).filter(
            Product.code == code, Product.market == market
        ).first()
        if not product:
            error("NOT_FOUND", f"产品 {code}({market}) 不存在")
        success(data=serialize_model(product))


@app.command("update")
def update_product(
    code: str = typer.Argument(...),
    market: str = typer.Argument(...),
    name: Optional[str] = typer.Option(None, "--name"),
    is_qdii: Optional[bool] = typer.Option(None, "--is-qdii"),
    asset_class_code: Optional[str] = typer.Option(None, "--asset-class-code"),
    data_source: Optional[str] = typer.Option(None, "--data-source"),
):
    """更新产品信息"""
    with cli_context() as db:
        from app.models.product import Product

        product = db.query(Product).filter(
            Product.code == code, Product.market == market
        ).first()
        if not product:
            error("NOT_FOUND", f"产品 {code}({market}) 不存在")

        if name is not None:
            product.name = name
        if asset_class_code is not None:
            product.asset_class_code = asset_class_code
        if data_source is not None:
            product.data_source = data_source
        if is_qdii is not None:
            product.is_qdii = is_qdii
            product.confirm_days = _calculate_confirm_days(product.market, is_qdii)

        db.flush()
        db.refresh(product)
        success(data=serialize_model(product))


@app.command("delete")
def delete_product(
    code: str = typer.Argument(...),
    market: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes"),
):
    """删除产品"""
    with cli_context() as db:
        from app.models.product import Product

        product = db.query(Product).filter(
            Product.code == code, Product.market == market
        ).first()
        if not product:
            error("NOT_FOUND", f"产品 {code}({market}) 不存在")

        db.delete(product)
        db.flush()
        success(data={"message": f"产品 {code}({market}) 已删除"})
