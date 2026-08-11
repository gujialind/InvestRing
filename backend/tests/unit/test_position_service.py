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
        cash_amount=amount, platform_code=platform_code,
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
        """基线直接读快照表 CASH 行的 cash_amount（快照已含 manual 覆盖）"""
        # 模拟快照生成时已 bake in manual 覆盖值 6001.39
        create_portfolio(test_db, code="GV_P", status="active")
        create_platform(test_db, code="GV_PLAT")
        create_value_snapshot(test_db, "GV_P", SNAP_DATE,
                              total_value=6001.39, total_shares=6001.39, unit_price=1.0)
        create_position_snapshot(
            test_db, "GV_P", "CASH", "", SNAP_DATE,
            cash_amount=6001.39, platform_code="GV_PLAT",
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
            cash_amount=6001.39, platform_code="GV_PLAT",
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
            cash_amount=6001.39, platform_code="GV_PLAT",
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
            cash_amount=10200, platform_code="GV_PLAT",
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
            cash_amount=20000, platform_code="GV_PLAT",
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

    def test_as_of_date_pending_sell_after_as_of_excluded(self, test_db):
        """新口径（#70/#78）：pending sell 仅在 trade_date <= as_of_date 时计提"""
        _seed_cash_baseline(test_db)
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="sell", amount=500, status="pending",
            trade_date=date(2025, 1, 20),  # 下单日在 as_of 之后，尚未承诺，不计提
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(
            test_db, "GV_P", "GV_PLAT", as_of_date=date(2025, 1, 10)
        )
        assert cash == Decimal("6000")

    def test_as_of_date_pending_sell_on_or_before_as_of_deducted(self, test_db):
        """新口径（#70/#78）：pending sell 的 trade_date <= as_of_date 时正常计提"""
        _seed_cash_baseline(test_db)
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="sell", amount=500, status="pending",
            trade_date=date(2025, 1, 8),
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(
            test_db, "GV_P", "GV_PLAT", as_of_date=date(2025, 1, 10)
        )
        assert cash == Decimal("5500")


class TestAvailableCashTradeDateAnchor:
    """可用现金时点口径（#70/#78）：流出锚定 trade_date，流入锚定 confirm_date"""

    def test_confirmed_sell_trade_date_within_as_of_deducted(self, test_db):
        """confirmed sell：trade_date <= as_of < confirm_date 仍扣减（旧口径会隐身）"""
        _seed_cash_baseline(test_db)
        # 下单 1-7、确认 1-13：as_of=1-10 时旧口径（按 confirm_date）不扣，新口径必扣
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="sell", amount=2000, status="confirmed",
            trade_date=date(2025, 1, 7), confirm_date=date(2025, 1, 13),
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(
            test_db, "GV_P", "GV_PLAT", as_of_date=date(2025, 1, 10)
        )
        assert cash == Decimal("4000")

    def test_confirmed_sell_trade_date_after_as_of_excluded(self, test_db):
        """confirmed sell：trade_date > as_of 时不扣减（承诺尚未发生）"""
        _seed_cash_baseline(test_db)
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="sell", amount=2000, status="confirmed",
            trade_date=date(2025, 1, 13), confirm_date=date(2025, 1, 14),
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(
            test_db, "GV_P", "GV_PLAT", as_of_date=date(2025, 1, 10)
        )
        assert cash == Decimal("6000")

    def test_spec_scenario_t_plus_1(self, test_db):
        """事故口径复刻：T 日 4000，T+n 确认入金 2000，T+m(m>n) 下单卖出 2000，
        as_of=T+1 时：入金未确认不计、卖出未下单不扣 → 4000"""
        _seed_cash_baseline(test_db, amount=4000)  # T = 2025-01-06
        # T+3 确认的入金（在途 confirmed CASH buy，confirm_date 未到不计入）
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="buy", amount=2000, status="confirmed",
            trade_date=date(2025, 1, 8), confirm_date=date(2025, 1, 9),
            platform_code="GV_PLAT",
        )
        # T+4 下单的卖出（trade_date 晚于 as_of，不扣）
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="sell", amount=2000, status="confirmed",
            trade_date=date(2025, 1, 10), confirm_date=date(2025, 1, 13),
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(
            test_db, "GV_P", "GV_PLAT", as_of_date=date(2025, 1, 7)
        )
        assert cash == Decimal("4000")

    def test_as_of_none_equivalent_to_legacy(self, test_db):
        """as_of_date=None 时选取集合与旧实现完全一致（不设上限）"""
        _seed_cash_baseline(test_db)  # 基线 6000
        # 快照后 confirmed buy +300
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="buy", amount=300, status="confirmed",
            trade_date=date(2025, 1, 13), confirm_date=date(2025, 1, 14),
            platform_code="GV_PLAT",
        )
        # 快照后 confirmed sell −200（无上限，无论 trade_date/confirm_date 多晚）
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="sell", amount=200, status="confirmed",
            trade_date=date(2025, 2, 10), confirm_date=date(2025, 2, 11),
            platform_code="GV_PLAT",
        )
        # pending sell −500（远期下单仍全额计提）
        create_trade(
            test_db, "GV_P", "CASH", "",
            trade_type="sell", amount=500, status="pending",
            trade_date=date(2025, 3, 3),
            platform_code="GV_PLAT",
        )
        cash = calculate_available_cash(test_db, "GV_P", "GV_PLAT")
        assert cash == Decimal("5600")


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
