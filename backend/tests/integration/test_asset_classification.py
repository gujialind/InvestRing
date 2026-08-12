# ============================================================================
# 集成测试：资产分类正交维度字典 + 迁移 0008（issue #128）
# ============================================================================
# 覆盖：
# - 测试种子维度字典与 ASSET_DIMENSIONS 一致（旧扁平码不存在）
# - 迁移 0008 upgrade：asset_classification 加列 + 维度值插入 + product 回填
#   （逐产品判定表优先 / 旧码兜底）+ 旧行清退 + portfolio_position 删 asset_type
# - 维度适用矩阵校验：股票必填 region/style/size、商品/现金维度 NULL
# - 迁移幂等：重复 upgrade 结果不变
# - 校验失败中止：存量违例产品时 raise，且旧分类行未被删除（不留半成品）
# - downgrade 不可逆（NotImplementedError）
# ============================================================================

import importlib.util
import os

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine

from app.constants.asset_dimensions import ASSET_DIMENSIONS, PRODUCT_DIMENSIONS
from app.models.asset_classification import AssetClassification


MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "alembic", "versions", "0008_asset_dimension_refactor.py",
)

_OLD_CODES = [
    "STOCK_CN_LARGE", "STOCK_CN_SMALL", "STOCK_CN_VALUE", "STOCK_CN_GROWTH",
    "STOCK_CN_MIXED", "STOCK_HK_LARGE", "STOCK_HK_SMALL", "STOCK_US",
    "STOCK_EU", "STOCK_JP", "STOCK_GLOBAL", "BOND_SHORT", "BOND_LONG",
    "BOND_MIXED", "BOND_US", "BOND_GLOBAL", "GOLD", "CASH",
]


def _load_migration():
    """按文件路径加载迁移 0008 模块（文件名以数字开头，无法常规 import）"""
    spec = importlib.util.spec_from_file_location("migration_0008", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_old_schema(engine, products):
    """构造 0008 之前的旧版三表（仅迁移涉及的列）并插入旧种子与产品"""
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE asset_classification ("
            " code VARCHAR(30) PRIMARY KEY,"
            " asset_type VARCHAR(20) NOT NULL,"
            " asset_category VARCHAR(50) NOT NULL,"
            " asset_subcat VARCHAR(50),"
            " asset_name VARCHAR(50),"
            " description TEXT"
            ")"
        ))
        conn.execute(sa.text(
            "CREATE TABLE product ("
            " code VARCHAR(20) PRIMARY KEY,"
            " market VARCHAR(20),"
            " name VARCHAR(100) NOT NULL,"
            " product_type VARCHAR(20) NOT NULL,"
            " asset_class_code VARCHAR(30),"
            " confirm_days INTEGER,"
            " is_qdii BOOLEAN"
            ")"
        ))
        conn.execute(sa.text(
            "CREATE TABLE portfolio_position ("
            " id INTEGER PRIMARY KEY,"
            " portfolio_code VARCHAR(20) NOT NULL,"
            " product_code VARCHAR(20) NOT NULL,"
            " market VARCHAR(20) NOT NULL,"
            " asset_type VARCHAR(20),"
            " snapshot_date DATE NOT NULL"
            ")"
        ))
        for code in _OLD_CODES:
            conn.execute(
                sa.text(
                    "INSERT INTO asset_classification (code, asset_type, asset_category)"
                    " VALUES (:code, '股票', '测试')"
                ).bindparams(code=code)
            )
        for code, old_class in products:
            conn.execute(
                sa.text(
                    "INSERT INTO product (code, market, name, product_type, asset_class_code)"
                    " VALUES (:code, 'CN_OTC', '测试产品', 'OEF', :old_class)"
                ).bindparams(code=code, old_class=old_class)
            )
        conn.execute(sa.text(
            "INSERT INTO portfolio_position"
            " (id, portfolio_code, product_code, market, asset_type, snapshot_date)"
            " VALUES (1, 'P1', 'CASH', '', 'cash', '2025-11-03')"
        ))


def _run_upgrade(engine, migration):
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()


def _read_product_dims(engine):
    with engine.connect() as conn:
        result = conn.execute(sa.text(
            "SELECT code, asset_class_code, region_code, style_code, size_code, segment_code"
            " FROM product"
        ))
        return {r[0]: r[1:] for r in result}


_SAMPLE_PRODUCTS = [
    ("510300.SH", "STOCK_CN_LARGE"),   # 不在逐产品判定表 → 旧码兜底
    ("513050.SH", "STOCK_GLOBAL"),     # 判定表：中概互联 → 中国/互联网
    ("518880.SH", "GOLD"),             # 判定表：黄金 → 商品
    ("CASH", "CASH"),                  # 判定表：现金
    ("IN_TRANSIT_BUY", None),          # 无分类：不迁移、保持全 NULL
]


class TestDimensionSeed:
    """测试种子（conftest._seed_base_data）与 ASSET_DIMENSIONS 一致"""

    def test_seed_dimensions_match_constants(self, test_db):
        rows = test_db.query(AssetClassification).all()
        by_code = {row.code: row for row in rows}
        assert len(by_code) == len(ASSET_DIMENSIONS)
        for code, dimension, name, sort_order, _ in ASSET_DIMENSIONS:
            row = by_code[code]
            assert row.dimension == dimension
            assert row.name == name
            assert row.sort_order == sort_order
        # 旧扁平码（含僵尸分类）不存在
        for old in _OLD_CODES:
            assert old not in by_code


