"""issue #128 资产分类体系正交维度重构（不可逆）

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-12

asset_classification 从扁平单级分类改造为维度值字典（dimension/name/sort_order），
product 按维度挂值（新增 region/style/size/segment 四列），portfolio_position
删除 asset_type 列（分类信息改为 positions API 读侧派生，快照不再承载）。

操作顺序（不可打乱，FK 约束与数据完整性依赖此前序）：
1. asset_classification 加 dimension/name/sort_order 列（幂等，存量库 ALTER；
   全新库由 create_all 按新模型建表，inspect 跳过）；
2. 插入全部维度值（双方言幂等；数据源自 app/constants/asset_dimensions.py）；
3. product 加 4 个维度列 + FK（幂等）；
4. product 回填：逐产品判定表 PRODUCT_DIMENSIONS 优先，未列入产品按旧 code
   经 OLD_CLASS_FALLBACK 兜底；CASH→ASSET_CASH；IN_TRANSIT 保持全 NULL；
5. 回填完整性校验（维度适用矩阵），失败 raise 整体中止——此处在删除任何
   旧数据之前，保证失败不留半成品（DML 回滚；注意 MySQL DDL 自动提交，
   故所有破坏性 DDL 均排在校验通过之后）；
6. 删除 18 条旧分类行、删 asset_classification 旧列；
7. DROP portfolio_position.asset_type。

幂等设计：所有 DDL 先经 inspector 检查；维度值插入双方言幂等（MySQL
ON DUPLICATE KEY UPDATE / SQLite INSERT OR IGNORE）；产品回填仅更新
asset_class_code 仍为旧码的行（重跑无副作用）。

不可逆说明：旧扁平分类行与 asset_type 列被物理删除，downgrade 不予支持
（沿用 0006 先例）。
"""
from alembic import op
import sqlalchemy as sa

from app.constants.asset_dimensions import (
    ASSET_DIMENSIONS,
    OLD_CLASS_FALLBACK,
    PRODUCT_DIMENSIONS,
)


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

_DIMENSION_COLUMNS = ("asset_class_code", "region_code", "style_code", "size_code", "segment_code")
_OLD_CLASS_CODES = tuple(OLD_CLASS_FALLBACK.keys())


def _existing_columns(table: str) -> set:
    """实时查询表当前列名集合（复用 0007 模式，反映此前 DDL 的结果）"""
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table)}


def _insert_dimension_values():
    """双方言幂等插入维度值字典（复用 0006 的方言分支模式）。

    存量库的 asset_classification 仍带旧 NOT NULL 列（asset_type/asset_category），
    插入时需顺带提供占位值（这些列与旧行在步骤 6 一并删除，占位值无实际语义）。
    """
    dialect = op.get_bind().dialect.name
    legacy_cols = _existing_columns('asset_classification') & {
        'asset_type', 'asset_category', 'asset_subcat', 'asset_name'}
    for code, dimension, name, sort_order, description in ASSET_DIMENSIONS:
        cols = ["code", "dimension", "name", "sort_order", "description"]
        params = {
            "code": code, "dimension": dimension, "name": name,
            "sort_order": sort_order, "description": description,
        }
        # 旧 NOT NULL 列占位（仅存量库；asset_type/asset_category 为 NOT NULL）
        for legacy in sorted(legacy_cols):
            cols.append(legacy)
            params[legacy] = name if legacy in ("asset_type", "asset_name") else dimension

        col_list = ", ".join(cols)
        val_list = ", ".join(f":{c}" for c in cols)
        if dialect == "mysql":
            op.execute(sa.text(
                f"INSERT INTO asset_classification ({col_list}) VALUES ({val_list}) "
                "ON DUPLICATE KEY UPDATE "
                "dimension=VALUES(dimension), name=VALUES(name), "
                "sort_order=VALUES(sort_order), description=VALUES(description)"
            ).bindparams(**params))
        else:
            op.execute(sa.text(
                f"INSERT OR IGNORE INTO asset_classification ({col_list}) VALUES ({val_list})"
            ).bindparams(**params))


def _backfill_products():
    """product 五维度回填：逐产品判定表优先，旧码兜底；仅处理仍为旧码的行（幂等）"""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT code, asset_class_code FROM product "
            "WHERE asset_class_code IN :old_codes"
        ).bindparams(sa.bindparam("old_codes", expanding=True)),
        {"old_codes": list(_OLD_CLASS_CODES)},
    ).fetchall()

    update_stmt = sa.text(
        "UPDATE product SET asset_class_code=:asset_class, region_code=:region, "
        "style_code=:style, size_code=:size, segment_code=:segment "
        "WHERE code=:code AND asset_class_code IN :old_codes"
    ).bindparams(sa.bindparam("old_codes", expanding=True))

    for code, old_class in rows:
        dims = PRODUCT_DIMENSIONS.get(code) or OLD_CLASS_FALLBACK[old_class]
        asset_class, region, style, size, segment = dims
        bind.execute(
            update_stmt,
            {
                "asset_class": asset_class, "region": region, "style": style,
                "size": size, "segment": segment, "code": code,
                "old_codes": list(_OLD_CLASS_CODES),
            },
        )


