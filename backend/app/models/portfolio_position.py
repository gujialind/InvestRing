from sqlalchemy import Column, String, Numeric, Date, DateTime, Integer, ForeignKey, ForeignKeyConstraint, func, CheckConstraint, UniqueConstraint
from app.database import Base


class PortfolioPosition(Base):
    __tablename__ = "portfolio_position"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_code = Column(String(20), ForeignKey("portfolio.code"), nullable=False)
    platform_code = Column(String(20), ForeignKey("platform.code"))
    product_code = Column(String(10), nullable=False)
    market = Column(String(20), nullable=False)
    shares = Column(Numeric(15, 4))
    frozen_shares = Column(Numeric(15, 4), default=0)
    cost_price = Column(Numeric(10, 4))
    unit_price = Column(Numeric(10, 4))
    market_value = Column(Numeric(15, 4), default=0)
    amount = Column(Numeric(15, 4))
    frozen_amount = Column(Numeric(15, 4), default=0)
    asset_type = Column(String(20))
    snapshot_date = Column(Date, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["product_code", "market"],
            ["product.code", "product.market"]
        ),
        CheckConstraint(
            '(shares IS NOT NULL AND amount IS NULL) OR (shares IS NULL AND amount IS NOT NULL)',
            name='check_nav_or_non_nav'
        ),
        UniqueConstraint('portfolio_code', 'product_code', 'market', 'platform_code', 'snapshot_date', name='uix_position_snapshot'),
    )
