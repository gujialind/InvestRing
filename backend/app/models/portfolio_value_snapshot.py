from sqlalchemy import Column, String, Numeric, Date, DateTime, Integer, ForeignKey, func, UniqueConstraint
from app.database import Base


class PortfolioValueSnapshot(Base):
    __tablename__ = "portfolio_value_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_code = Column(String(20), ForeignKey("portfolio.code"), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    total_value = Column(Numeric(15, 4), nullable=False)
    total_shares = Column(Numeric(15, 4), nullable=False)
    unit_price = Column(Numeric(10, 4), nullable=False)
    unit_price_change_pct = Column(Numeric(8, 4))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('portfolio_code', 'snapshot_date', name='uix_snapshot_portfolio_date'),
    )
