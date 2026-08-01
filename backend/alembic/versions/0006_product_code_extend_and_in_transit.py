"""issue #93 在途资金模型：product_code 扩展 + in_transit_total 列

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-01

为 issue #93（在途资金模型）准备数据基础：

1. 扩展 product_code 字段（String(10) → String(20)）：
   支持 IN_TRANSIT_BUY / IN_TRANSIT_SELL 等长命名。
   涉及 8 处列（product.code + 7 张表的 product_code/cash_product_code）。
   product.code 是 ForeignKeyConstraint 引用方，同步扩展后 FK 关系不变
  （portfolio_position / trade / price_record / share_change_event 均以
   (product_code, market) 复合 FK 引用 product.(code, market)）。

2. 新增 portfolio_value_snapshot.in_transit_total 列：
   Numeric(15, 4)，server_default='0'，记录在途资金总额。

3. 插入两条种子产品记录（IN_TRANSIT_BUY / IN_TRANSIT_SELL）：
   与 CASH 虚拟产品同构（market=''），product_type='IN_TRANSIT'，
   confirm_days=0，is_qdii=0。CASH 经 init_data.py 脚本种子，IN_TRANSIT
   经本迁移种子（部署时 alembic upgrade head 自动执行）。

幂等设计：
- 全新库经 create_all 已按 String(20) 建列，alter_column 对 MySQL 为
  no-op（MODIFY VARCHAR(20) 对已是 VARCHAR(20) 的列无影响）。
- add_column 用 try/except 兼容 create_all 已建列。
- 种子产品用 ON DUPLICATE KEY UPDATE（MySQL）/ INSERT OR IGNORE（SQLite）
  保证幂等。
- SQLite 不强制 String 长度，alter_column 失败可容忍（与 0004 同策略）。
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


# product_code String(10) → String(20)：支持 IN_TRANSIT_BUY / IN_TRANSIT_SELL 命名
PRODUCT_CODE_COLUMNS = [
    ('product', 'code'),
    ('portfolio_position', 'product_code'),
    ('trade', 'product_code'),
    ('price_record', 'product_code'),
    ('manual_market_value', 'product_code'),
    ('nav_sync_detail', 'product_code'),
    ('share_change_event', 'product_code'),
    ('share_change_event', 'cash_product_code'),
]


def upgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    is_mysql = bind.dialect.name == "mysql"

    # 1. 扩展 product_code 字段（8处）
    # MySQL: MODIFY COLUMN 是元数据操作，无数据变更；对已是 VARCHAR(20) 的列为 no-op
    # SQLite: 不强制 String 长度，alter 失败可容忍（与 0004 同策略）
    for table, col in PRODUCT_CODE_COLUMNS:
        try:
            kwargs = {}
            # product.code 是主键，MySQL 要求主键列必须 NOT NULL
            if (table, col) == ('product', 'code'):
                kwargs['nullable'] = False
            op.alter_column(
                table, col,
                existing_type=sa.String(10),
                type_=sa.String(20),
                **kwargs,
            )
        except Exception:
            if is_sqlite:
                print(
                    f"WARN: alter_column {table}.{col} failed on SQLite, "
                    "tolerated (SQLite does not enforce String length)"
                )
            else:
                raise

    # 2. 新增 in_transit_total 列（幂等：兼容 create_all 已建列）
    try:
        op.add_column(
            'portfolio_value_snapshot',
            sa.Column('in_transit_total', sa.Numeric(15, 4), server_default='0'),
        )
    except Exception:
        pass

    # 3. 插入种子产品记录（与 CASH 虚拟产品同构：market=''）
    #    product_type='IN_TRANSIT'，confirm_days=0，is_qdii=0
    if is_mysql:
        op.execute("""
            INSERT INTO product (code, market, name, product_type, asset_class_code, confirm_days, is_qdii)
            VALUES
                ('IN_TRANSIT_BUY', '', '买入在途资金', 'IN_TRANSIT', NULL, 0, 0),
                ('IN_TRANSIT_SELL', '', '卖出在途资金', 'IN_TRANSIT', NULL, 0, 0)
            ON DUPLICATE KEY UPDATE name=VALUES(name)
        """)
    else:
        # SQLite: INSERT OR IGNORE（已存在则跳过）
        op.execute("""
            INSERT OR IGNORE INTO product (code, market, name, product_type, asset_class_code, confirm_days, is_qdii)
            VALUES
                ('IN_TRANSIT_BUY', '', '买入在途资金', 'IN_TRANSIT', NULL, 0, 0),
                ('IN_TRANSIT_SELL', '', '卖出在途资金', 'IN_TRANSIT', NULL, 0, 0)
        """)


def downgrade():
    """Migration 0006 is irreversible once IN_TRANSIT data exists."""
    # Attempting to downgrade would require:
    # 1. Deleting/migrating all IN_TRANSIT position/trade rows (FK constraints)
    # 2. Deleting seed products
    # 3. Narrowing String(20) back to String(10) — fails for IN_TRANSIT_BUY (14 chars)
    # Since this is unsafe, we mark it as irreversible.
    raise NotImplementedError(
        "Migration 0006 is irreversible once IN_TRANSIT data exists. "
        "Manual intervention required for rollback."
    )
