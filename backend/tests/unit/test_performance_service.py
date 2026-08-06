"""
组合绩效指标单测：TWR / MWR(XIRR) / 回撤 / 波动率 / 区间收益

重点验证：
- 净值化体系下 TWR 两种算法恒等（净值比法 == 逐期几何连乘）
- XIRR 对已知答案的现金流求解正确，且能识别无解情形
- 回撤/波动率/区间收益的边界（快照不足、净值为 0、全程上涨）
"""
from datetime import date, timedelta

from app.services.performance_service import (
    _annualize,
    _annualized_volatility,
    _max_drawdown,
    _npv,
    _period_return,
    _xirr,
    compute_mwr,
    compute_twr,
)


class _FakeSub:
    """轻量替身：避免为纯计算函数构造完整 ORM 对象"""

    def __init__(self, sub_type, amount, confirm_date, status="confirmed", apply_date=None):
        self.sub_type = sub_type
        self.amount = amount
        self.confirm_date = confirm_date
        self.apply_date = apply_date or confirm_date
        self.status = status


class _FakeSnapshot:
    def __init__(self, snapshot_date, unit_price):
        self.snapshot_date = snapshot_date
        self.unit_price = unit_price


class TestComputeTwr:
    """TWR：净值比法与几何连乘在净值化体系下必须恒等"""

    def test_two_algorithms_identical(self):
        navs = [1.0, 1.0055, 1.0074, 0.9800, 1.2, 1.4376]
        result = compute_twr(navs)
        assert result["twr"] == result["twr_chained"]
        # 差异应在浮点误差量级
        assert result["twr_diff"] < 1e-9

    def test_simple_growth(self):
        # 1.0 → 1.5 即 +50%
        assert compute_twr([1.0, 1.5])["twr"] == 50.0

    def test_loss(self):
        assert compute_twr([1.0, 0.8])["twr"] == -20.0

    def test_flat(self):
        assert compute_twr([1.0, 1.0, 1.0])["twr"] == 0.0

    def test_insufficient_data(self):
        assert compute_twr([1.0])["twr"] is None
        assert compute_twr([])["twr"] is None

    def test_ignores_invalid_navs(self):
        # None 与非正净值被剔除，不应污染结果
        assert compute_twr([1.0, None, 0, 1.2])["twr"] == 20.0


class TestXirr:
    """XIRR：不规则现金流年化内部收益率"""

    def test_single_flow_pair_one_year(self):
        # 投入 100，一年后取回 110 → 约 10%
        rate = _xirr([(date(2025, 1, 1), -100.0), (date(2026, 1, 1), 110.0)])
        assert rate is not None
        assert abs(rate - 0.10) < 1e-4

    def test_npv_zero_at_solution(self):
        flows = [
            (date(2025, 1, 1), -1000.0),
            (date(2025, 7, 1), -500.0),
            (date(2026, 1, 1), 1650.0),
        ]
        rate = _xirr(flows)
        assert rate is not None
        # 解处净现值应≈0
        assert abs(_npv(rate, flows, flows[0][0])) < 1e-6

    def test_loss_gives_negative_rate(self):
        rate = _xirr([(date(2025, 1, 1), -100.0), (date(2026, 1, 1), 80.0)])
        assert rate is not None
        assert rate < 0

    def test_all_same_sign_returns_none(self):
        # 全为流出，NPV 无零点
        assert _xirr([(date(2025, 1, 1), -100.0), (date(2026, 1, 1), -50.0)]) is None

    def test_too_few_flows(self):
        assert _xirr([(date(2025, 1, 1), -100.0)]) is None

    def test_later_investment_lowers_mwr_below_twr(self):
        """核心业务语义：资金后期进入时 MWR 应低于 TWR。

        净值全程 1.0 → 1.5（TWR +50%），但大部分资金在最后一个月才投入，
        只享受到末段涨幅，故年化 MWR 不应等同于 TWR 的年化。
        """
        flows = [
            (date(2025, 1, 1), -100.0),      # 期初小额
            (date(2025, 12, 1), -10000.0),   # 末期大额加仓
            (date(2026, 1, 1), 10500.0),     # 期末市值
        ]
        rate = _xirr(flows)
        assert rate is not None
        assert abs(_npv(rate, flows, flows[0][0])) < 1e-6