def _validate_backfill():
    """维度适用矩阵校验：任一产品违反即中止迁移（在删除旧数据之前）"""
    bind = op.get_bind()
    violations = []

    def _fetch(label: str, where: str) -> list:
        rows = bind.execute(
            sa.text(f"SELECT code FROM product WHERE {where}")
        ).fetchall()
        return [f"{label}: {[r[0] for r in rows]}"] if rows else []

    # 股票：region/style/size 必填
    violations += _fetch(
        "股票缺region/style/size",
        "asset_class_code='ASSET_STOCK' AND (region_code IS NULL OR style_code IS NULL OR size_code IS NULL)",
    )
    # 债券：region+segment 必填，style/size 必须 NULL
    violations += _fetch(
        "债券缺region/segment",
        "asset_class_code='ASSET_BOND' AND (region_code IS NULL OR segment_code IS NULL)",
    )
    # 商品/现金：region/style/size 必须 NULL
    violations += _fetch(
        "商品/现金维度应为NULL",
        "asset_class_code IN ('ASSET_COMMODITY','ASSET_CASH') "
        "AND (region_code IS NOT NULL OR style_code IS NOT NULL OR size_code IS NOT NULL)",
    )
    # 维度 code 必须存在于字典
    for col in _DIMENSION_COLUMNS:
        violations += _fetch(
            f"{col}引用不存在维度值",
            f"{col} IS NOT NULL AND {col} NOT IN (SELECT code FROM asset_classification)",
        )
    # 仍有未迁移的旧码（IN_TRANSIT 等 asset_class_code 为 NULL 的不受影响）
    old_codes = ", ".join(f"'{c}'" for c in _OLD_CLASS_CODES)
    violations += _fetch(
        "旧分类码未清退",
        f"asset_class_code IN ({old_codes})",
    )

    if violations:
        raise RuntimeError(
            "迁移 0008 产品维度回填校验失败，未删除任何旧数据：\n" + "\n".join(violations)
        )


def upgrade():
    # 1. asset_classification 新列（幂等；先可空加入，删除旧行后于步骤 6 收紧 NOT NULL）
    ac_cols = _existing_columns('asset_classification')
    added_dim_cols = 'dimension' not in ac_cols
    if added_dim_cols:
        op.add_column('asset_classification', sa.Column('dimension', sa.String(20), nullable=True))
        op.add_column('asset_classification', sa.Column('name', sa.String(50), nullable=True))
        op.add_column('asset_classification', sa.Column('sort_order', sa.Integer, nullable=True))

    # 2. 维度值字典（双方言幂等）
    _insert_dimension_values()

    # 3. product 四个维度列 + FK（幂等；batch 模式兼容 SQLite，MySQL 下即普通 ALTER）
    product_cols = _existing_columns('product')
    if 'region_code' not in product_cols:
        with op.batch_alter_table('product') as batch_op:
            for col in ("region_code", "style_code", "size_code", "segment_code"):
                batch_op.add_column(sa.Column(col, sa.String(30), nullable=True))
                batch_op.create_foreign_key(
                    f'fk_product_{col}', 'asset_classification', [col], ['code']
                )

    # 4. 回填 → 5. 校验（失败中止，尚未删除任何旧数据）
    _backfill_products()
    _validate_backfill()

    # 6. 清退旧分类行 + 删旧列（SQLite 经 batch 模式兼容 DROP COLUMN）
    op.get_bind().execute(
        sa.text("DELETE FROM asset_classification WHERE code IN :codes")
        .bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": list(_OLD_CLASS_CODES)},
    )
    ac_cols = _existing_columns('asset_classification')
    legacy_cols = [c for c in ('asset_type', 'asset_category', 'asset_subcat', 'asset_name') if c in ac_cols]
    if legacy_cols or added_dim_cols:
        with op.batch_alter_table('asset_classification') as batch_op:
            for col in legacy_cols:
                batch_op.drop_column(col)
            if added_dim_cols:
                # 旧行已清退、维度值均有 dimension/name，收紧与模型一致
                batch_op.alter_column('dimension', existing_type=sa.String(20), nullable=False)
                batch_op.alter_column('name', existing_type=sa.String(50), nullable=False)

    # 7. DROP portfolio_position.asset_type（快照分类改读侧派生）
    if 'asset_type' in _existing_columns('portfolio_position'):
        with op.batch_alter_table('portfolio_position') as batch_op:
            batch_op.drop_column('asset_type')


def downgrade():
    # 旧扁平分类行与 asset_type 列已物理删除，不可逆（沿用 0006 先例）
    raise NotImplementedError(
        "迁移 0008 不可逆：旧扁平分类与 portfolio_position.asset_type 已物理删除，"
        "回滚请使用数据库备份恢复"
    )
