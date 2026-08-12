"""
ir product - 产品管理命令组
"""
import typer
from typing import Optional

from cli.context import cli_context
from cli.output import success, error
from cli.utils import serialize_model, paginate, pagination_meta

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_products(
    product_type: Optional[str] = typer.Option(None, "--product-type", help="ETF/OEF/LOF/CASH"),
    asset_class_code: Optional[str] = typer.Option(None, "--asset-class-code", help="维度筛选：大类"),
    region_code: Optional[str] = typer.Option(None, "--region-code", help="维度筛选：地域"),
    style_code: Optional[str] = typer.Option(None, "--style-code", help="维度筛选：风格"),
    size_code: Optional[str] = typer.Option(None, "--size-code", help="维度筛选：规模"),
    segment_code: Optional[str] = typer.Option(None, "--segment-code", help="维度筛选：细分"),
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
        if asset_class_code:
            query = query.filter(Product.asset_class_code == asset_class_code)
        if region_code:
            query = query.filter(Product.region_code == region_code)
        if style_code:
            query = query.filter(Product.style_code == style_code)
        if size_code:
            query = query.filter(Product.size_code == size_code)
        if segment_code:
            query = query.filter(Product.segment_code == segment_code)
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
    region_code: Optional[str] = typer.Option(None, "--region-code"),
    style_code: Optional[str] = typer.Option(None, "--style-code"),
    size_code: Optional[str] = typer.Option(None, "--size-code"),
    segment_code: Optional[str] = typer.Option(None, "--segment-code"),
    is_qdii: bool = typer.Option(False, "--is-qdii"),
    data_source: Optional[str] = typer.Option(None, "--data-source"),
    sync: bool = typer.Option(False, "--sync", help="创建后立即回填历史净值（issue #90）"),
):
    """创建产品（自动计算 confirm_days，校验五维度适用矩阵）"""
    with cli_context() as db:
        from app.services import product_service

        product = product_service.create_product(
            db,
            code=code,
            market=market,
            name=name,
            product_type=product_type,
            asset_class_code=asset_class_code,
            region_code=region_code,
            style_code=style_code,
            size_code=size_code,
            segment_code=segment_code,
            is_qdii=is_qdii,
            data_source=data_source,
            sync_history=sync,
        )
        db.flush()
        db.refresh(product)
        data = serialize_model(product)
        sync_result = getattr(product, "sync_result", None)
        if sync_result is not None:
            data["sync_result"] = sync_result
        success(data=data)


@app.command("get")
def get_product(
    code: str = typer.Argument(...),
    market: Optional[str] = typer.Argument(None, help="市场类型（省略时自动解析；LOF 多市场须显式指定）"),
):
    """查看产品详情"""
    with cli_context() as db:
        from app.models.product import Product
        from app.services.product_service import resolve_product_market

        # #83：market 省略时经服务层解析（与 REST 同一实现）
        _, market = resolve_product_market(db, code, market)
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
    region_code: Optional[str] = typer.Option(None, "--region-code"),
    style_code: Optional[str] = typer.Option(None, "--style-code"),
    size_code: Optional[str] = typer.Option(None, "--size-code"),
    segment_code: Optional[str] = typer.Option(None, "--segment-code"),
    data_source: Optional[str] = typer.Option(None, "--data-source"),
):
    """更新产品信息（维度标签按合并后结果校验适用矩阵）"""
    with cli_context() as db:
        from app.services import product_service

        updates = {}
        if name is not None:
            updates["name"] = name
        if asset_class_code is not None:
            updates["asset_class_code"] = asset_class_code
        if region_code is not None:
            updates["region_code"] = region_code
        if style_code is not None:
            updates["style_code"] = style_code
        if size_code is not None:
            updates["size_code"] = size_code
        if segment_code is not None:
            updates["segment_code"] = segment_code
        if data_source is not None:
            updates["data_source"] = data_source
        if is_qdii is not None:
            updates["is_qdii"] = is_qdii

        product = product_service.update_product(db, code=code, market=market, updates=updates)
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
