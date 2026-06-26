# ============================================================================
# 单元测试：快照服务 (test_snapshot_service.py)
# ============================================================================
# 覆盖 app/services/snapshot_service.py 中的核心函数：
# - 快照依赖校验（validate_snapshot_dependencies）
# - 冻结份额计算
# - 交易日判断
# - 快照前置校验（组合状态、交易日）
# ============================================================================

import pytest
from datetime import date
from decimal import Decimal

from app.services.snapshot_service import (
    validate_snapshot_dependencies,
    _validate_portfolio,
    _validate_trading_day,
    _is_trading_day,
    _calculate_frozen_shares,
    _calculate_portfolio_frozen_shares,
    _calculate_investor_frozen_shares,
    _check_trading_day,
    _check_pending_transactions,
    _check_share_change_events,
    _prev_trading_day,
)
from app.models import (
    Portfolio, TradingCalendar, Trade, Subscription,
    PortfolioPosition, Product, Investor,
)
from tests.factories import (
    create_portfolio, create_product, create_trade,
    create_subscription, create_investor, ensure_trading_day,
    create_position_snapshot, create_platform,
)


class TestValidatePortfolio:
    """组合前置校验测试"""

    def test_nonexistent_portfolio_raises(self, test_db):
        """不存在的组合应抛出 ValueError"""
        with pytest.raises(ValueError, match="不存在"):
            _validate_portfolio(test_db, "NONEXISTENT")

    def test_draft_portfolio_raises(self, test_db):
        """draft 状态组合应抛出 ValueError（未激活）"""
        create_portfolio(test_db, code="DRAFT_P", status="draft")
        with pytest.raises(ValueError, match="未激活"):
            _validate_portfolio(test_db, "DRAFT_P")

    def test_closed_portfolio_raises(self, test_db):
        """closed 状态组合应抛出 ValueError"""
        create_portfolio(test_db, code="CLOSED_P", status="closed")
        with pytest.raises(ValueError, match="未激活"):
            _validate_portfolio(test_db, "CLOSED_P")

    def test_active_portfolio_passes(self, test_db):
        """active 状态组合应通过校验"""
        create_portfolio(test_db, code="ACTIVE_V", status="active")
        _validate_portfolio(test_db, "ACTIVE_V")  # 不抛异常即通过


class TestIsTradingDay:
    """交易日判断测试"""

    def test_trading_day_returns_true(self, test_db):
        """交易日应返回 True"""
        ensure_trading_day(test_db, date(2025, 3, 3), is_open=True)  # 周一
        assert _is_trading_day(test_db, date(2025, 3, 3)) is True

    def test_non_trading_day_returns_false(self, test_db):
        """非交易日应返回 False"""
        ensure_trading_day(test_db, date(2025, 3, 1), is_open=False)  # 周六
        assert _is_trading_day(test_db, date(2025, 3, 1)) is False

    def test_unknown_date_returns_false(self, test_db):
        """交易日历中不存在的日期应返回 False"""
        assert _is_trading_day(test_db, date(2030, 1, 1)) is False


class TestValidateTradingDay:
    """交易日校验测试"""

    def test_non_trading_day_raises(self, test_db):
        """非交易日应抛出 ValueError"""
        ensure_trading_day(test_db, date(2025, 3, 2), is_open=False)
        with pytest.raises(ValueError, match="不是交易日"):
            _validate_trading_day(test_db, date(2025, 3, 2))

    def test_trading_day_passes(self, test_db):
        """交易日应通过校验"""
        ensure_trading_day(test_db, date(2025, 3, 3), is_open=True)
        _validate_trading_day(test_db, date(2025, 3, 3))


class TestPrevTradingDay:
    """前一交易日查找测试"""

    def test_prev_trading_day_basic(self, test_db):
        """应正确找到前一个交易日"""
        ensure_trading_day(test_db, date(2025, 3, 3), is_open=True)  # 周一
        ensure_trading_day(test_db, date(2025, 3, 4), is_open=True)  # 周二
        result = _prev_trading_day(test_db, date(2025, 3, 4), 1)
        assert result == date(2025, 3, 3)

    def test_prev_trading_day_skips_weekend(self, test_db):
        """应跳过周末非交易日"""
        ensure_trading_day(test_db, date(2025, 2, 28), is_open=True)  # 周五
        ensure_trading_day(test_db, date(2025, 3, 1), is_open=False)  # 周六
        ensure_trading_day(test_db, date(2025, 3, 2), is_open=False)  # 周日
        ensure_trading_day(test_db, date(2025, 3, 3), is_open=True)  # 周一
        result = _prev_trading_day(test_db, date(2025, 3, 3), 1)
        assert result == date(2025, 2, 28)


