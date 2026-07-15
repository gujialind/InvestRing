# ============================================================================
# 集成测试：调仓交易 (test_trades.py)
# ============================================================================

import pytest
from datetime import date

from tests.factories import (
    create_portfolio, create_product, create_platform, create_trade,
    create_position_snapshot, create_value_snapshot, create_investor_holding,
    create_investor, ensure_trading_day, create_price_record,
)
from app.models.trade import Trade


class TestBuyTrade:
    """买入交易测试"""

    def test_create_buy_trade_pending(self, client, admin_headers, test_db):
        """买入交易创建后应为 pending"""
        create_portfolio(test_db, code="TRD_P1", status="active")
        create_product(test_db, code="ETF01", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="TRD_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        # 提供可用现金：通过 confirmed CASH buy trade 表示现金流入（如申购确认）
        create_trade(
            test_db, "TRD_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="TRD_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "TRD_P1",
                "product_code": "ETF01",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "TRD_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        data = resp.json()
        assert data["status"] == "pending"
        assert data["trade_type"] == "buy"

    def test_buy_insufficient_cash_rejected(self, client, admin_headers, test_db):
        """买入金额超过可用现金应被拒绝"""
        create_portfolio(test_db, code="TRD_NC", status="active")
        create_product(test_db, code="ETF02", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="TRD_PLAT2")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        # 少量现金
        create_value_snapshot(test_db, "TRD_NC", date(2025, 10, 3),
                              total_value=100, total_shares=100, unit_price=1.0)

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "TRD_NC",
                "product_code": "ETF02",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 999999.0,
                "price": 1.5,
                "platform_code": "TRD_PLAT2",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_buy_zero_amount_rejected(self, client, admin_headers, test_db):
        """买入金额为 0 应被拒绝"""
        create_portfolio(test_db, code="TRD_Z", status="active")
        create_product(test_db, code="ETF03", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="TRD_PLAT3")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "TRD_Z",
                "product_code": "ETF03",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 0,
                "price": 1.5,
                "platform_code": "TRD_PLAT3",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)


class TestSellTrade:
    """卖出交易测试"""

    def test_create_sell_trade_pending(self, client, admin_headers, test_db):
        """卖出交易创建后应为 pending"""
        create_portfolio(test_db, code="SEL_P1", status="active")
        create_product(test_db, code="ETF04", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="SEL_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        # 先有持仓
        create_position_snapshot(
            test_db, "SEL_P1", "ETF04", "CN_EXCHANGE",
            snapshot_date=date(2025, 10, 3),
            shares=1000.0, unit_price=1.5, cost_price=1.5,
            market_value=1500.0, platform_code="SEL_PLAT",
        )

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "SEL_P1",
                "product_code": "ETF04",
                "market": "CN_EXCHANGE",
                "trade_type": "sell",
                "shares": 500.0,
                "price": 1.6,
                "platform_code": "SEL_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["status"] == "pending"
        assert data["trade_type"] == "sell"

    def test_sell_exceeds_available_shares_rejected(self, client, admin_headers, test_db):
        """卖出份额超过可用份额应被拒绝"""
        create_portfolio(test_db, code="SEL_EX", status="active")
        create_product(test_db, code="ETF05", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE")
        create_platform(test_db, code="SEL_PLAT2")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        create_position_snapshot(
            test_db, "SEL_EX", "ETF05", "CN_EXCHANGE",
            snapshot_date=date(2025, 10, 3),
            shares=100.0, unit_price=1.5, cost_price=1.5,
            market_value=150.0, platform_code="SEL_PLAT2",
        )

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "SEL_EX",
                "product_code": "ETF05",
                "market": "CN_EXCHANGE",
                "trade_type": "sell",
                "shares": 99999.0,
                "price": 1.6,
                "platform_code": "SEL_PLAT2",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestTradePermissions:
    """调仓交易权限测试"""

    def test_viewer_cannot_trade(self, client, viewer_headers):
        """viewer 不能提交调仓交易"""
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "X",
                "product_code": "X",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 1000,
                "price": 1.0,
                "trade_date": "2025-10-06",
            },
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_list_trades(self, client, admin_headers):
        """获取调仓交易列表"""
        resp = client.get("/api/trades", headers=admin_headers)
        assert resp.status_code == 200
        assert "items" in resp.json()