class TestMigration0008:
    """迁移 0008：维度字典 + 回填 + 校验 + 删列（SQLite 方言）"""

    def test_upgrade_full_flow(self):
        migration = _load_migration()
        engine = create_engine("sqlite:///:memory:")
        _create_old_schema(engine, _SAMPLE_PRODUCTS)

        _run_upgrade(engine, migration)

        # asset_classification：新列存在、旧列删除
        ac_cols = {c["name"] for c in sa.inspect(engine).get_columns("asset_classification")}
        assert {"dimension", "name", "sort_order"} <= ac_cols
        assert not {"asset_type", "asset_category", "asset_subcat", "asset_name"} & ac_cols

        # 维度值字典完整、旧行清退
        with engine.connect() as conn:
            codes = {r[0] for r in conn.execute(sa.text("SELECT code FROM asset_classification"))}
        assert codes == {code for code, *_ in ASSET_DIMENSIONS}
        assert "STOCK_EU" not in codes and "STOCK_HK_SMALL" not in codes

        # product 回填：兜底 vs 逐产品判定
        dims = _read_product_dims(engine)
        assert dims["510300.SH"] == (
            "ASSET_STOCK", "REGION_CN", "STYLE_BALANCED", "SIZE_LARGE", "SEG_COMPOSITE")
        assert dims["513050.SH"] == (
            "ASSET_STOCK", "REGION_CN", "STYLE_GROWTH", "SIZE_LARGE", "SEG_INTERNET")
        assert dims["518880.SH"] == ("ASSET_COMMODITY", None, None, None, "SEG_GOLD")
        assert dims["CASH"] == ("ASSET_CASH", None, None, None, None)
        assert dims["IN_TRANSIT_BUY"] == (None, None, None, None, None)

        # portfolio_position.asset_type 已删除
        pp_cols = {c["name"] for c in sa.inspect(engine).get_columns("portfolio_position")}
        assert "asset_type" not in pp_cols

    def test_upgrade_idempotent(self):
        """重复执行 upgrade 结果不变"""
        migration = _load_migration()
        engine = create_engine("sqlite:///:memory:")
        _create_old_schema(engine, _SAMPLE_PRODUCTS)

        _run_upgrade(engine, migration)
        first = _read_product_dims(engine)
        _run_upgrade(engine, migration)
        second = _read_product_dims(engine)

        assert first == second
        with engine.connect() as conn:
            count = conn.execute(sa.text("SELECT COUNT(*) FROM asset_classification")).scalar()
        assert count == len(ASSET_DIMENSIONS)

    def test_validation_failure_aborts_before_delete(self):
        """存量违例产品（股票缺 region）→ raise 且旧分类行未被删除"""
        migration = _load_migration()
        engine = create_engine("sqlite:///:memory:")
        _create_old_schema(engine, _SAMPLE_PRODUCTS)
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO product (code, market, name, product_type, asset_class_code)"
                " VALUES ('BROKEN.OF', 'CN_OTC', '违例产品', 'OEF', 'ASSET_STOCK')"
            ))

        with pytest.raises(RuntimeError, match="回填校验失败"):
            _run_upgrade(engine, migration)

        # 中止点在所有破坏性操作之前：旧分类行与旧列仍在
        with engine.connect() as conn:
            old_count = conn.execute(
                sa.text("SELECT COUNT(*) FROM asset_classification WHERE code IN ("
                        + ",".join(f"'{c}'" for c in _OLD_CODES) + ")")
            ).scalar()
        assert old_count == len(_OLD_CODES)
        ac_cols = {c["name"] for c in sa.inspect(engine).get_columns("asset_classification")}
        assert "asset_type" in ac_cols

    def test_downgrade_not_supported(self):
        migration = _load_migration()
        with pytest.raises(NotImplementedError):
            migration.downgrade()


class TestProductDimensionMap:
    """逐产品判定表自洽性（验收断言：124 只全覆盖、维度适用矩阵、点名判定）"""

    def test_all_dimensions_reference_valid_values(self):
        valid = {code for code, *_ in ASSET_DIMENSIONS}
        for code, dims in PRODUCT_DIMENSIONS.items():
            for dim in dims:
                assert dim is None or dim in valid, f"{code} 引用不存在维度值 {dim}"

    def test_applicability_matrix(self):
        for code, (asset, region, style, size, segment) in PRODUCT_DIMENSIONS.items():
            if asset == "ASSET_STOCK":
                assert region and style and size, f"{code} 股票缺 region/style/size"
            elif asset == "ASSET_BOND":
                assert region and segment, f"{code} 债券缺 region/segment"
                assert style is None and size is None
            elif asset in ("ASSET_COMMODITY", "ASSET_CASH"):
                assert region is None and style is None and size is None

    def test_named_judgments(self):
        """中概互联 3 只→中国；广发全球医疗→全球；标普油气→美国；黄金→商品"""
        assert PRODUCT_DIMENSIONS["513050.SH"][1] == "REGION_CN"
        assert PRODUCT_DIMENSIONS["164906.SZ"][1] == "REGION_CN"
        assert PRODUCT_DIMENSIONS["006327.OF"][1] == "REGION_CN"
        assert PRODUCT_DIMENSIONS["000369.OF"][1] == "REGION_GLOBAL"
        assert PRODUCT_DIMENSIONS["162411.SZ"][1] == "REGION_US"
        assert PRODUCT_DIMENSIONS["518880.SH"][0] == "ASSET_COMMODITY"
        assert PRODUCT_DIMENSIONS["518880.SH"][4] == "SEG_GOLD"
        # 用户确认的 style 判定
        for code in ("519062.OF", "270002.OF", "519697.OF"):
            assert PRODUCT_DIMENSIONS[code][2] == "STYLE_BALANCED"
        assert PRODUCT_DIMENSIONS["512400.SH"][2] == "STYLE_VALUE"