class TestCheckPendingTransactions:
    """Pending 交易检查测试"""

    def test_no_pending_passes(self, test_db):
        """无 pending 交易应通过"""
        create_portfolio(test_db, code="NO_PEND", status="active")
        result = _check_pending_transactions(test_db, "NO_PEND", date(2025, 3, 3))
        assert result["status"] == "passed"

    def test_pending_trade_fails(self, test_db):
        """存在 pending 调仓交易应失败"""
        create_portfolio(test_db, code="PEND_T", status="active")
        create_product(test_db, code="FUND01", market="CN_OTC", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="PLAT_P")
        create_trade(
            test_db, portfolio_code="PEND_T",
            product_code="FUND01", market="CN_OTC",
            status="pending", trade_date=date(2025, 3, 3),
        )
        result = _check_pending_transactions(test_db, "PEND_T", date(2025, 3, 3))
        assert result["status"] == "failed"
        assert "待确认交易" in result["message"]

    def test_pending_subscription_fails(self, test_db):
        """存在 pending 申购应失败"""
        create_portfolio(test_db, code="PEND_S", status="active")
        create_investor(test_db, code="INV_PEND")
        create_subscription(
            test_db, portfolio_code="PEND_S", investor_code="INV_PEND",
            status="pending", apply_date=date(2025, 3, 3),
        )
        result = _check_pending_transactions(test_db, "PEND_S", date(2025, 3, 3))
        assert result["status"] == "failed"


class TestCheckShareChangeEvents:
    """份额变动事件检查测试"""

    def test_no_pending_events_passes(self, test_db):
        """无 pending 事件应通过"""
        create_portfolio(test_db, code="NO_EVT", status="active")
        result = _check_share_change_events(test_db, "NO_EVT", date(2025, 3, 3))
        assert result["status"] == "passed"


class TestFrozenSharesCalculation:
    """冻结份额计算测试"""

    def test_no_pending_sells_zero_frozen(self, test_db):
        """无 pending 卖出，冻结份额应为 0"""
        create_portfolio(test_db, code="FZ0", status="active")
        result = _calculate_frozen_shares(
            test_db, "FZ0", "510300.SH", "CN_EXCHANGE", date(2025, 3, 3)
        )
        assert result == Decimal("0")

    def test_pending_sell_freezes_shares(self, test_db):
        """pending 卖出应冻结对应份额"""
        create_portfolio(test_db, code="FZ1", status="active")
        create_product(test_db, code="510300.SH", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="PLAT_FZ")
        create_trade(
            test_db, portfolio_code="FZ1",
            product_code="510300.SH", market="CN_EXCHANGE",
            trade_type="sell", shares=500.0, status="pending",
            trade_date=date(2025, 3, 3), platform_code="PLAT_FZ",
        )
        result = _calculate_frozen_shares(
            test_db, "FZ1", "510300.SH", "CN_EXCHANGE", date(2025, 3, 3)
        )
        assert result == Decimal("500.0") or result == Decimal("500")

    def test_portfolio_frozen_shares_from_pending_redeem(self, test_db):
        """pending 赎回应冻结组合份额"""
        create_portfolio(test_db, code="FZP", status="active")
        create_investor(test_db, code="INV_FZP")
        create_subscription(
            test_db, portfolio_code="FZP", investor_code="INV_FZP",
            sub_type="redeem", shares=1000.0, status="pending",
            apply_date=date(2025, 3, 3),
        )
        result = _calculate_portfolio_frozen_shares(test_db, "FZP", date(2025, 3, 3))
        assert result == Decimal("1000.0") or result == Decimal("1000")

    def test_investor_frozen_shares(self, test_db):
        """投资人 pending 赎回冻结份额"""
        create_portfolio(test_db, code="FZI", status="active")
        create_investor(test_db, code="INV_FZI")
        create_subscription(
            test_db, portfolio_code="FZI", investor_code="INV_FZI",
            sub_type="redeem", shares=2000.0, status="pending",
            apply_date=date(2025, 3, 3),
        )
        result = _calculate_investor_frozen_shares(
            test_db, "FZI", "INV_FZI", date(2025, 3, 3)
        )
        assert result == Decimal("2000.0") or result == Decimal("2000")

    def test_confirmed_trade_not_frozen(self, test_db):
        """confirmed 卖出不计入冻结"""
        create_portfolio(test_db, code="FZC", status="active")
        create_product(test_db, code="510300.SH", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="PLAT_FZC")
        create_trade(
            test_db, portfolio_code="FZC",
            product_code="510300.SH", market="CN_EXCHANGE",
            trade_type="sell", shares=300.0, status="confirmed",
            trade_date=date(2025, 3, 3), platform_code="PLAT_FZC",
        )
        result = _calculate_frozen_shares(
            test_db, "FZC", "510300.SH", "CN_EXCHANGE", date(2025, 3, 3)
        )
        assert result == Decimal("0")


class TestValidateSnapshotDependencies:
    """快照依赖校验集成测试"""

    def test_non_trading_day_fails(self, test_db):
        """非交易日校验应失败"""
        create_portfolio(test_db, code="DEP_NTD", status="active")
        ensure_trading_day(test_db, date(2025, 4, 5), is_open=False)
        results = validate_snapshot_dependencies(test_db, "DEP_NTD", date(2025, 4, 5))
        trading_day_check = [r for r in results if r["check_type"] == "trading_day"]
        assert trading_day_check[0]["status"] == "failed"

    def test_all_checks_pass_on_clean_state(self, test_db):
        """干净状态下所有校验应通过"""
        create_portfolio(test_db, code="DEP_OK", status="active")
        ensure_trading_day(test_db, date(2025, 4, 7), is_open=True)
        results = validate_snapshot_dependencies(test_db, "DEP_OK", date(2025, 4, 7))
        # trading_day 和 pending_transactions 应通过
        for r in results:
            if r["check_type"] in ("trading_day", "pending_transactions"):
                assert r["status"] == "passed"
