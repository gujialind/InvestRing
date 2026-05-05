from sqlalchemy import Column, String, Numeric, Date, DateTime, Integer, ForeignKey, func, UniqueConstraint
from app.database import Base


class InvestorHolding(Base):
    __tablename__ = "investor_holding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_code = Column(String(20), ForeignKey("portfolio.code"), nullable=False)
    investor_code = Column(String(20), ForeignKey("investor.code"), nullable=False)
    shares = Column(Numeric(15, 4), nullable=False)
    frozen_shares = Column(Numeric(15, 4), default=0)
    cost_per_share = Column(Numeric(10, 4))
    snapshot_date = Column(Date, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('portfolio_code', 'investor_code', 'snapshot_date', name='uix_holding_snapshot'),
    )
