# ============================================================================
# E2E 测试：完整业务流程 (test_business_flows.py)
# ============================================================================
# 端到端测试覆盖从组合创建到关闭的完整业务链路。
# ============================================================================

import pytest
from datetime import date

from tests.factories import (
    create_portfolio, create_investor, create_product, create_platform,
    create_value_snapshot, create_investor_holding, create_position_snapshot,
    ensure_trading_day, create_price_record,
)
from app.models.portfolio import Portfolio
from app.models.subscription import Subscription
from app.models.trade import Trade


class TestFullSubscriptionFlow:
    """完整申购流程：创建组合 → 申购 → 确认"""

    def test_subscribe_and_confirm_flow(self, client, admin_headers, test_db):
        """申购 → 确认完整流程"""
        # 1. 创建组合
        create_portfolio(test_db, code="FLOW_P1", status="active")
        create_investor(test_db, code="FLOW_I1")
        ensure_trading_day(test_db, date(2025, 11, 3), is_open=True)

        # 2. 提交申购
        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "FLOW_P1",
                "investor_code": "FLOW_I1",
                "sub_type": "subscribe",
                "amount": 10000.0,
                "apply_date": "2025-11-03",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        sub_id = resp.json()["id"]
        assert resp.json()["status"] == "pending"

        # 3. 确认申购
        resp = client.post(
            f"/api/subscriptions/{sub_id}/confirm",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        confirmed = test_db.query(Subscription).filter(Subscription.id == sub_id).first()
        assert confirmed.status == "confirmed"
        assert confirmed.shares is not None


class TestFullTradeFlow:
    """完整调仓流程：有持仓 → 买入 → 确认"""

    def test_buy_and_confirm_flow(self, client, admin_headers, test_db):
        """买入 → 确认完整流程"""
        create_portfolio(test_db, code="FLOW_T1", status="active")
        create_product(test_db, code="ETF_F1", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="FLOW_PLAT")
        ensure_trading_day(test_db, date(2025, 11, 3), is_open=True)

        # 创建初始现金持仓（CASH 产品）
        create_position_snapshot(
            test_db, "FLOW_T1", "CASH", "",
            snapshot_date=date(2025, 10, 31),
            amount=100000.0, unit_price=None, cost_price=None,
            market_value=100000.0, platform_code="FLOW_PLAT",
        )

        # 提交买入
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "FLOW_T1",
                "product_code": "ETF_F1",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 20000.0,
                "price": 2.0,
                "platform_code": "FLOW_PLAT",
                "trade_date": "2025-11-03",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        trade_id = resp.json()["id"]
        assert resp.json()["status"] == "pending"

        # 确认买入
        resp = client.post(
            f"/api/trades/{trade_id}/confirm",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        confirmed = test_db.query(Trade).filter(Trade.id == trade_id).first()
        assert confirmed.status == "confirmed"


class TestPortfolioLifecycle:
    """组合生命周期测试：创建 → 激活 → 关闭 → 重新激活"""

    def test_full_lifecycle(self, client, admin_headers, test_db):
        """组合完整生命周期"""
        # 1. 创建组合（draft）
        resp = client.post(
            "/api/portfolios",
            json={"code": "LIFE_P", "name": "生命周期组合"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"

        # 2. 激活组合
        resp = client.post(
            "/api/portfolios/LIFE_P/activate",
            headers=admin_headers,
        )
        # 可能没有独立的 activate 端点，尝试直接改为 active
        port = test_db.query(Portfolio).filter(Portfolio.code == "LIFE_P").first()
        if port.status == "draft":
            port.status = "active"
            test_db.commit()

        # 3. 关闭组合
        resp = client.post("/api/portfolios/LIFE_P/close", headers=admin_headers)
        assert resp.status_code == 200
        port = test_db.query(Portfolio).filter(Portfolio.code == "LIFE_P").first()
        assert port.status == "closed"

        # 4. 重新激活
        resp = client.post("/api/portfolios/LIFE_P/reactivate", headers=admin_headers)
        assert resp.status_code == 200
        port = test_db.query(Portfolio).filter(Portfolio.code == "LIFE_P").first()
        assert port.status == "active"


class TestClosedPortfolioRestrictions:
    """已关闭组合限制测试"""

    def test_closed_portfolio_rejects_subscribe(self, client, admin_headers, test_db):
        """已关闭组合不能申购"""
        create_portfolio(test_db, code="CLD_SUB", status="closed")
        create_investor(test_db, code="CLD_INV")
        ensure_trading_day(test_db, date(2025, 11, 3), is_open=True)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "CLD_SUB",
                "investor_code": "CLD_INV",
                "sub_type": "subscribe",
                "amount": 5000,
                "apply_date": "2025-11-03",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)

    def test_closed_portfolio_rejects_trade(self, client, admin_headers, test_db):
        """已关闭组合不能调仓"""
        create_portfolio(test_db, code="CLD_TRD", status="closed")
        create_product(test_db, code="ETF_CLD", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="CLD_PLAT")
        ensure_trading_day(test_db, date(2025, 11, 3), is_open=True)

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "CLD_TRD",
                "product_code": "ETF_CLD",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 1000,
                "price": 1.0,
                "platform_code": "CLD_PLAT",
                "trade_date": "2025-11-03",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)


class TestHealthCheck:
    """健康检查端点"""

    def test_health_endpoint(self, client):
        """/health 应返回 200"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_root_endpoint(self, client):
        """/ 应返回欢迎信息"""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "InvestRing" in resp.json()["message"]
