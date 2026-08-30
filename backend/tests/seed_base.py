# ============================================================================
# 基础数据种子（单一事实来源）
# ============================================================================
# pytest（conftest._seed_base_data）与 CI E2E（scripts/seed_e2e.py）、
# 本地 E2E（scripts/run_e2e_backend.py）共用本模块，替代已退役的
# scripts/init_data.py（issue #222）。全部写入带存在性检查，幂等。
#
# 注意：本模块是测试/E2E 固件（含测试口令与启发式日历），不是生产种子——
# 生产基础数据由 alembic 迁移落库。
# ============================================================================

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Investor, Portfolio, Product, Platform,
    AssetClassification, AssetDimensionApplicability, AssetClassDimensionRule,
    TradingCalendar,
)
from app.constants.asset_dimensions import (
    ASSET_DIMENSIONS, PRODUCT_DIMENSIONS, DIMENSION_APPLICABILITY, DIMENSION_RULES,
)
from app.utils.security import get_password_hash


def seed_base_data(db: Session) -> None:
    """种子基础数据：维度字典、适用关系、平台、产品、日历、draft 组合、用户。

    调用方负责 commit/rollback/close 的事务外壳。
    """
    # 1. 资产分类维度值字典（issue #128，与迁移 0008 同源）
    for code, dimension, name, sort_order, description in ASSET_DIMENSIONS:
        if not db.query(AssetClassification).filter(AssetClassification.code == code).first():
            db.add(AssetClassification(
                code=code, dimension=dimension, name=name,
                sort_order=sort_order, description=description,
            ))
    db.commit()

    # 1b. 适用关系（issue #135 矩阵落库）：值级关联 + 维度级规则，
    #     与迁移 0009 同源（测试环境跳过 alembic，须在此种子）
    for value, classes in DIMENSION_APPLICABILITY.items():
        for asset_class in classes:
            if not db.query(AssetDimensionApplicability).filter_by(
                dimension_value_code=value, asset_class_code=asset_class
            ).first():
                db.add(AssetDimensionApplicability(
                    dimension_value_code=value,
                    asset_class_code=asset_class,
                ))
    for asset_class, rules in DIMENSION_RULES.items():
        for dimension, rule in rules.items():
            if not db.query(AssetClassDimensionRule).filter_by(
                asset_class_code=asset_class, dimension=dimension
            ).first():
                db.add(AssetClassDimensionRule(
                    asset_class_code=asset_class, dimension=dimension, rule=rule,
                ))
    db.commit()

    # 2. 平台
    platforms = [
        {"code": "MYCF", "name": "蚂蚁财富", "platform_type": "第三方平台"},
        {"code": "HBZQ", "name": "华宝证券", "platform_type": "券商"},
        {"code": "TTJJ", "name": "天天基金", "platform_type": "第三方平台"},
        {"code": "ZB", "name": "纸币", "platform_type": "其他"},
    ]
    for p in platforms:
        if not db.query(Platform).filter(Platform.code == p["code"]).first():
            db.add(Platform(**p))
    db.commit()

    # 3. 示例产品（精简版，仅用于测试；五维度标签取自 PRODUCT_DIMENSIONS 同源判定）
    def _dims(code):
        d = PRODUCT_DIMENSIONS[code]
        return {"asset_class_code": d[0], "region_code": d[1],
                "style_code": d[2], "size_code": d[3], "segment_code": d[4]}

    products = [
        {"code": "CASH", "market": "", "name": "现金类资产", "product_type": "CASH",
         "confirm_days": 0, "is_qdii": False, "nav_lag_days": 0, **_dims("CASH")},
        # #93: 在途资金虚拟产品（与 CASH 同构：market='', 五维度全 NULL）
        {"code": "IN_TRANSIT_BUY", "market": "", "name": "买入在途资金", "product_type": "IN_TRANSIT",
         "asset_class_code": None, "region_code": None, "style_code": None,
         "size_code": None, "segment_code": None, "confirm_days": 0, "is_qdii": False,
         "nav_lag_days": 0},
        {"code": "IN_TRANSIT_SELL", "market": "", "name": "卖出在途资金", "product_type": "IN_TRANSIT",
         "asset_class_code": None, "region_code": None, "style_code": None,
         "size_code": None, "segment_code": None, "confirm_days": 0, "is_qdii": False,
         "nav_lag_days": 0},
        {"code": "510300.SH", "market": "CN_EXCHANGE", "name": "沪深300ETF", "product_type": "ETF",
         "confirm_days": 0, "is_qdii": False, "nav_lag_days": 0,
         "asset_class_code": "ASSET_STOCK", "region_code": "REGION_CN",
         "style_code": "STYLE_BALANCED", "size_code": "SIZE_LARGE", "segment_code": "SEG_COMPOSITE"},
        {"code": "000300.OF", "market": "CN_OTC", "name": "沪深300联接A", "product_type": "OEF",
         "confirm_days": 1, "is_qdii": False, "nav_lag_days": 0,
         "asset_class_code": "ASSET_STOCK", "region_code": "REGION_CN",
         "style_code": "STYLE_BALANCED", "size_code": "SIZE_LARGE", "segment_code": "SEG_COMPOSITE"},
        # #259: LOF 一码双市场（产品选择器市场标识 E2E 种子；长名稳定触发截断）
        {"code": "161017.SZ", "market": "CN_EXCHANGE", "name": "富国中证500指数增强(LOF)A", "product_type": "LOF",
         "confirm_days": 0, "is_qdii": False, "nav_lag_days": 0,
         "asset_class_code": "ASSET_STOCK", "region_code": "REGION_CN",
         "style_code": "STYLE_BALANCED", "size_code": "SIZE_LARGE", "segment_code": "SEG_COMPOSITE"},
        {"code": "161017.OF", "market": "CN_OTC", "name": "富国中证500指数增强(LOF)A", "product_type": "LOF",
         "confirm_days": 1, "is_qdii": False, "nav_lag_days": 0,
         "asset_class_code": "ASSET_STOCK", "region_code": "REGION_CN",
         "style_code": "STYLE_BALANCED", "size_code": "SIZE_LARGE", "segment_code": "SEG_COMPOSITE"},
        # 场外 QDII：快照估值取 T-1 交易日净值（issue #228 nav_lag_days=1）
        {"code": "270042.OF", "market": "CN_OTC", "name": "广发纳指100(QDII)A", "product_type": "OEF",
         "confirm_days": 2, "is_qdii": True, "nav_lag_days": 1, **_dims("270042.OF")},
        {"code": "1001767344", "market": "HK_MUTUAL", "name": "摩根国际债券人民币对冲", "product_type": "OEF",
         "confirm_days": 1, "is_qdii": False, "nav_lag_days": 0,
         "data_source": "akshare", **_dims("1001767344")},
    ]
    for p in products:
        if not db.query(Product).filter(
            Product.code == p["code"], Product.market == p["market"]
        ).first():
            db.add(Product(**p))
    db.commit()

    # 4. 交易日历（2025-01-01 到 2026-12-31，工作日为交易日）
    start = date(2025, 1, 1)
    end = date(2026, 12, 31)
    existing_count = db.query(TradingCalendar).count()
    if existing_count == 0:
        current = start
        while current <= end:
            is_weekday = current.weekday() < 5  # Mon-Fri
            db.add(TradingCalendar(
                calendar_date=current,
                is_open=is_weekday,
                exchange="SSE",
            ))
            current += timedelta(days=1)
        db.commit()

    # 5. draft 组合（前端 E2E 冒烟依赖：无组合时业务 spec 优雅 skip，
    #    缺少它会让 datepicker/platform-select/regression 用例在 CI 静默跳过）
    if not db.query(Portfolio).filter(Portfolio.code == "E2E_PORT").first():
        db.add(Portfolio(
            code="E2E_PORT",
            name="E2E 冒烟组合",
            description="测试/E2E 种子 draft 组合（issue #222）",
        ))
        db.commit()

    # 6. 管理员用户（密码：admin@2026）
    if not db.query(Investor).filter(Investor.code == "ADMIN").first():
        db.add(Investor(
            code="ADMIN",
            name="测试管理员",
            role="admin",
            password_hash=get_password_hash("admin@2026"),
        ))
        db.commit()

    # 7. 普通用户（viewer，密码：viewer123）
    if not db.query(Investor).filter(Investor.code == "VIEWER").first():
        db.add(Investor(
            code="VIEWER",
            name="测试投资人",
            role="viewer",
            password_hash=get_password_hash("viewer123"),
        ))
        db.commit()
