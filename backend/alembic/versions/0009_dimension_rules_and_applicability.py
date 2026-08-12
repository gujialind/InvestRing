"""issue #135 资产分类管理：维度规则表 + 值级适用关联表 + is_active 软失效

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-13

1. asset_classification 加 is_active 列（软失效：停用值不下拉、不通过新赋值校验，
   存量引用不受影响；server_default 回填存量为 active）；
2. 新建 asset_dimension_applicability（维度值 ↔ asset_class 多对多，值级适用性），
   按 DIMENSION_APPLICABILITY 回填；
3. 新建 asset_class_dimension_rule（asset_class × 维度三态规则，维度级矩阵落库：
   required/optional，无行 = forbidden），按 DIMENSION_RULES 回填。

两表数据源自 app/constants/asset_dimensions.py（沿用 0008 import 常量模式；
init_data.py、tests/conftest.py 三方同源）。回填后校验（先于任何后续操作）：
- 每个非 asset_class 维度值至少有 1 条适用关联（否则值级校验下该值不可用）；
- 存量产品五维引用全部通过值级适用校验（否则中止，不留半成品——本迁移纯增量，
  DML 回滚即复原；注意 MySQL DDL 自动提交，故校验排在建表之后、无任何破坏操作）。

幂等设计：DDL 先经 inspector 检查；种子按主键查缺补插（Python 侧，双方言通用）。

downgrade 支持：纯增量（删两表 + 删 is_active 列）。
"""
from alembic import op
import sqlalchemy as sa

from app.constants.asset_dimensions import (
    DIMENSION_APPLICABILITY,
    DIMENSION_RULES,
)


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

_DIMENSION_FIELDS = ("region_code", "style_code", "size_code", "segment_code")
_FIELD_TO_DIMENSION = {
    "region_code": "region", "style_code": "style",
    "size_code": "size", "segment_code": "segment",
}


def _existing_tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table: str) -> set:
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table)}


def _seed_applicability():
    """值级适用关联回填：按 (value, class) 主键查缺补插（幂等）"""
    bind = op.get_bind()
    existing = {
        (r[0], r[1])
        for r in bind.execute(sa.text(
            "SELECT dimension_value_code, asset_class_code FROM asset_dimension_applicability"
        ))
    }
    stmt = sa.text(
        "INSERT INTO asset_dimension_applicability (dimension_value_code, asset_class_code)"
        " VALUES (:value, :class)"
    )
    for value, classes in DIMENSION_APPLICABILITY.items():
        for asset_class in classes:
            if (value, asset_class) not in existing:
                bind.execute(stmt, {"value": value, "class": asset_class})


def _seed_rules():
    """维度级规则回填：按 (class, dimension) 主键查缺补插（幂等）"""
    bind = op.get_bind()
    existing = {
        (r[0], r[1])
        for r in bind.execute(sa.text(
            "SELECT asset_class_code, dimension FROM asset_class_dimension_rule"
        ))
    }
    stmt = sa.text(
        "INSERT INTO asset_class_dimension_rule (asset_class_code, dimension, rule)"
        " VALUES (:class, :dimension, :rule)"
    )
    for asset_class, rules in DIMENSION_RULES.items():
        for dimension, rule in rules.items():
            if (asset_class, dimension) not in existing:
                bind.execute(stmt, {"class": asset_class, "dimension": dimension, "rule": rule})


def _validate_backfill():
    """回填校验：字典覆盖完整 + 存量产品通过值级适用校验；失败 raise 中止"""
    bind = op.get_bind()
    violations = []

    # 1. 每个非 asset_class 维度值至少有 1 条适用关联
    rows = bind.execute(sa.text(
        "SELECT code FROM asset_classification WHERE dimension != 'asset_class'"
        " AND code NOT IN (SELECT dimension_value_code FROM asset_dimension_applicability)"
    )).fetchall()
    if rows:
        violations.append(f"维度值缺适用关联: {[r[0] for r in rows]}")

    # 2. 存量产品值级适用校验：(维度值, 产品 asset_class) 必须有关联行
    for field in _DIMENSION_FIELDS:
        rows = bind.execute(sa.text(
            f"SELECT code, {field} FROM product"
            f" WHERE {field} IS NOT NULL AND asset_class_code IS NOT NULL"
            f" AND NOT EXISTS ("
            f"   SELECT 1 FROM asset_dimension_applicability a"
            f"   WHERE a.dimension_value_code = product.{field}"
            f"     AND a.asset_class_code = product.asset_class_code)"
        )).fetchall()
        if rows:
            violations.append(
                f"{field} 值级适用违例: {[(r[0], r[1]) for r in rows]}"
            )

    if violations:
        raise RuntimeError(
            "迁移 0009 适用关系回填校验失败（未做任何破坏性操作）：\n" + "\n".join(violations)
        )


def upgrade():
    # 1. is_active 软失效列（幂等；server_default 回填存量为 active）
    if 'is_active' not in _existing_columns('asset_classification'):
        with op.batch_alter_table('asset_classification') as batch_op:
            batch_op.add_column(sa.Column(
                'is_active', sa.Boolean(), nullable=False, server_default=sa.true(),
            ))

    tables = _existing_tables()

    # 2. 值级适用关联表
    if 'asset_dimension_applicability' not in tables:
        op.create_table(
            'asset_dimension_applicability',
            sa.Column('dimension_value_code', sa.String(30), nullable=False),
            sa.Column('asset_class_code', sa.String(30), nullable=False),
            sa.ForeignKeyConstraint(
                ['dimension_value_code'], ['asset_classification.code'],
                name='fk_applicability_value', ondelete='RESTRICT',
            ),
            sa.ForeignKeyConstraint(
                ['asset_class_code'], ['asset_classification.code'],
                name='fk_applicability_class', ondelete='RESTRICT',
            ),
            sa.PrimaryKeyConstraint(
                'dimension_value_code', 'asset_class_code', name='pk_applicability',
            ),
        )
        op.create_index(
            'ix_applicability_asset_class',
            'asset_dimension_applicability', ['asset_class_code'],
        )

    # 3. 维度级规则表
    if 'asset_class_dimension_rule' not in tables:
        op.create_table(
            'asset_class_dimension_rule',
            sa.Column('asset_class_code', sa.String(30), nullable=False),
            sa.Column('dimension', sa.String(20), nullable=False),
            sa.Column('rule', sa.String(10), nullable=False),
            sa.ForeignKeyConstraint(
                ['asset_class_code'], ['asset_classification.code'],
                name='fk_rule_class', ondelete='RESTRICT',
            ),
            sa.PrimaryKeyConstraint('asset_class_code', 'dimension', name='pk_dimension_rule'),
        )

    # 4. 回填（幂等）→ 5. 校验（失败中止；纯增量无任何破坏操作）
    _seed_applicability()
    _seed_rules()
    _validate_backfill()


def downgrade():
    # 纯增量迁移，可回滚：删两表 + 删 is_active 列
    tables = _existing_tables()
    if 'asset_class_dimension_rule' in tables:
        op.drop_table('asset_class_dimension_rule')
    if 'asset_dimension_applicability' in tables:
        op.drop_table('asset_dimension_applicability')
    if 'is_active' in _existing_columns('asset_classification'):
        with op.batch_alter_table('asset_classification') as batch_op:
            batch_op.drop_column('is_active')
