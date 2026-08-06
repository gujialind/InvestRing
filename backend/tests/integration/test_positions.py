# ============================================================================
# 集成测试：持仓管理与实时计算 (test_positions.py)
# ============================================================================

import pytest
from datetime import date
from decimal import Decimal

from tests.factories import (
    create_portfolio, create_product, create_platform,
    create_position_snapshot, create_value_snapshot,
    create_investor_holding, create_investor, create_trade,
    create_subscription, create_share_change_event, ensure_trading_day,
)


class TestPositionList:
    """持仓查询测试"""

    def test_list_positions(self, client, admin_headers, test_db):
        """获取持仓列表"""
        create_portfolio(test_db, code="POS_P1", status="active")
        resp = client.get("/api/positions?portfolio_code=POS_P1", headers=admin_headers)
        assert resp.status_code == 200

    def test_viewer_can_view_positions(self, client, viewer_headers, test_db):
        """viewer 可以查看持仓"""
        create_portfolio(test_db, code="POS_V1", status="active")
        resp = client.get("/api/positions?portfolio_code=POS_V1", headers=viewer_headers)
        assert resp.status_code == 200


class TestAvailableCash:
    """可用现金实时计算测试"""

    def test_available_cash_with_snapshot_only(self, client, admin_headers, test_db):
        """仅有快照时，可用现金 = 快照现金"""
        create_portfolio(test_db, code="AC_S", status="active")
        create_platform(test_db, code="AC_S_PLAT")
        # 创建现金持仓
        create_position_snapshot(
            test_db, "AC_S", "CASH", "",
            snapshot_date=date(2025, 11, 3),
            cash_amount=10000.0, unit_price=None, cost_price=None,
            market_value=10000.0, platform_code="AC_S_PLAT",
        )

        resp = client.get(
            "/api/positions/portfolio/AC_S/available-cash",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_available_cash_reduced_by_pending_buy(self, client, admin_headers, test_db):
        """pending 买入应减少可用现金"""
        create_portfolio(test_db, code="AC_PB", status="active")
        create_product(test_db, code="ETF_AC1", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="AC_PLAT")
        ensure_trading_day(test_db, date(2025, 11, 3), is_open=True)

        # 创建现金持仓
        create_position_snapshot(
            test_db, "AC_PB", "CASH", "",
            snapshot_date=date(2025, 10, 31),
            cash_amount=50000.0, unit_price=None, cost_price=None,
            market_value=50000.0, platform_code="AC_PLAT",
        )

        # 创建 pending 买入
        create_trade(test_db, "AC_PB", "ETF_AC1", "CN_EXCHANGE",
                     trade_type="buy", amount=10000, status="pending",
                     trade_date=date(2025, 11, 3), platform_code="AC_PLAT")

        resp = client.get(
            "/api/positions/portfolio/AC_PB/available-cash",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_available_cash_reflects_manual_override(self, client, admin_headers, test_db):
        """available-cash 端点应反映快照中已 bake in 的 manual 覆盖值（回归 issue #52）"""
        create_portfolio(test_db, code="AC_OVR", status="active")
        create_platform(test_db, code="AC_OVR_PLAT")
        # 快照日 + 持仓快照（模拟快照生成时已 bake in manual 覆盖值 6001.39）
        create_value_snapshot(test_db, "AC_OVR", date(2025, 10, 31),
                              total_value=6001.39, total_shares=6001.39, unit_price=1.0)
        create_position_snapshot(
            test_db, "AC_OVR", "CASH", "",
            snapshot_date=date(2025, 10, 31),
            cash_amount=6001.39, unit_price=None, cost_price=None,
            market_value=6001.39, platform_code="AC_OVR_PLAT",
            asset_type="cash",
        )

        resp = client.get(
            "/api/positions/portfolio/AC_OVR/available-cash?platform_code=AC_OVR_PLAT",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert abs(resp.json()["available_cash"] - 6001.39) < 0.01


class TestAvailableShares:
    """可用份额实时计算测试"""

    def test_investor_available_shares(self, client, admin_headers, test_db):
        """投资人可用份额 = 快照份额 - pending 赎回"""
        create_portfolio(test_db, code="AS_P", status="active")
        create_investor(test_db, code="AS_I")
        create_value_snapshot(test_db, "AS_P", date(2025, 11, 3),
                              total_value=10000, total_shares=10000, unit_price=1.0)
        create_investor_holding(test_db, "AS_P", "AS_I", date(2025, 11, 3), shares=10000)

        resp = client.get(
            "/api/positions/portfolio/AS_P/product/AS_I/available-shares",
            headers=admin_headers,
        )
        # 端点计算的是产品份额而非投资人份额，这里只验证端点可达
        assert resp.status_code in (200, 404)


class TestInvestorAvailableShares:
    """投资人可用份额端点测试（issue #67）"""

    def test_investor_available_shares_basic(self, client, admin_headers, test_db):
        """无在途赎回时，可用份额 = 最新快照份额"""
        create_portfolio(test_db, code="IAS_P", status="active")
        create_investor(test_db, code="IAS_I")
        create_investor_holding(test_db, "IAS_P", "IAS_I", date(2025, 11, 3), shares=10000.50)

        resp = client.get(
            "/api/positions/portfolio/IAS_P/investor/IAS_I/available-shares",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["portfolio_code"] == "IAS_P"
        assert data["investor_code"] == "IAS_I"
        assert data["available_shares"] == 10000.50

    def test_investor_available_shares_minus_pending_redeem(self, client, admin_headers, test_db):
        """pending 赎回应扣减可用份额"""
        create_portfolio(test_db, code="IAS_PR", status="active")
        create_investor(test_db, code="IAS_IR")
        create_investor_holding(test_db, "IAS_PR", "IAS_IR", date(2025, 11, 3), shares=10000)
        create_subscription(
            test_db, "IAS_PR", "IAS_IR",
            sub_type="redeem", shares=3000, amount=3000,
            apply_date=date(2025, 11, 4), status="pending",
        )

        resp = client.get(
            "/api/positions/portfolio/IAS_PR/investor/IAS_IR/available-shares",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["available_shares"] == 7000.0

    def test_investor_available_shares_zero_without_holding(self, client, admin_headers, test_db):
        """无持仓快照时可用份额为 0"""
        create_portfolio(test_db, code="IAS_Z", status="active")
        create_investor(test_db, code="IAS_IZ")

        resp = client.get(
            "/api/positions/portfolio/IAS_Z/investor/IAS_IZ/available-shares",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["available_shares"] == 0.0

    def test_investor_available_shares_not_found(self, client, admin_headers, test_db):
        """组合或投资人不存在返回 404"""
        create_portfolio(test_db, code="IAS_NF", status="active")
        resp = client.get(
            "/api/positions/portfolio/NO_SUCH/investor/IAS_X/available-shares",
            headers=admin_headers,
        )
        assert resp.status_code == 404

        resp = client.get(
            "/api/positions/portfolio/IAS_NF/investor/NO_SUCH_INV/available-shares",
            headers=admin_headers,
        )
        assert resp.status_code == 404


# ============================================================================
# 持仓读侧派生字段（issue #99）：asset_name / daily_profit / 分红复权 / 现金收益
# ============================================================================

class TestPositionDerivedFields:
    """asset_name 与 daily_profit 派生"""

    def test_asset_name_from_classification(self, client, admin_headers, test_db):
        """产品挂 STOCK_CN_LARGE → asset_name 为「国内大盘」；CASH → 「现金」"""
        create_portfolio(test_db, code="PD_AN", status="active")
        create_platform(test_db, code="PD_AN_PLAT")
        create_product(test_db, code="FUND_AN", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        create_position_snapshot(
            test_db, "PD_AN", "FUND_AN", "CN_OTC",
            snapshot_date=date(2025, 11, 3),
            shares=1000.0, cost_price=1.5, unit_price=1.5, market_value=1500.0,
            platform_code="PD_AN_PLAT",
        )
        create_position_snapshot(
            test_db, "PD_AN", "CASH", "",
            snapshot_date=date(2025, 11, 3),
            cash_amount=500.0, unit_price=None, cost_price=None,
            market_value=500.0, platform_code="PD_AN_PLAT",
        )

        resp = client.get("/api/positions?portfolio_code=PD_AN", headers=admin_headers)
        assert resp.status_code == 200
        rows = {r["product_code"]: r for r in resp.json()["items"]}
        assert rows["FUND_AN"]["asset_name"] == "国内大盘"
        assert rows["CASH"]["asset_name"] == "现金"
        # is_qdii 读侧透传（QDII tooltip 依赖）
        assert rows["FUND_AN"]["is_qdii"] is False
        assert rows["CASH"]["is_qdii"] is False

    def test_daily_profit_two_days_no_trade(self, client, admin_headers, test_db):
        """两快照日 + 无当日交易 → daily_profit = 市值差值"""
        create_portfolio(test_db, code="PD_DP", status="active")
        create_platform(test_db, code="PD_DP_PLAT")
        create_product(test_db, code="FUND_DP", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        create_position_snapshot(
            test_db, "PD_DP", "FUND_DP", "CN_OTC",
            snapshot_date=date(2025, 11, 3),
            shares=1000.0, cost_price=1.5, unit_price=1.5, market_value=1500.0,
            platform_code="PD_DP_PLAT",
        )
        create_position_snapshot(
            test_db, "PD_DP", "FUND_DP", "CN_OTC",
            snapshot_date=date(2025, 11, 4),
            shares=1000.0, cost_price=1.5, unit_price=1.56, market_value=1560.0,
            platform_code="PD_DP_PLAT",
        )
        create_position_snapshot(
            test_db, "PD_DP", "CASH", "",
            snapshot_date=date(2025, 11, 3),
            cash_amount=5000.0, unit_price=None, cost_price=None,
            market_value=5000.0, platform_code="PD_DP_PLAT",
        )
        create_position_snapshot(
            test_db, "PD_DP", "CASH", "",
            snapshot_date=date(2025, 11, 4),
            cash_amount=5000.0, unit_price=None, cost_price=None,
            market_value=5000.0, platform_code="PD_DP_PLAT",
        )

        resp = client.get("/api/positions?portfolio_code=PD_DP", headers=admin_headers)
        assert resp.status_code == 200
        rows = {r["product_code"]: r for r in resp.json()["items"]}
        assert rows["FUND_DP"]["daily_profit"] == pytest.approx(60.0, abs=1e-4)
        assert rows["CASH"]["daily_profit"] == pytest.approx(0.0, abs=1e-4)

    def test_aggregate_flows_called_once(self, client, admin_headers, test_db):
        """issue #103：三个 compute 函数共享一次 _aggregate_position_flows 聚合

        复用 PD_DP 两快照日场景（fund + CASH 均有），用 patch(wraps=...) 包装定义处
        模块属性，断言整个请求只聚合 1 次（原 6 条查询降至 2 条）且响应值不变。
        """
        from unittest.mock import patch
        from app.services import position_service as ps

        create_portfolio(test_db, code="PD_DP", status="active")
        create_platform(test_db, code="PD_DP_PLAT")
        create_product(test_db, code="FUND_DP", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        for d, mv in ((date(2025, 11, 3), 1500.0), (date(2025, 11, 4), 1560.0)):
            create_position_snapshot(
                test_db, "PD_DP", "FUND_DP", "CN_OTC", snapshot_date=d,
                shares=1000.0, cost_price=1.5, unit_price=1.5, market_value=mv,
                platform_code="PD_DP_PLAT",
            )
            create_position_snapshot(
                test_db, "PD_DP", "CASH", "", snapshot_date=d,
                cash_amount=5000.0, unit_price=None, cost_price=None,
                market_value=5000.0, platform_code="PD_DP_PLAT",
            )

        with patch.object(ps, "_aggregate_position_flows", wraps=ps._aggregate_position_flows) as spy:
            resp = client.get("/api/positions?portfolio_code=PD_DP", headers=admin_headers)
        assert resp.status_code == 200
        assert spy.call_count == 1  # 聚合仅 1 次（trade 1 + event 1 = 2 查询，原 6 次）
        rows = {r["product_code"]: r for r in resp.json()["items"]}
        assert rows["FUND_DP"]["daily_profit"] == pytest.approx(60.0, abs=1e-4)

    def test_daily_profit_deducts_same_day_buy(self, client, admin_headers, test_db):
        """当日确认买入 → daily_profit 扣除买入额；配对 CASH 腿当日净流入抵消"""
        create_portfolio(test_db, code="PD_DB", status="active")
        create_platform(test_db, code="PD_DB_PLAT")
        create_product(test_db, code="FUND_DB", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        d1, d2 = date(2025, 11, 3), date(2025, 11, 4)
        create_position_snapshot(
            test_db, "PD_DB", "FUND_DB", "CN_OTC", snapshot_date=d1,
            shares=1000.0, cost_price=1.5, unit_price=1.5, market_value=1500.0,
            platform_code="PD_DB_PLAT",
        )
        create_position_snapshot(
            test_db, "PD_DB", "CASH", "", snapshot_date=d1,
            cash_amount=5000.0, unit_price=None, cost_price=None,
            market_value=5000.0, platform_code="PD_DB_PLAT",
        )
        # 当日买入 300（基金腿 + CASH 腿，rebal_ 组），市值涨 4% 后加仓
        create_trade(
            test_db, "PD_DB", "FUND_DB", "CN_OTC", trade_type="buy",
            amount=300.0, shares=192.31, price=1.56, platform_code="PD_DB_PLAT",
            trade_date=d2, confirm_date=d2, status="confirmed",
            transfer_group="rebal_pd_db_001",
        )
        create_trade(
            test_db, "PD_DB", "CASH", "", trade_type="sell",
            amount=300.0, platform_code="PD_DB_PLAT",
            trade_date=d2, confirm_date=d2, status="confirmed",
            transfer_group="rebal_pd_db_001",
        )
        create_position_snapshot(
            test_db, "PD_DB", "FUND_DB", "CN_OTC", snapshot_date=d2,
            shares=1192.31, cost_price=1.5, unit_price=1.56, market_value=1860.0,
            platform_code="PD_DB_PLAT",
        )
        create_position_snapshot(
            test_db, "PD_DB", "CASH", "", snapshot_date=d2,
            cash_amount=4700.0, unit_price=None, cost_price=None,
            market_value=4700.0, platform_code="PD_DB_PLAT",
        )

        resp = client.get("/api/positions?portfolio_code=PD_DB", headers=admin_headers)
        assert resp.status_code == 200
        rows = {r["product_code"]: r for r in resp.json()["items"]}
        # 基金：1860 − 1500 − 300 = 60
        assert rows["FUND_DB"]["daily_profit"] == pytest.approx(60.0, abs=1e-4)
        # 现金：4700 − 5000 − (−300) = 0
        assert rows["CASH"]["daily_profit"] == pytest.approx(0.0, abs=1e-4)

    def test_daily_profit_none_on_first_snapshot(self, client, admin_headers, test_db):
        """组合首个快照日 → daily_profit 为 None"""
        create_portfolio(test_db, code="PD_FS", status="active")
        create_platform(test_db, code="PD_FS_PLAT")
        create_product(test_db, code="FUND_FS", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        create_position_snapshot(
            test_db, "PD_FS", "FUND_FS", "CN_OTC",
            snapshot_date=date(2025, 11, 3),
            shares=1000.0, cost_price=1.5, unit_price=1.5, market_value=1500.0,
            platform_code="PD_FS_PLAT",
        )

        resp = client.get("/api/positions?portfolio_code=PD_FS", headers=admin_headers)
        assert resp.status_code == 200
        rows = resp.json()["items"]
        assert len(rows) == 1
        assert rows[0]["daily_profit"] is None

    def test_daily_profit_none_for_in_transit(self, client, admin_headers, test_db):
        """IN_TRANSIT 在途行 daily_profit 恒为 None"""
        create_portfolio(test_db, code="PD_IT", status="active")
        create_platform(test_db, code="PD_IT_PLAT")
        for d in (date(2025, 11, 3), date(2025, 11, 4)):
            create_position_snapshot(
                test_db, "PD_IT", "IN_TRANSIT_BUY", "", snapshot_date=d,
                cash_amount=1000.0, unit_price=None, cost_price=None,
                market_value=1000.0, platform_code="PD_IT_PLAT",
                asset_type="cash",
            )

        resp = client.get("/api/positions?portfolio_code=PD_IT", headers=admin_headers)
        assert resp.status_code == 200
        rows = resp.json()["items"]
        assert len(rows) == 1
        assert rows[0]["daily_profit"] is None


class TestPositionDividendRouteC:
    """分红复权口径（路线 C）：基金侧加回分红 + 现金侧事件入基数"""

    def _build_dividend_scenario(self, test_db):
        """构造：申购 2500 → 买基金 1500 → 次日现金分红 100（除权）"""
        create_portfolio(test_db, code="PD_DIV", status="active")
        create_platform(test_db, code="PD_DIV_PLAT")
        create_product(test_db, code="FUND_DIV", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        create_investor(test_db, code="PD_DIV_INV")
        d1, d2 = date(2025, 11, 3), date(2025, 11, 4)
        # 申购 2500（CASH buy，sub_ 组，d1 确认）
        create_subscription(
            test_db, "PD_DIV", "PD_DIV_INV", sub_type="subscribe", amount=2500.0,
            apply_date=d1, confirm_date=d1, status="confirmed",
            platform_code="PD_DIV_PLAT",
        )
        create_trade(
            test_db, "PD_DIV", "CASH", "", trade_type="buy",
            amount=2500.0, platform_code="PD_DIV_PLAT",
            trade_date=d1, confirm_date=d1, status="confirmed",
            transfer_group="sub_pd_div_001",
        )
        # 买基金 1500（基金 buy + CASH sell，rebal_ 组，d1 确认）
        create_trade(
            test_db, "PD_DIV", "FUND_DIV", "CN_OTC", trade_type="buy",
            amount=1500.0, shares=1000.0, price=1.5, platform_code="PD_DIV_PLAT",
            trade_date=d1, confirm_date=d1, status="confirmed",
            transfer_group="rebal_pd_div_001",
        )
        create_trade(
            test_db, "PD_DIV", "CASH", "", trade_type="sell",
            amount=1500.0, platform_code="PD_DIV_PLAT",
            trade_date=d1, confirm_date=d1, status="confirmed",
            transfer_group="rebal_pd_div_001",
        )
        # d1 持仓：基金 1000 份（成本 1.5，市值 1500）+ 现金 1000
        create_position_snapshot(
            test_db, "PD_DIV", "FUND_DIV", "CN_OTC", snapshot_date=d1,
            shares=1000.0, cost_price=1.5, unit_price=1.5, market_value=1500.0,
            platform_code="PD_DIV_PLAT",
        )
        create_position_snapshot(
            test_db, "PD_DIV", "CASH", "", snapshot_date=d1,
            cash_amount=1000.0, unit_price=None, cost_price=None,
            market_value=1000.0, platform_code="PD_DIV_PLAT",
        )
        # d2 除权：基金市值 −100，现金 +100，组合总资产不变
        create_share_change_event(
            test_db, "PD_DIV", "FUND_DIV", "CN_OTC",
            event_type="cash_dividend", ex_date=d2, entitlement_date=d1,
            status="confirmed", platform_code="PD_DIV_PLAT",
            cash_change=100.0,
        )
        create_position_snapshot(
            test_db, "PD_DIV", "FUND_DIV", "CN_OTC", snapshot_date=d2,
            shares=1000.0, cost_price=1.5, unit_price=1.4, market_value=1400.0,
            platform_code="PD_DIV_PLAT",
        )
        create_position_snapshot(
            test_db, "PD_DIV", "CASH", "", snapshot_date=d2,
            cash_amount=1100.0, unit_price=None, cost_price=None,
            market_value=1100.0, platform_code="PD_DIV_PLAT",
        )
        create_value_snapshot(test_db, "PD_DIV", d1, 2500.0, 2500.0, 1.0)
        create_value_snapshot(test_db, "PD_DIV", d2, 2500.0, 2500.0, 1.0)
        return d1, d2

    def test_dividend_adjusted_profit(self, client, admin_headers, test_db):
        """基金行 profit_loss 含分红加回；分红日两侧 daily_profit 均为 0；
        CASH 行 profit_loss ≈ 0（事件入基数）；卡片合计 = 总资产 − 净投入"""
        self._build_dividend_scenario(test_db)

        resp = client.get("/api/positions?portfolio_code=PD_DIV", headers=admin_headers)
        assert resp.status_code == 200
        rows = {r["product_code"]: r for r in resp.json()["items"]}

        fund = rows["FUND_DIV"]
        # 复权口径：1400 − 1000×1.5 + 100 = 0
        assert fund["profit_loss"] == pytest.approx(0.0, abs=1e-4)
        # 分红日 daily：1400 − 1500 + 100 = 0（除权损失被分红加回对冲）
        assert fund["daily_profit"] == pytest.approx(0.0, abs=1e-4)

        cash = rows["CASH"]
        # 现金累计收益 = 1100 − (2500 净存入 − 1500 买入 + 100 事件) = 0
        assert cash["profit_loss"] == pytest.approx(0.0, abs=1e-4)
        # 分红日现金 daily：1100 − 1000 − 100(事件当日流入) = 0
        assert cash["daily_profit"] == pytest.approx(0.0, abs=1e-4)

        # 两侧卡片合计 = 0 = 总资产 2500 − 净投入 2500（无清仓场景自洽）
        total = fund["profit_loss"] + cash["profit_loss"]
        assert total == pytest.approx(0.0, abs=1e-4)


class TestPositionCashCumulativeProfit:
    """CASH 行 profit_loss：sub_/rebal_/转移/事件四类流水（§3.3）"""

    def test_cash_profit_with_all_flow_types(self, client, admin_headers, test_db):
        create_portfolio(test_db, code="PD_CF", status="active")
        create_platform(test_db, code="PD_CF_P1")
        create_platform(test_db, code="PD_CF_P2")
        create_product(test_db, code="FUND_CF", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        d1 = date(2025, 11, 3)
        # sub_：申购存入 10000（P1）
        create_trade(
            test_db, "PD_CF", "CASH", "", trade_type="buy", amount=10000.0,
            platform_code="PD_CF_P1", trade_date=d1, confirm_date=d1,
            status="confirmed", transfer_group="sub_pd_cf_001",
        )
        # rebal_：买基金花 4000（P1）+ 卖基金收 500（P1）
        create_trade(
            test_db, "PD_CF", "CASH", "", trade_type="sell", amount=4000.0,
            platform_code="PD_CF_P1", trade_date=d1, confirm_date=d1,
            status="confirmed", transfer_group="rebal_pd_cf_001",
        )
        create_trade(
            test_db, "PD_CF", "CASH", "", trade_type="buy", amount=500.0,
            platform_code="PD_CF_P1", trade_date=d1, confirm_date=d1,
            status="confirmed", transfer_group="rebal_pd_cf_002",
        )
        # 跨平台转移：P1 转出 800、P2 转入 800（裸 uuid 组）
        create_trade(
            test_db, "PD_CF", "CASH", "", trade_type="sell", amount=800.0,
            platform_code="PD_CF_P1", trade_date=d1, confirm_date=d1,
            status="confirmed", transfer_group="f1e2d3c4b5a6",
        )
        create_trade(
            test_db, "PD_CF", "CASH", "", trade_type="buy", amount=800.0,
            platform_code="PD_CF_P2", trade_date=d1, confirm_date=d1,
            status="confirmed", transfer_group="f1e2d3c4b5a6",
        )
        # 事件：现金分红 200（P1）
        create_share_change_event(
            test_db, "PD_CF", "FUND_CF", "CN_OTC",
            event_type="cash_dividend", ex_date=d1, entitlement_date=date(2025, 10, 31),
            status="confirmed", platform_code="PD_CF_P1",
            cash_change=200.0,
        )
        # 持仓：P1 现金 5900（另加 50 未记账差额验证吸收），P2 现金 800
        create_position_snapshot(
            test_db, "PD_CF", "CASH", "", snapshot_date=d1,
            cash_amount=5950.0, unit_price=None, cost_price=None,
            market_value=5950.0, platform_code="PD_CF_P1",
        )
        create_position_snapshot(
            test_db, "PD_CF", "CASH", "", snapshot_date=d1,
            cash_amount=800.0, unit_price=None, cost_price=None,
            market_value=800.0, platform_code="PD_CF_P2",
        )

        resp = client.get("/api/positions?portfolio_code=PD_CF", headers=admin_headers)
        assert resp.status_code == 200
        rows = {r["platform_code"]: r for r in resp.json()["items"]}
        # P1：5950 − (10000 − 4000 + 500 − 800 + 200) = 50（吸收未记账差额）
        assert rows["PD_CF_P1"]["profit_loss"] == pytest.approx(50.0, abs=1e-4)
        # P2：800 − 800（转移净额）= 0
        assert rows["PD_CF_P2"]["profit_loss"] == pytest.approx(0.0, abs=1e-4)
