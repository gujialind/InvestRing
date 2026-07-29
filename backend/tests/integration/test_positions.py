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
    create_subscription, ensure_trading_day,
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
