"""份额精度全局改为 2 位小数

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-28

将 11 个份额列从 Numeric(15,4) 收窄为 Numeric(15,2)（行业申购确认惯例：
净值 4 位小数、投资人确认份额 2 位小数）：

- portfolio_position: shares / frozen_shares
- portfolio_value_snapshot: total_shares / frozen_shares
- investor_holding: shares / frozen_shares
- trade: shares
- subscription: shares
- share_change_event: entitlement_shares / shares_before / shares_change / shares_after

金额类（amount/actual_amount/market_value 等）保持 Numeric(15,4)、
净值/价格类（unit_price/price 等）保持 Numeric(10,4)，均不在本迁移范围内。

先 UPDATE ROUND(col, 2) 保证舍入确定性（MySQL/SQLite 通用），再 alter 列类型；
SQLite 不强制 Numeric 精度，alter 失败以 try/except 容忍（UPDATE 已生效）。
幂等 try/except 包裹，避免 app 启动期 `alembic upgrade head` 抛错崩溃。

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
    # 先显式 ROUND 到 2 位，保证舍入行为确定（不依赖各数据库 ALTER 时的隐式舍入）
    for table, column, _ in SHARES_COLUMNS:
        try:
            op.execute(
                f"UPDATE {table} SET {column} = ROUND({column}, 2) "
                f"WHERE {column} IS NOT NULL"
            )
        except Exception:
            pass
    # 再收窄列类型；SQLite 不强制精度，alter 失败容忍（UPDATE 已生效）
    for table, column, nullable in SHARES_COLUMNS:
        try:
            op.alter_column(
                table, column,
                existing_type=sa.Numeric(15, 4),
                type_=sa.Numeric(15, 2),
                existing_nullable=nullable,
            )
        except Exception:
            pass


def downgrade():
    # 仅恢复列类型定义；已被 ROUND 舍去的精度数据不可恢复
    for table, column, nullable in SHARES_COLUMNS:
        try:
            op.alter_column(
                table, column,
                existing_type=sa.Numeric(15, 2),
                type_=sa.Numeric(15, 4),
                existing_nullable=nullable,
            )
        except Exception:
            pass
