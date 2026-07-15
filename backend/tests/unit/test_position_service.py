# ============================================================================
# 单元测试：持仓服务现金计算 (test_position_service.py)
# ============================================================================
# 覆盖 app/services/position_service.py 中的现金计算函数：
# - get_cash_value（含 manual_market_value 绝对替换）
# - calculate_available_cash（基线纳入 manual 覆盖，回归 issue #14）
# ============================================================================

from datetime import date
from decimal import Decimal

from app.services.position_service import (
    compute_cash_balance,
    get_cash_value,
    calculate_available_cash,
)
from tests.factories import (
    create_portfolio, create_platform, create_trade,
    create_value_snapshot, create_manual_market_value,
)


SNAP_DATE = date(2025, 1, 6)  # 周一，交易日


def _seed_cash_baseline(db, portfolio_code="GV_P", platform_code="GV_PLAT", amount=6000):
    """构造基线：组合 + 平台 + 快照 + 一笔 confirmed CASH buy（amount）"""
    create_portfolio(db, code=portfolio_code, status="active")
    create_platform(db, code=platform_code)
    create_value_snapshot(db, portfolio_code, SNAP_DATE,
                          total_value=amount, total_shares=amount, unit_price=1.0)
    create_trade(
        db, portfolio_code, "CASH", "",
        trade_type="buy", amount=amount, status="confirmed",
        trade_date=SNAP_DATE, confirm_date=SNAP_DATE,
        platform_code=platform_code,
    )


class TestGetCashValue:
    """get_cash_value 单元测试（迁移至 position_service 后）"""

    def test_without_override_returns_computed(self, test_db):
        """无 manual 覆盖时，返回 compute_cash_balance 结果"""
        _seed_cash_baseline(test_db)
        v = get_cash_value(test_db, "GV_P", "GV_PLAT", SNAP_DATE)
        assert v == Decimal("6000")

    def test_with_override_replaces_computed(self, test_db):
        """存在 manual 覆盖时，绝对替换计算值"""
        _seed_cash_baseline(test_db)
        create_manual_market_value(
            test_db, "GV_P", "GV_PLAT", "CASH",
            record_date=SNAP_DATE, market_value=6001.39,
        )
        v = get_cash_value(test_db, "GV_P", "GV_PLAT", SNAP_DATE)
        assert v == Decimal("6001.39")

    def test_override_non_matching_date_ignored(self, test_db):
        """覆盖日期 != target_date 时，不应用覆盖"""
        _seed_cash_baseline(test_db)
        create_manual_market_value(
            test_db, "GV_P", "GV_PLAT", "CASH",
            record_date=date(2025, 1, 10), market_value=9999,
        )
        v = get_cash_value(test_db, "GV_P", "GV_PLAT", SNAP_DATE)
        assert v == Decimal("6000")

    def test_target_date_none_skips_override(self, test_db):
        """target_date 为 None 时，跳过覆盖查询"""
        _seed_cash_baseline(test_db)
        create_manual_market_value(
            test_db, "GV_P", "GV_PLAT", "CASH",
            record_date=date.today(), market_value=9999,
        )
        v = get_cash_value(test_db, "GV_P", "GV_PLAT", None)
        assert v == Decimal("6000")


class TestCalculateAvailableCashWithOverride:
    """calculate_available_cash 含 manual_market_value 覆盖测试（核心修复验证）"""

    def test_baseline_includes_override(self, test_db):
        """基线纳入 manual 覆盖值（核心 bug 修复）"""
        _seed_cash_baseline(test_db)
        create_manual_market_value(
            test_db, "GV_P", "GV_PLAT", "CASH",
            record_date=SNAP_DATE, market_value=6001.39,
        )
        cash = calculate_available_cash(test_db, "GV_P", "GV_PLAT")
        assert cash == Decimal("6001.39")

    def test_override_plus_post_snapshot_trade(self, test_db):
        """覆盖基线 + 快照后 confirmed trade"""
        _seed_cash_baseline(test_db)
        create_manual_market_value(
            test_db, "GV_P", "GV_PLAT", "CASH",
            record_date=SNAP_DATE, market_value=6001.39,
        )
        # 快照后 confirmed CASH buy
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="buy", amount=100, status="confirmed",
            trade_date=date(2025, 1, 7), confirm_date=date(2025, 1, 7),
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(test_db, "GV_P", "GV_PLAT")
        assert cash == Decimal("6101.39")

    def test_override_minus_pending_sell(self, test_db):
        """覆盖基线 - pending sell 预留"""
        _seed_cash_baseline(test_db)
        create_manual_market_value(
            test_db, "GV_P", "GV_PLAT", "CASH",
            record_date=SNAP_DATE, market_value=6001.39,
        )
        # pending CASH sell（已承诺未执行，需预留）
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="sell", amount=500, status="pending",
            trade_date=date(2025, 1, 7),
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(test_db, "GV_P", "GV_PLAT")
        assert cash == Decimal("5501.39")

    def test_no_snapshot_ignores_override(self, test_db):
        """无快照时，不应用 manual 覆盖"""
        create_portfolio(test_db, code="GV_NOSNAP", status="active")
        create_platform(test_db, code="GV_PLAT2")
        # 无快照时写入 manual 覆盖
        create_manual_market_value(
            test_db, "GV_NOSNAP", "GV_PLAT2", "CASH",
            record_date=date.today(), market_value=9999,
        )
        # 无 CASH trade，覆盖值 9999 不应生效
        cash = calculate_available_cash(test_db, "GV_NOSNAP", "GV_PLAT2")
        assert cash == Decimal("0")

    def test_override_non_matching_date_no_effect(self, test_db):
        """覆盖日期 != latest_date 时，不影响可用现金"""
        _seed_cash_baseline(test_db)
        create_manual_market_value(
            test_db, "GV_P", "GV_PLAT", "CASH",
            record_date=date(2025, 1, 20), market_value=9999,
        )
        cash = calculate_available_cash(test_db, "GV_P", "GV_PLAT")
        assert cash == Decimal("6000")
