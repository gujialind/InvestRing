"""issue #66 命名治理：现金金额与裸 date 字段重命名

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-28

字段重命名（语义化，消除歧义）：

- portfolio_position.amount      -> cash_amount（现金持仓金额，与 trade.amount 区分）
- manual_market_value.date       -> value_date
- trading_calendar.date          -> calendar_date
- price_record.date              -> price_date

不改动：trade.amount / subscription.amount / frozen_amount / market_value /
total_value 及已带语义前缀的日期字段（trade_date/confirm_date/apply_date/
ex_date/entitlement_date/snapshot_date）。

方言差异：
- MySQL 8 禁止重命名被 CHECK 约束引用的列，portfolio_position.amount 被
  check_nav_or_non_nav 引用，需先 drop CHECK、rename、再以新列名重建 CHECK；
  三张表的 date 重命名用 op.alter_column(new_column_name=...)，MySQL 8 的
  RENAME COLUMN 自动跟随索引/唯一约束（trading_calendar.date 的 unique+index、
  uix_price_record、uq_manual_market_value），无需重建。
- SQLite（>=3.25）RENAME COLUMN 自动重写 CHECK/UNIQUE/索引引用，直接 rename。

幂等设计：生产/CI 的启动顺序是先 `Base.metadata.create_all`（按当前模型
直接建出新列名），再从 base 执行 `alembic upgrade head`，因此迁移到达 0005
时列可能已经是新名。upgrade()/downgrade() 均先通过 inspector 检查源列是否
存在，仅在源列存在时才执行该表的 rename，否则整体跳过（no-op）；MySQL 分支
「先确认旧列存在才进入 drop CHECK -> rename -> 重建 CHECK 整块」，避免
MySQL DDL 隐式提交下 drop 成功而 rename 失败导致约束永久丢失，drop/重建
CHECK 前也各自检查约束存在性，容忍 CI 库处于「CHECK 已删」的中间态。
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


# (table, old_column, new_column)：三张表裸 date 重命名
DATE_RENAMES = [
    ("manual_market_value", "date", "value_date"),
    ("trading_calendar", "date", "calendar_date"),
    ("price_record", "date", "price_date"),
]


def _existing_columns(table: str) -> set:
    """实时查询表当前列名集合（每次新建 inspector，反映此前 DDL 的结果）"""
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table)}


def _has_check_constraint(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        constraints = inspector.get_check_constraints(table)
    except NotImplementedError:
        return False
    return any(ck.get("name") == name for ck in constraints)


def _rename_date_columns(is_mysql: bool, renames):
    for table, old, new in renames:
        # 幂等：源列不存在（create_all 已按目标列名建表）则跳过
        if old not in _existing_columns(table):
            continue
        if is_mysql:
            op.alter_column(
                table, old,
                new_column_name=new,
                existing_type=sa.Date(),
                existing_nullable=False,
            )
        else:
            op.execute(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")


def _rename_position_amount(is_mysql: bool, old: str, new: str):
    """portfolio_position 现金金额列重命名（幂等，MySQL 需先删 CHECK 再重建）"""
    # 幂等：旧列不存在（create_all 已按新列名建表）则整块跳过；
    # 「先检查列存在才进入整块」也规避了 MySQL DDL 隐式提交下
    # drop CHECK 成功而 rename 失败导致约束永久丢失的风险
    if old not in _existing_columns('portfolio_position'):
        return
    if is_mysql:
        # MySQL 8 禁止重命名被 CHECK 引用的列：先删 CHECK 再改名再重建。
        # drop 前检查约束存在性，容忍库处于「CHECK 已被删」的中间态
        if _has_check_constraint('portfolio_position', 'check_nav_or_non_nav'):
            op.drop_constraint('check_nav_or_non_nav', 'portfolio_position', type_='check')
        op.alter_column(
            'portfolio_position', old,
            new_column_name=new,
            existing_type=sa.Numeric(15, 4),
            existing_nullable=True,
        )
        if not _has_check_constraint('portfolio_position', 'check_nav_or_non_nav'):
            op.create_check_constraint(
                'check_nav_or_non_nav', 'portfolio_position',
                f'(shares IS NOT NULL AND {new} IS NULL) OR (shares IS NULL AND {new} IS NOT NULL)',
            )
    else:
        # SQLite >=3.25 RENAME COLUMN 自动重写 CHECK/UNIQUE 引用
        op.execute(f"ALTER TABLE portfolio_position RENAME COLUMN {old} TO {new}")


def upgrade():
    bind = op.get_bind()
    is_mysql = bind.dialect.name == "mysql"

    # portfolio_position.amount -> cash_amount
    _rename_position_amount(is_mysql, 'amount', 'cash_amount')

    # 三张表 date 重命名（索引/唯一约束自动跟随，无需重建）
    _rename_date_columns(is_mysql, DATE_RENAMES)


def downgrade():
    bind = op.get_bind()
    is_mysql = bind.dialect.name == "mysql"

    # 三张表 date 还原
    _rename_date_columns(
        is_mysql, [(t, new, old) for t, old, new in DATE_RENAMES]
    )

    # portfolio_position.cash_amount -> amount（MySQL 同样先删 CHECK 再重建）
    _rename_position_amount(is_mysql, 'cash_amount', 'amount')