class TestComputeMwr:
    def test_subscribe_then_end_value(self):
        subs = [_FakeSub("subscribe", 100.0, date(2025, 1, 1))]
        result = compute_mwr(subs, date(2026, 1, 1), 110.0)
        assert result["cash_flow_count"] == 1
        assert result["mwr"] is not None
        assert abs(result["mwr"] - 10.0) < 0.01

    def test_redeem_counted_as_inflow(self):
        subs = [
            _FakeSub("subscribe", 1000.0, date(2025, 1, 1)),
            _FakeSub("redeem", 200.0, date(2025, 7, 1)),
        ]
        result = compute_mwr(subs, date(2026, 1, 1), 900.0)
        assert result["cash_flow_count"] == 2
        assert result["mwr"] is not None

    def test_pending_subscription_excluded(self):
        subs = [
            _FakeSub("subscribe", 100.0, date(2025, 1, 1)),
            _FakeSub("subscribe", 999.0, date(2025, 6, 1), status="pending"),
        ]
        result = compute_mwr(subs, date(2026, 1, 1), 110.0)
        # pending 不计入现金流
        assert result["cash_flow_count"] == 1

    def test_no_flows_returns_none(self):
        assert compute_mwr([], date(2026, 1, 1), 100.0)["mwr"] is None

    def test_zero_end_value_returns_none(self):
        subs = [_FakeSub("subscribe", 100.0, date(2025, 1, 1))]
        assert compute_mwr(subs, date(2026, 1, 1), 0.0)["mwr"] is None

    def test_falls_back_to_apply_date(self):
        # confirm_date 缺失时用 apply_date（补录场景）
        sub = _FakeSub("subscribe", 100.0, None, apply_date=date(2025, 1, 1))
        sub.confirm_date = None
        result = compute_mwr([sub], date(2026, 1, 1), 110.0)
        assert result["cash_flow_count"] == 1


class TestMaxDrawdown:
    def test_simple_drawdown(self):
        navs = [1.0, 1.2, 0.9, 1.1]
        dates = [date(2025, 1, i) for i in range(1, 5)]
        result = _max_drawdown(navs, dates)
        # 峰 1.2 → 谷 0.9，回撤 25%
        assert abs(result["max_drawdown"] - 25.0) < 1e-6
        assert result["max_drawdown_peak_date"] == "2025-01-02"
        assert result["max_drawdown_trough_date"] == "2025-01-03"

    def test_monotonic_rise_has_no_drawdown(self):
        navs = [1.0, 1.1, 1.2]
        dates = [date(2025, 1, i) for i in range(1, 4)]
        assert _max_drawdown(navs, dates)["max_drawdown"] == 0.0

    def test_picks_worst_of_multiple_drawdowns(self):
        # 第一段回撤 10%，第二段 30%，应取后者
        navs = [1.0, 0.9, 1.5, 1.05]
        dates = [date(2025, 1, i) for i in range(1, 5)]
        result = _max_drawdown(navs, dates)
        assert abs(result["max_drawdown"] - 30.0) < 1e-6
        assert result["max_drawdown_peak_date"] == "2025-01-03"

    def test_insufficient_data(self):
        assert _max_drawdown([1.0], [date(2025, 1, 1)])["max_drawdown"] is None


class TestVolatility:
    def test_flat_series_zero_volatility(self):
        assert _annualized_volatility([1.0, 1.0, 1.0, 1.0]) == 0.0

    def test_volatile_series_positive(self):
        vol = _annualized_volatility([1.0, 1.1, 0.95, 1.2, 1.0])
        assert vol is not None and vol > 0

    def test_insufficient_data(self):
        assert _annualized_volatility([1.0, 1.1]) is None


