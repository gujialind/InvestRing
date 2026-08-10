# ============================================================================
# 集成测试：asset_classification.asset_name (issue #98, test_asset_classification.py)
# ============================================================================
# 覆盖：
# - 测试种子分类 asset_name 与 ASSET_NAME_MAP 一致（含 CASH 行）
# - 迁移 0007 upgrade：加列 + 回填 18 条种子分类
# - 迁移幂等：upgrade 重复执行行值不变
# - 回填不覆盖非 NULL 既有值（人工修改保留）
# - downgrade 移除 asset_name 列
# ============================================================================

import importlib.util
import os

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine

from app.constants.asset_names import ASSET_NAME_MAP
from app.models.asset_classification import AssetClassification


MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "alembic", "versions", "0007_asset_classification_asset_name.py",
)


def _load_migration():
    """按文件路径加载迁移 0007 模块（文件名以数字开头，无法常规 import）"""
    spec = importlib.util.spec_from_file_location("migration_0007", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_old_schema_table(engine):
    """构造 asset_name 之前的旧版 asset_classification 表并插入 18 条种子"""
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE asset_classification ("
            " code VARCHAR(30) PRIMARY KEY,"
            " asset_type VARCHAR(20) NOT NULL,"
            " asset_category VARCHAR(50) NOT NULL,"
            " asset_subcat VARCHAR(50),"
            " description TEXT"
            ")"
        ))
        for code in ASSET_NAME_MAP:
            conn.execute(
                sa.text(
                    "INSERT INTO asset_classification"
                    " (code, asset_type, asset_category) VALUES (:code, '股票', '测试')"
                ).bindparams(code=code)
            )


class TestSeedAssetName:
    """测试种子（conftest._seed_base_data）asset_name 与映射表一致"""

    def test_seed_asset_names_match_map(self, test_db):
        rows = test_db.query(AssetClassification).all()
        assert len(rows) >= 9  # conftest 种子 9 条
        by_code = {row.code: row for row in rows}
        # conftest 种子必须覆盖 CASH 行
        assert "CASH" in by_code
        for code, row in by_code.items():
            if code in ASSET_NAME_MAP:
                assert row.asset_name == ASSET_NAME_MAP[code], (
                    f"{code} asset_name 应为 {ASSET_NAME_MAP[code]!r}，实际 {row.asset_name!r}"
                )


class TestMigration0007:
    """迁移 0007：加列 + 回填 + 幂等 + downgrade（SQLite 方言）"""

    def _run_upgrade(self, engine, migration):
        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                migration.upgrade()

    def _read_rows(self, engine):
        with engine.connect() as conn:
            result = conn.execute(
                sa.text("SELECT code, asset_name FROM asset_classification")
            )
            return {code: name for code, name in result}

    def test_upgrade_adds_column_and_backfills(self):
        migration = _load_migration()
        engine = create_engine("sqlite:///:memory:")
        _create_old_schema_table(engine)

        self._run_upgrade(engine, migration)

        columns = {c["name"] for c in sa.inspect(engine).get_columns("asset_classification")}
        assert "asset_name" in columns
        rows = self._read_rows(engine)
        assert rows == ASSET_NAME_MAP  # 18 条全部回填且与映射一致

    def test_upgrade_idempotent(self):
        """重复执行 upgrade（模拟跑两次）行值不变"""
        migration = _load_migration()
        engine = create_engine("sqlite:///:memory:")
        _create_old_schema_table(engine)

        self._run_upgrade(engine, migration)
        first = self._read_rows(engine)
        self._run_upgrade(engine, migration)  # 第二次：列已存在 + 无 NULL 行
        second = self._read_rows(engine)

        assert first == second == ASSET_NAME_MAP

    def test_backfill_preserves_manual_values(self):
        """回填仅补 NULL 行，不覆盖人工改过的 asset_name"""
        migration = _load_migration()
        engine = create_engine("sqlite:///:memory:")
        _create_old_schema_table(engine)
        # 先加列并人工改一行，再跑迁移（模拟 create_all 已建列的场景）
        with engine.begin() as conn:
            conn.execute(sa.text(
                "ALTER TABLE asset_classification ADD COLUMN asset_name VARCHAR(50)"
            ))
            conn.execute(sa.text(
                "UPDATE asset_classification SET asset_name = '人工修改' "
                "WHERE code = 'STOCK_CN_LARGE'"
            ))

        self._run_upgrade(engine, migration)

        rows = self._read_rows(engine)
        assert rows["STOCK_CN_LARGE"] == "人工修改"  # 非 NULL 行不被覆盖
        for code, name in ASSET_NAME_MAP.items():
            if code != "STOCK_CN_LARGE":
                assert rows[code] == name

    def test_downgrade_drops_column(self):
        migration = _load_migration()
        engine = create_engine("sqlite:///:memory:")
        _create_old_schema_table(engine)

        self._run_upgrade(engine, migration)
        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                migration.downgrade()

        columns = {c["name"] for c in sa.inspect(engine).get_columns("asset_classification")}
        assert "asset_name" not in columns
