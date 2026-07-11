# ============================================================================
# 集成测试：份额变动事件 (test_share_events.py)
# ============================================================================

import pytest
from datetime import date

from tests.factories import (
    create_portfolio, create_product, create_platform,
    create_share_change_event, create_position_snapshot,
    ensure_trading_day,
)
from app.models.share_change_event import ShareChangeEvent


class TestShareChangeEventCreate:
    """份额变动事件创建测试"""

    def test_create_cash_dividend_event(self, client, admin_headers, test_db):
        """创建现金分红事件"""
        create_portfolio(test_db, code="SCE_P1", status="active")
        create_product(test_db, code="FUND_SC1", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        ensure_trading_day(test_db, date(2025, 12, 8), is_open=True)

        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "SCE_P1",
                "product_code": "FUND_SC1",
                "market": "CN_OTC",
                "event_type": "cash_dividend",
                "ex_date": "2025-12-10",
                "entitlement_date": "2025-12-08",
                "event_source": "manual",
                "div_cash": 0.5,
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["event_type"] == "cash_dividend"
        assert data["status"] == "pending"

    def test_create_reinvest_dividend_event(self, client, admin_headers, test_db):
        """创建分红再投资事件"""
        create_portfolio(test_db, code="SCE_P2", status="active")
        create_product(test_db, code="FUND_SC2", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        ensure_trading_day(test_db, date(2025, 12, 8), is_open=True)

        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "SCE_P2",
                "product_code": "FUND_SC2",
                "market": "CN_OTC",
                "event_type": "reinvest_dividend",
                "ex_date": "2025-12-10",
                "entitlement_date": "2025-12-08",
                "event_source": "manual",
                "div_cash": 0.5,
                "reinvest_nav": 1.2,
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["event_type"] == "reinvest_dividend"

    def test_create_share_split_event(self, client, admin_headers, test_db):
        """创建份额拆分事件"""
        create_portfolio(test_db, code="SCE_P3", status="active")
        create_product(test_db, code="FUND_SC3", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        ensure_trading_day(test_db, date(2025, 12, 8), is_open=True)

        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "SCE_P3",
                "product_code": "FUND_SC3",
                "market": "CN_OTC",
                "event_type": "share_split",
                "ex_date": "2025-12-10",
                "entitlement_date": "2025-12-08",
                "event_source": "manual",
                "ratio": 2.0,
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)

    def test_entitlement_date_non_trading_day_rejected(self, client, admin_headers, test_db):
        """权益登记日非交易日应被拒绝"""
        create_portfolio(test_db, code="SCE_NTD", status="active")
        create_product(test_db, code="FUND_NT", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        ensure_trading_day(test_db, date(2025, 12, 6), is_open=False)  # 周六

        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "SCE_NTD",
                "product_code": "FUND_NT",
                "market": "CN_OTC",
                "event_type": "cash_dividend",
                "ex_date": "2025-12-10",
                "entitlement_date": "2025-12-06",
                "event_source": "manual",
                "div_cash": 0.5,
            },
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)


class TestShareChangeEventList:
    """份额变动事件列表测试"""

    def test_list_events(self, client, admin_headers, test_db):
        """获取事件列表"""
        resp = client.get("/api/share-change-events", headers=admin_headers)
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_viewer_cannot_create_event(self, client, viewer_headers):
        """viewer 不能创建份额变动事件"""
        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "X",
                "product_code": "X",
                "market": "CN_OTC",
                "event_type": "cash_dividend",
                "ex_date": "2025-12-10",
                "entitlement_date": "2025-12-08",
                "event_source": "manual",
            },
            headers=viewer_headers,
        )
        assert resp.status_code == 403


class TestShareChangeEventCancel:
    """份额变动事件取消测试"""

    def test_cancel_pending_event(self, client, admin_headers, test_db):
        """取消 pending 事件"""
        create_portfolio(test_db, code="SCE_CAN", status="active")
        create_product(test_db, code="FUND_CAN", market="CN_OTC",
                       product_type="OEF", asset_class_code="STOCK_CN_LARGE")
        event = create_share_change_event(
            test_db, "SCE_CAN", "FUND_CAN", "CN_OTC",
            status="pending",
        )
        resp = client.post(
            f"/api/share-change-events/{event.id}/cancel",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        updated = test_db.query(ShareChangeEvent).filter(
            ShareChangeEvent.id == event.id
        ).first()
        assert updated.status == "cancelled"
