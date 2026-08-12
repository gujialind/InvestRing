# ============================================================================
# 集成测试：市场解析接入点 (issue #83)
# ============================================================================
# 覆盖 trade create 与产品 GET 省略 market 时的行为：
# - 唯一市场自动补全成功
# - LOF 一码多市场返回 MARKET_AMBIGUOUS(422)，details.available_markets 正确
# - 产品不存在返回 PRODUCT_NOT_FOUND(404)，details.product_code 正确
# ============================================================================

import pytest
from datetime import date

from tests.factories import (
    create_portfolio, create_product, create_platform, create_trade,
    ensure_trading_day,
)


def _give_cash(test_db, portfolio_code, platform_code, amount=50000.0):
    """通过 confirmed CASH buy trade 提供可用现金"""
    create_trade(
        test_db, portfolio_code, "CASH", "",
        trade_type="buy", amount=amount, price=None,
        platform_code=platform_code, trade_date=date(2025, 10, 3),
        confirm_date=date(2025, 10, 3), status="confirmed",
    )


class TestTradeCreateMarketResolve:
    """POST /api/trades 省略 market 的解析行为"""

    def test_omit_market_unique_autofill(self, client, admin_headers, test_db):
        """唯一市场自动补全，创建成功且 market 落库为解析值"""
        create_portfolio(test_db, code="MKR_P1", status="active")
        create_product(test_db, code="MKR_ETF", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="MKR_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        _give_cash(test_db, "MKR_P1", "MKR_PLAT")

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "MKR_P1",
                "product_code": "MKR_ETF",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "MKR_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        data = resp.json()
        assert data["status"] == "pending"
        assert data["market"] == "CN_EXCHANGE"

    def test_omit_market_ambiguous(self, client, admin_headers, test_db):
        """LOF 一码多市场返回 MARKET_AMBIGUOUS(422)，details.available_markets 正确"""
        create_portfolio(test_db, code="MKR_P2", status="active")
        create_product(test_db, code="MKR_LOF", market="CN_OTC",
                       product_type="LOF", asset_class_code="ASSET_STOCK")
        create_product(test_db, code="MKR_LOF", market="CN_EXCHANGE",
                       product_type="LOF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="MKR_PLAT2")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        _give_cash(test_db, "MKR_P2", "MKR_PLAT2")

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "MKR_P2",
                "product_code": "MKR_LOF",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "MKR_PLAT2",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "MARKET_AMBIGUOUS"
        assert detail["details"]["product_code"] == "MKR_LOF"
        assert detail["details"]["available_markets"] == ["CN_EXCHANGE", "CN_OTC"]

    def test_omit_market_explicit_still_works(self, client, admin_headers, test_db):
        """多市场产品显式指定 market 仍可正常创建"""
        create_portfolio(test_db, code="MKR_P4", status="active")
        create_product(test_db, code="MKR_LOF2", market="CN_OTC",
                       product_type="LOF", asset_class_code="ASSET_STOCK")
        create_product(test_db, code="MKR_LOF2", market="CN_EXCHANGE",
                       product_type="LOF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="MKR_PLAT4")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        _give_cash(test_db, "MKR_P4", "MKR_PLAT4")

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "MKR_P4",
                "product_code": "MKR_LOF2",
                "market": "CN_OTC",
                "trade_type": "buy",
                "amount": 10000.0,
                "platform_code": "MKR_PLAT4",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        assert resp.json()["market"] == "CN_OTC"

    def test_omit_market_product_not_found(self, client, admin_headers, test_db):
        """产品不存在返回 PRODUCT_NOT_FOUND(404)，details.product_code 正确"""
        create_portfolio(test_db, code="MKR_P3", status="active")
        create_platform(test_db, code="MKR_PLAT3")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "MKR_P3",
                "product_code": "MKR_MISSING",
                "trade_type": "buy",
                "amount": 10000.0,
                "platform_code": "MKR_PLAT3",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["error"] == "PRODUCT_NOT_FOUND"
        assert detail["details"] == {"product_code": "MKR_MISSING"}


class TestProductGetMarketResolve:
    """GET /api/products/{code}（不带 market）的解析行为"""

    def test_get_unique_autofill(self, client, admin_headers, test_db):
        """唯一市场自动补全返回产品详情（响应含 market 字段）"""
        create_product(test_db, code="MKR_GET1", market="CN_OTC")
        resp = client.get("/api/products/MKR_GET1", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "MKR_GET1"
        assert data["market"] == "CN_OTC"

    def test_get_ambiguous(self, client, admin_headers, test_db):
        """LOF 一码多市场返回 MARKET_AMBIGUOUS(422)"""
        create_product(test_db, code="MKR_GET2", market="CN_OTC", product_type="LOF")
        create_product(test_db, code="MKR_GET2", market="CN_EXCHANGE", product_type="LOF")
        resp = client.get("/api/products/MKR_GET2", headers=admin_headers)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "MARKET_AMBIGUOUS"
        assert detail["details"]["available_markets"] == ["CN_EXCHANGE", "CN_OTC"]

    def test_get_not_found(self, client, admin_headers, test_db):
        """产品不存在返回 PRODUCT_NOT_FOUND(404)"""
        resp = client.get("/api/products/MKR_GET_NONE", headers=admin_headers)
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["error"] == "PRODUCT_NOT_FOUND"
        assert detail["details"] == {"product_code": "MKR_GET_NONE"}

    def test_get_with_market_unchanged(self, client, admin_headers, test_db):
        """带 market 的既有端点行为不变"""
        create_product(test_db, code="MKR_GET3", market="CN_OTC")
        resp = client.get("/api/products/MKR_GET3/CN_OTC", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["market"] == "CN_OTC"