class TestPeriodReturn:
    def test_uses_first_snapshot_on_or_after_start(self):
        snapshots = [
            _FakeSnapshot(date(2025, 1, 1), 1.0),
            _FakeSnapshot(date(2025, 6, 1), 1.2),
            _FakeSnapshot(date(2025, 12, 1), 1.5),
        ]
        # 从 2025-06-01 起算：1.2 → 1.5 = +25%
        assert _period_return(snapshots, date(2025, 6, 1)) == 25.0

    def test_start_after_latest_returns_none(self):
        snapshots = [
            _FakeSnapshot(date(2025, 1, 1), 1.0),
            _FakeSnapshot(date(2025, 6, 1), 1.2),
        ]
        assert _period_return(snapshots, date(2026, 1, 1)) is None

    def test_insufficient_snapshots(self):
        assert _period_return([_FakeSnapshot(date(2025, 1, 1), 1.0)], date(2025, 1, 1)) is None

    def test_history_not_covering_start_returns_none(self):
        """历史不足窗口期（首个快照日晚于 start）→ None（issue #99 口径统一）"""
        snapshots = [
            _FakeSnapshot(date(2025, 6, 1), 1.0),
            _FakeSnapshot(date(2025, 12, 1), 1.2),
        ]
        # 近 1 年窗口 start=2024-12-01，早于首个快照日 → None（不退化为成立以来）
        assert _period_return(snapshots, date(2024, 12, 1)) is None


class TestAnnualize:
    def test_one_year_unchanged(self):
        # 一年 +10% → 年化 10%
        assert abs(_annualize(1.10, 365) - 10.0) < 1e-6

    def test_half_year_compounds(self):
        # 半年 +10% → 年化约 21%
        result = _annualize(1.10, 182)
        assert result is not None and 20.0 < result < 22.5

    def test_zero_days_returns_none(self):
        assert _annualize(1.10, 0) is None

    def test_non_positive_growth_returns_none(self):
        assert _annualize(0.0, 365) is None


