from sqlalchemy import Column, String, Text, Numeric, Date, DateTime, Integer, ForeignKey, ForeignKeyConstraint, UniqueConstraint, func
from app.database import Base


class Trade(Base):
    __tablename__ = "trade"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_code = Column(String(20), ForeignKey("portfolio.code"), nullable=False)
    platform_code = Column(String(20), ForeignKey("platform.code"))
    product_code = Column(String(10), nullable=False)
    market = Column(String(20))
    trade_type = Column(String(10), nullable=False)
    transfer_group = Column(String(36))  # 平台间现金转移配对标识
    shares = Column(Numeric(15, 4))
    amount = Column(Numeric(15, 4), nullable=False)
    price = Column(Numeric(10, 4))
    fee = Column(Numeric(15, 4), default=0)
    actual_amount = Column(Numeric(15, 4))
    trade_date = Column(Date, nullable=False)
    confirm_date = Column(Date)
    status = Column(String(20), default="pending")
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["product_code", "market"],
            ["product.code", "product.market"]
        ),
        # transfer_group 唯一约束：防止重复确认生成重复 CASH trade
        # MySQL 中 NULL 值不参与唯一性检查，故 transfer_group 为空的普通 trade 不受影响
        UniqueConstraint('transfer_group', 'product_code', 'trade_type', name='uq_trade_transfer_group'),
    )
