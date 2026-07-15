# ============================================================================
# 单元测试：交易日校验 (test_trading_calendar.py)
# ============================================================================
# 测试交易日判断逻辑，覆盖路由层和服务层的交易日校验。
# ============================================================================

import pytest
from datetime import date

from app.models.trading_calendar import TradingCalendar
from tests.factories import ensure_trading_day


class TestTradingCalendarModel:
    """交易日历模型测试"""

    def test_create_trading_day(self, test_db):
        """创建交易日记录"""
        cal = ensure_trading_day(test_db, date(2025, 6, 2), is_open=True)
        assert cal.is_open is True
        assert cal.exchange == "SSE"

    def test_create_non_trading_day(self, test_db):
        """创建非交易日记录"""
        cal = ensure_trading_day(test_db, date(2025, 6, 1), is_open=False)
        assert cal.is_open is False

    def test_query_trading_day(self, test_db):
        """查询交易日应返回记录"""
        ensure_trading_day(test_db, date(2025, 7, 7), is_open=True)
        result = test_db.query(TradingCalendar).filter(
            TradingCalendar.date == date(2025, 7, 7)
        ).first()
        assert result is not None
        assert result.is_open is True

    def test_query_nonexistent_date(self, test_db):
        """查询不存在的日期应返回 None"""
        result = test_db.query(TradingCalendar).filter(
            TradingCalendar.date == date(2099, 1, 1)
        ).first()
        assert result is None


class TestTradingDayValidationInRouter:
    """路由层交易日校验测试（通过 API 间接测试）"""

    def test_subscription_on_non_trading_day_rejected(self, client, admin_headers, test_db):
        """非交易日提交申购应被拒绝"""
        # 确保目标日期为非交易日
        ensure_trading_day(test_db, date(2025, 8, 2), is_open=False)  # 周六

        from tests.factories import create_portfolio, create_investor
        create_portfolio(test_db, code="NTD_PORT", status="active")
        create_investor(test_db, code="NTD_INV")

        response = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "NTD_PORT",
                "investor_code": "NTD_INV",
                "sub_type": "subscribe",
                "amount": 10000.0,
                "apply_date": "2025-08-02",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        # 期望 422 NON_TRADING_DAY 或 400 错误
        assert response.status_code in (400, 422)

    def test_subscription_on_trading_day_accepted(self, client, admin_headers, test_db):
        """交易日提交申购应被接受（创建 pending 记录）"""
        ensure_trading_day(test_db, date(2025, 8, 4), is_open=True)  # 周一

        from tests.factories import create_portfolio, create_investor
        create_portfolio(test_db, code="TD_PORT", status="active")
        create_investor(test_db, code="TD_INV")

        response = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "TD_PORT",
                "investor_code": "TD_INV",
                "sub_type": "subscribe",
                "amount": 10000.0,
                "apply_date": "2025-08-04",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        # 应成功创建（200 或 201）
        assert response.status_code in (200, 201)
