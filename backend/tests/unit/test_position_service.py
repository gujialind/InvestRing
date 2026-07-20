# ============================================================================
# 单元测试：持仓服务现金计算 (test_position_service.py)
# ============================================================================
# 覆盖 app/services/position_service.py 中的现金计算函数：
# - get_cash_value（含 manual_market_value 绝对替换，辅助审计场景）
# - calculate_available_cash（基线读快照表，回归 issue #52）
# ============================================================================

from datetime import date
from decimal import Decimal

from app.services.position_service import (
    compute_cash_balance,
    get_cash_value,
    calculate_available_cash,
    calculate_available_shares,
    calculate_investor_available_shares,
)
from tests.factories import (
    create_portfolio, create_platform, create_trade,
    create_value_snapshot, create_manual_market_value,
    create_position_snapshot, create_investor_holding, create_subscription,
    create_investor, create_product,
)


SNAP_DATE = date(2025, 1, 6)  # 周一，交易日


def _seed_cash_baseline(db, portfolio_code="GV_P", platform_code="GV_PLAT", amount=6000):
    """构造基线：组合 + 平台 + 价值快照 + CASH 持仓快照 + 一笔 confirmed CASH buy（amount）"""
    create_portfolio(db, code=portfolio_code, status="active")
    create_platform(db, code=platform_code)
    create_value_snapshot(db, portfolio_code, SNAP_DATE,
                          total_value=amount, total_shares=amount, unit_price=1.0)
    create_position_snapshot(
        db, portfolio_code, "CASH", "", SNAP_DATE,
        amount=amount, platform_code=platform_code, asset_type="cash",
    )
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
    """基线读快照表（#52）：manual 覆盖已 baked in 快照，实时计算自然继承"""

    def test_baseline_reads_from_snapshot(self, test_db):
        """基线直接读快照表 CASH amount（快照已含 manual 覆盖）"""
        # 模拟快照生成时已 bake in manual 覆盖值 6001.39
        create_portfolio(test_db, code="GV_P", status="active")
        create_platform(test_db, code="GV_PLAT")
        create_value_snapshot(test_db, "GV_P", SNAP_DATE,
                              total_value=6001.39, total_shares=6001.39, unit_price=1.0)
        create_position_snapshot(
            test_db, "GV_P", "CASH", "", SNAP_DATE,
            amount=6001.39, platform_code="GV_PLAT", asset_type="cash",
        )
        cash = calculate_available_cash(test_db, "GV_P", "GV_PLAT")
        assert cash == Decimal("6001.39")

    def test_override_plus_post_snapshot_trade(self, test_db):
        """快照基线（含覆盖）+ 快照后 confirmed trade"""
        create_portfolio(test_db, code="GV_P", status="active")
        create_platform(test_db, code="GV_PLAT")
        create_value_snapshot(test_db, "GV_P", SNAP_DATE,
                              total_value=6001.39, total_shares=6001.39, unit_price=1.0)
        create_position_snapshot(
            test_db, "GV_P", "CASH", "", SNAP_DATE,
            amount=6001.39, platform_code="GV_PLAT", asset_type="cash",
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
        """快照基线（含覆盖）- pending sell 预留"""
        create_portfolio(test_db, code="GV_P", status="active")
        create_platform(test_db, code="GV_PLAT")
        create_value_snapshot(test_db, "GV_P", SNAP_DATE,
                              total_value=6001.39, total_shares=6001.39, unit_price=1.0)
        create_position_snapshot(
            test_db, "GV_P", "CASH", "", SNAP_DATE,
            amount=6001.39, platform_code="GV_PLAT", asset_type="cash",
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
        """无快照时，降级为全量流水计算，不应用 manual 覆盖"""
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

    def test_manual_override_inherited_from_snapshot(self, test_db):
        """核心场景（#52）：历史 manual 覆盖已 baked in 快照，实时计算自然继承"""
        # 模拟：D-2 设置了 manual 覆盖 10000，D-1 快照继承了该值 + 增量 200 = 10200
        # 当前最新快照 = D-1，无 manual 记录在 D-1
        create_portfolio(test_db, code="GV_P", status="active")
        create_platform(test_db, code="GV_PLAT")
        create_value_snapshot(test_db, "GV_P", SNAP_DATE,
                              total_value=10200, total_shares=10200, unit_price=1.0)
        create_position_snapshot(
            test_db, "GV_P", "CASH", "", SNAP_DATE,
            amount=10200, platform_code="GV_PLAT", asset_type="cash",
        )
        # 无 manual_market_value 记录在 SNAP_DATE
        # 流水只有一笔原始 buy 6000（全量重算会得 6000，但快照基线应为 10200）
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="buy", amount=6000, status="confirmed",
            trade_date=date(2025, 1, 2), confirm_date=date(2025, 1, 2),
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(test_db, "GV_P", "GV_PLAT")
        # 应读快照基线 10200，而非全量流水 6000
        assert cash == Decimal("10200")


class TestCalculateAvailableCashAsOfDate:
    """calculate_available_cash 的 as_of_date 截止计算（#23）"""

    def test_as_of_date_baseline_le(self, test_db):
        """as_of_date 传入历史日时，基线取 <= as_of_date 的最新快照日"""
        _seed_cash_baseline(test_db)  # SNAP_DATE(2025-01-06) 现金 6000
        # 造一个更晚的快照（as_of_date 之后），不应被采用为基线
        create_value_snapshot(
            test_db, "GV_P", date(2025, 1, 13),
            total_value=20000, total_shares=20000, unit_price=1.0,
        )
        create_position_snapshot(
            test_db, "GV_P", "CASH", "", date(2025, 1, 13),
            amount=20000, platform_code="GV_PLAT", asset_type="cash",
        )
        cash = calculate_available_cash(
            test_db, "GV_P", "GV_PLAT", as_of_date=date(2025, 1, 10)
        )
        # 基线落在 2025-01-06（<= as_of_date），无后续快照内 trade，应为 6000
        assert cash == Decimal("6000")

    def test_as_of_date_after_range_inclusive(self, test_db):
        """as_of_date 截止：快照后 confirmed trade 在 (latest, as_of] 内计入"""
        _seed_cash_baseline(test_db)
        # SNAP_DATE 之后、as_of 之前的 confirmed buy 应计入
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="buy", amount=300, status="confirmed",
            trade_date=date(2025, 1, 7), confirm_date=date(2025, 1, 8),
            platform_code="GV_PLAT",
        )
        # as_of 之后的 confirmed buy 不应计入
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="buy", amount=999, status="confirmed",
            trade_date=date(2025, 1, 13), confirm_date=date(2025, 1, 14),
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(
            test_db, "GV_P", "GV_PLAT", as_of_date=date(2025, 1, 10)
        )
        assert cash == Decimal("6300")

    def test_as_of_date_pending_unaffected(self, test_db):
        """as_of_date 截止不影响 pending sells 计提"""
        _seed_cash_baseline(test_db)
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="sell", amount=500, status="pending",
            trade_date=date(2025, 1, 20),  # pending 在 as_of 之后，仍计提预留
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(
            test_db, "GV_P", "GV_PLAT", as_of_date=date(2025, 1, 10)
        )
        assert cash == Decimal("5500")


class TestCalculateAvailableSharesAsOfDate:
    """calculate_available_shares 的 as_of_date 截止计算（#23）"""

    def test_as_of_date_latest_position_le(self, test_db):
        """as_of_date 截止：最新持仓取 <= as_of_date 的快照"""
        create_portfolio(test_db, code="SHR_P", status="active")
        create_platform(test_db, code="SHR_PLAT")
        create_product(test_db, code="FUND1", market="CN_OTC")
        # 1-6 快照 1000 份
        create_position_snapshot(
            test_db, "SHR_P", "FUND1", "CN_OTC", date(2025, 1, 6),
            shares=1000, platform_code="SHR_PLAT",
        )
        # 1-13 快照 800 份（as_of 之后，不应采用）
        create_position_snapshot(
            test_db, "SHR_P", "FUND1", "CN_OTC", date(2025, 1, 13),
            shares=800, platform_code="SHR_PLAT",
        )
        # as_of=1-10：基线取 1-6 的 1000
        shares = calculate_available_shares(
            test_db, "SHR_P", "FUND1", "CN_OTC", as_of_date=date(2025, 1, 10)
        )
        assert shares == Decimal("1000")

    def test_as_of_date_confirmed_sell_in_range(self, test_db):
        """as_of_date 截止：confirmed sell 在 (latest, as_of] 内扣减"""
        create_portfolio(test_db, code="SHR_P2", status="active")
        create_platform(test_db, code="SHR_PLAT2")
        create_product(test_db, code="FUND1", market="CN_OTC")
        create_value_snapshot(
            test_db, "SHR_P2", date(2025, 1, 6),
            total_value=1000, total_shares=1000, unit_price=1.0,
        )
        create_position_snapshot(
            test_db, "SHR_P2", "FUND1", "CN_OTC", date(2025, 1, 6),
            shares=1000, platform_code="SHR_PLAT2",
        )
        # 快照后、as_of 内 confirmed sell 100
        create_trade(
            test_db, "SHR_P2", "FUND1", "CN_OTC",
            trade_type="sell", shares=100, status="confirmed",
            trade_date=date(2025, 1, 7), confirm_date=date(2025, 1, 8),
            platform_code="SHR_PLAT2",
        )
        # as_of 之后的 confirmed sell 50 不扣减
        create_trade(
            test_db, "SHR_P2", "FUND1", "CN_OTC",
            trade_type="sell", shares=50, status="confirmed",
            trade_date=date(2025, 1, 13), confirm_date=date(2025, 1, 14),
            platform_code="SHR_PLAT2",
        )
        shares = calculate_available_shares(
            test_db, "SHR_P2", "FUND1", "CN_OTC", as_of_date=date(2025, 1, 10)
        )
        assert shares == Decimal("900")


class TestCalculateInvestorAvailableSharesAsOfDate:
    """calculate_investor_available_shares 的 as_of_date 截止计算（#23）"""

    def test_as_of_date_latest_holding_le(self, test_db):
        """as_of_date 截止：最新投资人份额取 <= as_of_date 的快照"""
        create_portfolio(test_db, code="INV_P", status="active")
        create_investor(test_db, code="INV_I")
        create_investor_holding(test_db, "INV_P", "INV_I", date(2025, 1, 6), shares=500)
        create_investor_holding(test_db, "INV_P", "INV_I", date(2025, 1, 13), shares=300)
        shares = calculate_investor_available_shares(
            test_db, "INV_P", "INV_I", as_of_date=date(2025, 1, 10)
        )
        assert shares == Decimal("500")

    def test_as_of_date_confirmed_redeem_in_range(self, test_db):
        """as_of_date 截止：confirmed redeem 在 (latest, as_of] 内扣减"""
        create_portfolio(test_db, code="INV_P2", status="active")
        create_investor(test_db, code="INV_I2")
        create_platform(test_db, code="MYCF")
        create_value_snapshot(
            test_db, "INV_P2", date(2025, 1, 6),
            total_value=500, total_shares=500, unit_price=1.0,
        )
        create_investor_holding(test_db, "INV_P2", "INV_I2", date(2025, 1, 6), shares=500)
        create_subscription(
            test_db, "INV_P2", "INV_I2", sub_type="redeem",
            shares=100, apply_date=date(2025, 1, 7),
            confirm_date=date(2025, 1, 8), status="confirmed",
        )
        create_subscription(
            test_db, "INV_P2", "INV_I2", sub_type="redeem",
            shares=50, apply_date=date(2025, 1, 13),
            confirm_date=date(2025, 1, 14), status="confirmed",
        )
        shares = calculate_investor_available_shares(
            test_db, "INV_P2", "INV_I2", as_of_date=date(2025, 1, 10)
        )
        assert shares == Decimal("400")