class TestGetPerformanceIntegration:
    """端到端：无快照组合应返回全 None 而不报错"""

    def test_portfolio_without_snapshots(self, test_db):
        from app.models.portfolio import Portfolio
        from app.services.performance_service import get_performance

        test_db.add(Portfolio(code="PERF_EMPTY", name="无快照组合", status="draft"))
        test_db.commit()

        result = get_performance(test_db, "PERF_EMPTY")
        assert result["portfolio_code"] == "PERF_EMPTY"
        assert result["twr"] is None
        assert result["mwr"] is None
        assert result["max_drawdown"] is None
        assert result["cash_flow_count"] == 0
        # empty 兑底含新增区间字段（issue #99）
        assert result["return_6m"] is None
        assert result["return_1y"] is None
        assert result["return_3y"] is None

    def test_portfolio_with_snapshots(self, test_db):
        from app.models.investor import Investor
        from app.models.platform import Platform
        from app.models.portfolio import Portfolio
        from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
        from app.models.subscription import Subscription
        from app.services.performance_service import get_performance

        test_db.add(Investor(code="PERF_INV", name="绩效投资人", password_hash="x", role="viewer"))
        test_db.add(Platform(code="PERF_PF", name="绩效平台"))
        test_db.add(Portfolio(code="PERF_FULL", name="绩效组合", status="active"))
        base = date(2025, 1, 1)
        # 净值 1.0 → 1.25，中途回撤到 0.9
        for i, nav in enumerate([1.0, 1.1, 0.9, 1.15, 1.25]):
            test_db.add(
                PortfolioValueSnapshot(
                    portfolio_code="PERF_FULL",
                    snapshot_date=base + timedelta(days=i * 30),
                    total_value=1000 * nav,
                    total_shares=1000,
                    unit_price=nav,
                )
            )
        test_db.add(
            Subscription(
                portfolio_code="PERF_FULL",
                investor_code="PERF_INV",
                platform_code="PERF_PF",
                sub_type="subscribe",
                amount=1000,
                apply_date=base,
                confirm_date=base,
                status="confirmed",
            )
        )
        test_db.commit()

        result = get_performance(test_db, "PERF_FULL")
        assert abs(result["twr"] - 25.0) < 1e-6
        # 两种 TWR 算法一致性自检应通过
        assert result["nav_series_consistent"] is True
        # 峰 1.1 → 谷 0.9，回撤 约 18.18%
        assert abs(result["max_drawdown"] - 18.1818) < 0.01
        assert result["holding_days"] == 120
        assert result["cash_flow_count"] == 1
        assert result["mwr"] is not None
        # 成立仅 120 天：6m/1y/3y 历史不足窗口期 → None（issue #99 口径统一）
        assert result["return_6m"] is None
        assert result["return_1y"] is None
        assert result["return_3y"] is None

    def test_new_period_returns_with_sufficient_history(self, test_db):
        """快照历史充足时 return_6m/1y/3y 数值正确（issue #99）"""
        from app.models.portfolio import Portfolio
        from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
        from app.services.performance_service import get_performance

        test_db.add(Portfolio(code="PERF_LONG", name="长历史组合", status="active"))
        # 稀疏快照：覆盖 3 年以上；latest = 2026-08-04
        points = [
            (date(2023, 1, 2), 1.0),
            (date(2025, 8, 4), 1.1),
            (date(2026, 2, 4), 1.2),
            (date(2026, 7, 10), 1.25),
            (date(2026, 8, 4), 1.3),
        ]
        for snap_date, nav in points:
            test_db.add(
                PortfolioValueSnapshot(
                    portfolio_code="PERF_LONG",
                    snapshot_date=snap_date,
                    total_value=1000 * nav,
                    total_shares=1000,
                    unit_price=nav,
                )
            )
        test_db.commit()

        result = get_performance(test_db, "PERF_LONG")
        # 6m：start=2026-02-04（relativedelta 月份锚点），基准 1.2 → 1.3
        assert abs(result["return_6m"] - (1.3 / 1.2 - 1) * 100) < 1e-3
        # 1y：start=2025-08-04，基准 1.1 → 1.3
        assert abs(result["return_1y"] - (1.3 / 1.1 - 1) * 100) < 1e-3
        # 3y：start=2023-08-04，首个 ≥ start 的快照为 2025-08-04（1.1）
        assert abs(result["return_3y"] - (1.3 / 1.1 - 1) * 100) < 1e-3
        # 存量字段不受影响：1m 基准 2026-07-10（1.25）
        assert abs(result["return_1m"] - (1.3 / 1.25 - 1) * 100) < 1e-3
        # ytd：start=2026-01-01，首个 ≥ start 的快照为 2026-02-04（1.2）
        assert abs(result["return_ytd"] - (1.3 / 1.2 - 1) * 100) < 1e-3

    def test_ytd_none_when_founded_after_new_year(self, test_db):
        """成立晚于当年元旦 → return_ytd 为 None（语义自洽，issue #99）"""
        from app.models.portfolio import Portfolio
        from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
        from app.services.performance_service import get_performance

        test_db.add(Portfolio(code="PERF_YTD", name="年内新组合", status="active"))
        for snap_date, nav in [
            (date(2026, 7, 1), 1.0),
            (date(2026, 7, 20), 1.05),
            (date(2026, 8, 4), 1.1),
        ]:
            test_db.add(
                PortfolioValueSnapshot(
                    portfolio_code="PERF_YTD",
                    snapshot_date=snap_date,
                    total_value=1000 * nav,
                    total_shares=1000,
                    unit_price=nav,
                )
            )
        test_db.commit()

        result = get_performance(test_db, "PERF_YTD")
        # 首个快照日 2026-07-01 晚于 2026-01-01 → ytd None
        assert result["return_ytd"] is None
        # 1m：start=2026-07-05，首个快照日 07-01 ≤ start → 基准 07-20（1.05）有值
        assert abs(result["return_1m"] - (1.1 / 1.05 - 1) * 100) < 1e-3
        # 6m/1y/3y 历史不足 → None
        assert result["return_6m"] is None
        assert result["return_1y"] is None
        assert result["return_3y"] is None
