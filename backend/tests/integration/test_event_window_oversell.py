# ============================================================================
# 集成测试：负向份额变动事件窗口内的卖出超卖防线 (test_event_window_oversell.py)
# ============================================================================
# issue #277：可用份额实时计算不含份额变动事件——负向事件确认后、入快照前的
# 窗口内可用份额高估，可卖出超过实际持有量的份额。
#
# 覆盖验收断言：
# 1. 负向 forced_adjustment 确认后、快照前，超额卖出被 INSUFFICIENT_SHARES 拒绝
# 2. 调整后余额内不误拒（含量化边界）
# 3. ex_date 当日快照生成后，超额卖出仍被拒（快照基线路径不回退）
# 4. share_merge 负向（基金级）窗口内同样扣减
# 5. 正向事件（share_split）保守低估：≤快照份额通过、超出部分仍拒
# ============================================================================

from datetime import date
from decimal import Decimal

import pytest

from app.models import PortfolioPosition
from app.services.exceptions import BusinessError
from app.services.share_change_event_service import (
    create_share_change_event as svc_create_event,
    confirm_share_change_event,
)
from app.services.snapshot_service import generate_daily_snapshots
from app.services.trade_service import create_trade
from tests.factories import (
    create_portfolio,
    create_product,
    create_price_record,
    create_position_snapshot,
)

S = date(2025, 6, 6)     # 基线快照日（周五）
EX = date(2025, 6, 9)    # 事件除息日（周一，窗口内）
NEXT = date(2025, 6, 10)  # 快照生成后的下一交易日

FUND = "OV277.OF"


def _setup(db, port_code: str, shares: float = 1000.0):
    """基线：组合持有该基金 1000 份（快照日 S）"""
    create_portfolio(db, code=port_code, status="active")
    create_product(db, code=FUND, market="CN_OTC",
                   product_type="OEF", asset_class_code="ASSET_STOCK")
    create_position_snapshot(
        db, port_code, FUND, "CN_OTC", snapshot_date=S,
        shares=shares, unit_price=1.0, cost_price=1.0,
        market_value=shares, platform_code="MYCF",
    )
    # 价格记录按产品维度唯一，多个组合共用同一产品时跳过重复创建
    from app.models.price_record import PriceRecord
    if not db.query(PriceRecord).filter(
        PriceRecord.product_code == FUND, PriceRecord.price_date == EX,
    ).first():
        create_price_record(db, FUND, "CN_OTC", EX, 1.0)


def _confirm_event(db, port_code: str, *, event_type="forced_adjustment",
                   shares_change=None, ratio=None, platform_code="MYCF"):
    """走真实创建 + 确认流程"""
    event = svc_create_event(
        db,
        portfolio_code=port_code,
        event_type=event_type,
        product_code=FUND,
        market="CN_OTC",
        platform_code=platform_code,
        ex_date=EX,
        entitlement_date=S,
        shares_change=shares_change,
        ratio=ratio,
    )
    db.flush()
    confirm_share_change_event(db, event)
    db.flush()
    return event


def _sell(db, port_code: str, shares: str, trade_date: date = EX):
    return create_trade(
        db, portfolio_code=port_code, product_code=FUND, market="CN_OTC",
        trade_type="sell", trade_date=trade_date,
        shares=Decimal(shares), platform_code="MYCF",
    )


class TestNegativeEventWindowOversell:

    def test_oversell_rejected_after_negative_adjustment(self, test_db):
        """验收 1：1000 − 100 后可用 900，卖 950 被拒"""
        _setup(test_db, "OV_P1")
        _confirm_event(test_db, "OV_P1", shares_change=Decimal("-100.00"))

        with pytest.raises(BusinessError) as exc:
            _sell(test_db, "OV_P1", "950.00")
        assert exc.value.code == "INSUFFICIENT_SHARES"

    def test_within_adjusted_balance_not_blocked(self, test_db):
        """验收 2：调整后余额内不误拒（900 通过、900.01 量化后精确比较仍拒）"""
        _setup(test_db, "OV_P2A")
        _confirm_event(test_db, "OV_P2A", shares_change=Decimal("-100.00"))
        trade = _sell(test_db, "OV_P2A", "900.00")
        assert trade.status == "pending"

        _setup(test_db, "OV_P2B")
        _confirm_event(test_db, "OV_P2B", shares_change=Decimal("-100.00"))
        with pytest.raises(BusinessError) as exc:
            _sell(test_db, "OV_P2B", "900.01")
        assert exc.value.code == "INSUFFICIENT_SHARES"

    def test_snapshot_baseline_keeps_rejection(self, test_db):
        """验收 3：事件入快照后再卖超额仍被拒（快照基线路径不回退）"""
        _setup(test_db, "OV_P3")
        _confirm_event(test_db, "OV_P3", shares_change=Decimal("-100.00"))

        result = generate_daily_snapshots(test_db, "OV_P3", EX)
        assert result["success"] is True
        pos = test_db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == "OV_P3",
            PortfolioPosition.product_code == FUND,
            PortfolioPosition.snapshot_date == EX,
        ).one()
        assert Decimal(str(pos.shares)) == Decimal("900.00")

        with pytest.raises(BusinessError) as exc:
            _sell(test_db, "OV_P3", "950.00", trade_date=NEXT)
        assert exc.value.code == "INSUFFICIENT_SHARES"

    def test_share_merge_negative_window_deducted(self, test_db):
        """验收 4：share_merge（ratio=2，基金级负向）窗口内同样扣减"""
        _setup(test_db, "OV_P4")
        _confirm_event(test_db, "OV_P4", event_type="share_merge",
                       ratio=Decimal("2"), platform_code=None)

        # 1000 / 2 = 500，变动 −500 → 可用 500
        with pytest.raises(BusinessError) as exc:
            _sell(test_db, "OV_P4", "600.00")
        assert exc.value.code == "INSUFFICIENT_SHARES"
        trade = _sell(test_db, "OV_P4", "500.00")
        assert trade.status == "pending"

    def test_positive_event_conservative(self, test_db):
        """验收 5：正向事件保守低估——≤快照份额通过、超出快照份额的部分仍拒"""
        _setup(test_db, "OV_P5A")
        _confirm_event(test_db, "OV_P5A", event_type="share_split",
                       ratio=Decimal("2"), platform_code=None)
        trade = _sell(test_db, "OV_P5A", "1000.00")  # = 快照份额，通过
        assert trade.status == "pending"

        _setup(test_db, "OV_P5B")
        _confirm_event(test_db, "OV_P5B", event_type="share_split",
                       ratio=Decimal("2"), platform_code=None)
        with pytest.raises(BusinessError) as exc:
            _sell(test_db, "OV_P5B", "1500.00")  # 快照 1000 < 1500 ≤ 拆分后 2000，仍拒
        assert exc.value.code == "INSUFFICIENT_SHARES"
