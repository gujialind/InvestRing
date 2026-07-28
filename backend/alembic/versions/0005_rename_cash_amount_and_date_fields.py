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


def _rename_date_columns(is_mysql: bool, renames):
    for table, old, new in renames:
        if is_mysql:
            op.alter_column(
                table, old,
                new_column_name=new,
                existing_type=sa.Date(),
                existing_nullable=False,
            )
        else:
            op.execute(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")


def upgrade():
    bind = op.get_bind()
    is_mysql = bind.dialect.name == "mysql"

    # portfolio_position.amount -> cash_amount
    if is_mysql:
        # MySQL 8 禁止重命名被 CHECK 引用的列：先删 CHECK 再改名再重建
        op.drop_constraint('check_nav_or_non_nav', 'portfolio_position', type_='check')
        op.alter_column(
            'portfolio_position', 'amount',
            new_column_name='cash_amount',
            existing_type=sa.Numeric(15, 4),
            existing_nullable=True,
        )
        op.create_check_constraint(
            'check_nav_or_non_nav', 'portfolio_position',
            '(shares IS NOT NULL AND cash_amount IS NULL) OR (shares IS NULL AND cash_amount IS NOT NULL)',
        )
    else:
        # SQLite >=3.25 RENAME COLUMN 自动重写 CHECK/UNIQUE 引用
        op.execute("ALTER TABLE portfolio_position RENAME COLUMN amount TO cash_amount")

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
    if is_mysql:
        op.drop_constraint('check_nav_or_non_nav', 'portfolio_position', type_='check')
        op.alter_column(
            'portfolio_position', 'cash_amount',
            new_column_name='amount',
            existing_type=sa.Numeric(15, 4),
            existing_nullable=True,
        )
        op.create_check_constraint(
            'check_nav_or_non_nav', 'portfolio_position',
            '(shares IS NOT NULL AND amount IS NULL) OR (shares IS NULL AND amount IS NOT NULL)',
        )
    else:
        op.execute("ALTER TABLE portfolio_position RENAME COLUMN cash_amount TO amount")
