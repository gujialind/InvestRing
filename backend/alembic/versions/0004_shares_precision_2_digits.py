"""份额精度全局改为 2 位小数

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-28

将 12 个份额列从 Numeric(15,4) 收窄为 Numeric(15,2)（行业申购确认惯例：
净值 4 位小数、投资人确认份额 2 位小数）：

- portfolio_position: shares / frozen_shares
- portfolio_value_snapshot: total_shares / frozen_shares
- investor_holding: shares / frozen_shares
- trade: shares
- subscription: shares
- share_change_event: entitlement_shares / shares_before / shares_change / shares_after

金额类（amount/actual_amount/market_value 等）保持 Numeric(15,4)、
净值/价格类（unit_price/price 等）保持 Numeric(10,4)，均不在本迁移范围内。

先 UPDATE 显式截断到 2 位保证舍入确定性，再 alter 列类型；历史数据采用与
运行时 quantize_shares（ROUND_DOWN）一致的「向零截断」策略，不用 ROUND
半进位：MySQL 用 TRUNCATE(col, 2)，SQLite 等无 TRUNCATE 的方言用
CAST(col * 100 AS INTEGER) / 100（CAST 为 INTEGER 即向零截断，含负数）。
UPDATE 失败必须抛出；仅 SQLite 下容忍 alter 失败（SQLite 不强制 Numeric
精度，UPDATE 已生效），其他方言 alter 失败同样抛出，避免静默吞错。

注：本迁移仅改份额精度，不涉及 issue #66 命名治理；#66 若做 DB 字段重命名
另开迁移（如 0005）。
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


# (table, column, nullable)：nullable 与 models 现状保持一致
SHARES_COLUMNS = [
    ("portfolio_position", "shares", True),
    ("portfolio_position", "frozen_shares", True),
    ("portfolio_value_snapshot", "total_shares", False),
    ("portfolio_value_snapshot", "frozen_shares", True),
    ("investor_holding", "shares", False),
    ("investor_holding", "frozen_shares", True),
    ("trade", "shares", True),
    ("subscription", "shares", True),
    ("share_change_event", "entitlement_shares", True),
    ("share_change_event", "shares_before", True),
    ("share_change_event", "shares_change", True),
    ("share_change_event", "shares_after", True),
]


def upgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    is_mysql = bind.dialect.name == "mysql"

    # 先显式截断到 2 位，保证舍入行为确定（不依赖各数据库 ALTER 时的隐式舍入）。
    # 历史数据采用与运行时 quantize_shares（ROUND_DOWN）一致的「向零截断」策略，
    # 不用 ROUND 半进位。UPDATE 在所有方言都应成功，失败必须抛出。
    for table, column, _ in SHARES_COLUMNS:
        if is_mysql:
            op.execute(
                f"UPDATE {table} SET {column} = TRUNCATE({column}, 2) "
                f"WHERE {column} IS NOT NULL"
            )
        else:
            # SQLite 等无 TRUNCATE 的方言：CAST 为 INTEGER 即向零截断（含负数），
            # 与 ROUND_DOWN 语义一致
            op.execute(
                f"UPDATE {table} SET {column} = "
                f"CAST(CAST({column} * 100 AS INTEGER) AS REAL) / 100.0 "
                f"WHERE {column} IS NOT NULL"
            )
    # 再收窄列类型；仅 SQLite 容忍 alter 失败（不强制 Numeric 精度，UPDATE 已生效），
    # 其他方言失败必须抛出，避免 revision 前进但列未收窄的静默吞错
    for table, column, nullable in SHARES_COLUMNS:
        try:
            op.alter_column(
                table, column,
                existing_type=sa.Numeric(15, 4),
                type_=sa.Numeric(15, 2),
                existing_nullable=nullable,
            )
        except Exception:
            if is_sqlite:
                print(
                    f"WARN: alter_column {table}.{column} failed on SQLite, "
                    "tolerated (SQLite does not enforce Numeric precision; "
                    "UPDATE truncation already applied)"
                )
            else:
                raise


def downgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 仅恢复列类型定义；已被截断舍去的精度数据不可恢复。
    # 仅 SQLite 容忍 alter 失败，其他方言失败必须抛出
    for table, column, nullable in SHARES_COLUMNS:
        try:
            op.alter_column(
                table, column,
                existing_type=sa.Numeric(15, 2),
                type_=sa.Numeric(15, 4),
                existing_nullable=nullable,
            )
        except Exception:
            if is_sqlite:
                print(
                    f"WARN: alter_column {table}.{column} failed on SQLite, "
                    "tolerated (SQLite does not enforce Numeric precision)"
                )
            else:
                raise
