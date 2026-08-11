# ============================================================================
# 集成测试：份额精度统一 2 位小数 (test_shares_precision.py)
# ============================================================================
# 覆盖份额精度全局改 2 位小数（ROUND_HALF_UP 四舍五入，issue #87）后的核心场景：
# - 申购确认后 subscription.shares 为 2 位小数（非整除净值）
# - 场外基金买入确认后 trade.shares 为 2 位小数
# - 回归：按 2 位可用份额全额卖出/全额赎回不再被 INSUFFICIENT_SHARES 拒绝
# - 4 位输入份额先量化到 2 位再精确校验（量化后在可用内通过、超出仍拒）
# ============================================================================

import pytest
from datetime import date
from decimal import Decimal

from tests.factories import (
    create_portfolio, create_investor, create_subscription,
    create_investor_holding, create_value_snapshot, ensure_trading_day,
    create_product, create_platform, create_trade, create_position_snapshot,
    create_price_record,
)
from app.models.subscription import Subscription
from app.models.trade import Trade


class TestSubscriptionConfirmSharesPrecision:
    """申购确认份额量化到 2 位（ROUND_HALF_UP）"""

    def test_confirm_subscribe_shares_two_decimals(self, client, admin_headers, test_db):
        """非整除净值（0.9757）申购确认后份额为 2 位小数：3000/0.9757 → 3074.72"""
        create_portfolio(test_db, code="PREC_SP", status="active")
        create_investor(test_db, code="PREC_SI")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)

        # 已有 confirmed 申购 → 本笔非首次，净值取申请日快照 unit_price
        create_subscription(
            test_db, "PREC_SP", "PREC_SI",
            sub_type="subscribe", amount=10000.0, shares=10000.0,
            unit_price=1.0, apply_date=date(2025, 8, 1),
            confirm_date=date(2025, 8, 4), status="confirmed",
        )
        create_value_snapshot(test_db, "PREC_SP", date(2025, 9, 1),
                              total_value=9757, total_shares=10000, unit_price=0.9757)
        sub = create_subscription(
            test_db, "PREC_SP", "PREC_SI",
            sub_type="subscribe", amount=3000.0,
            apply_date=date(2025, 9, 1), status="pending",
        )

        resp = client.post(f"/api/subscriptions/{sub.id}/confirm", headers=admin_headers)
        assert resp.status_code == 200, f"Response: {resp.status_code} {resp.json()}"

        test_db.expire_all()
        confirmed = test_db.query(Subscription).filter(Subscription.id == sub.id).first()
        # issue #87 实例：3000 / 0.9757 = 3074.715588...，HALF_UP → 3074.72（DOWN 为 3074.71）
        assert Decimal(str(confirmed.shares)) == Decimal("3074.72")
        assert Decimal(str(confirmed.unit_price)) == Decimal("0.9757")


class TestOtcBuyConfirmSharesPrecision:
    """场外基金买入确认份额量化到 2 位（ROUND_HALF_UP）"""

    def test_confirm_otc_buy_shares_two_decimals(self, client, admin_headers, test_db):
        """场外基金买入确认按 T 日净值重算份额：3000/0.9757 → 3074.72"""
        create_portfolio(test_db, code="PREC_TP", status="active")
        create_product(test_db, code="FUND_PREC", market="CN_OTC",
                       product_type="OEF", confirm_days=1, is_qdii=False)
        create_platform(test_db, code="PREC_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 10, 7), is_open=True)
        # 提供可用现金
        create_trade(
            test_db, "PREC_TP", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="PREC_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        # T 日净值（非整除）
        create_price_record(test_db, "FUND_PREC", "CN_OTC",
                            date(2025, 10, 6), unit_price=0.9757)

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "PREC_TP",
                "product_code": "FUND_PREC",
                "market": "CN_OTC",
                "trade_type": "buy",
                "amount": 3000.0,
                "platform_code": "PREC_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        trade_id = resp.json()["id"]

        confirm = client.post(f"/api/trades/{trade_id}/confirm", headers=admin_headers)
        assert confirm.status_code == 200, f"Response: {confirm.status_code} {confirm.json()}"

        test_db.expire_all()
        trade = test_db.query(Trade).filter(Trade.id == trade_id).first()
        # issue #87 实例：3000 / 0.9757 = 3074.715588...，HALF_UP → 3074.72（DOWN 为 3074.71）
        assert Decimal(str(trade.shares)) == Decimal("3074.72")


class TestFullSellRedeemRegression:
    """回归：持仓份额为 2 位后，全额卖出/全额赎回不被 INSUFFICIENT_SHARES 拒绝"""

    def test_full_sell_all_available_shares(self, client, admin_headers, test_db):
        """按可用份额（6837.29）全额卖出应成功"""
        create_portfolio(test_db, code="PREC_FS", status="active")
        create_product(test_db, code="ETF_PREC1", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="PREC_FSPLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        create_position_snapshot(
            test_db, "PREC_FS", "ETF_PREC1", "CN_EXCHANGE",
            snapshot_date=date(2025, 10, 3),
            shares=6837.29, unit_price=1.5, cost_price=1.5,
            market_value=10255.94, platform_code="PREC_FSPLAT",
        )

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "PREC_FS",
                "product_code": "ETF_PREC1",
                "market": "CN_EXCHANGE",
                "trade_type": "sell",
                "shares": 6837.29,
                "price": 1.6,
                "platform_code": "PREC_FSPLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        trade = test_db.query(Trade).filter(Trade.id == resp.json()["id"]).first()
        assert Decimal(str(trade.shares)) == Decimal("6837.29")

    def test_full_redeem_all_available_shares(self, client, admin_headers, test_db):
        """按可用份额（6837.29）全额赎回应成功"""
        create_portfolio(test_db, code="PREC_FR", status="active")
        create_investor(test_db, code="PREC_FRI")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)

        create_value_snapshot(test_db, "PREC_FR", date(2025, 8, 29),
                              total_value=6837.29, total_shares=6837.29, unit_price=1.0)
        create_investor_holding(test_db, "PREC_FR", "PREC_FRI",
                                date(2025, 8, 29), shares=6837.29)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "PREC_FR",
                "investor_code": "PREC_FRI",
                "sub_type": "redeem",
                "shares": 6837.29,
                "apply_date": "2025-09-01",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        sub = test_db.query(Subscription).filter(Subscription.id == resp.json()["id"]).first()
        assert Decimal(str(sub.shares)) == Decimal("6837.29")


class TestFourDecimalInputQuantization:
    """4 位输入份额先量化到 2 位再精确校验"""

    def test_sell_four_decimal_input_quantized_and_accepted(self, client, admin_headers, test_db):
        """可用 6837.29，输入 6837.2949 → 量化为 6837.29 后通过校验"""
        create_portfolio(test_db, code="PREC_Q1", status="active")
        create_product(test_db, code="ETF_PREC2", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="PREC_QPLAT1")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        create_position_snapshot(
            test_db, "PREC_Q1", "ETF_PREC2", "CN_EXCHANGE",
            snapshot_date=date(2025, 10, 3),
            shares=6837.29, unit_price=1.5, cost_price=1.5,
            market_value=10255.94, platform_code="PREC_QPLAT1",
        )

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "PREC_Q1",
                "product_code": "ETF_PREC2",
                "market": "CN_EXCHANGE",
                "trade_type": "sell",
                "shares": 6837.2949,
                "price": 1.6,
                "platform_code": "PREC_QPLAT1",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        # 落库份额已量化到 2 位
        trade = test_db.query(Trade).filter(Trade.id == resp.json()["id"]).first()
        assert Decimal(str(trade.shares)) == Decimal("6837.29")

    def test_sell_quantized_input_exceeding_available_rejected(self, client, admin_headers, test_db):
        """可用 6837.29，输入 6837.31（量化后仍超出）应被 INSUFFICIENT_SHARES 拒绝"""
        create_portfolio(test_db, code="PREC_Q2", status="active")
        create_product(test_db, code="ETF_PREC3", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="PREC_QPLAT2")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        create_position_snapshot(
            test_db, "PREC_Q2", "ETF_PREC3", "CN_EXCHANGE",
            snapshot_date=date(2025, 10, 3),
            shares=6837.29, unit_price=1.5, cost_price=1.5,
            market_value=10255.94, platform_code="PREC_QPLAT2",
        )

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "PREC_Q2",
                "product_code": "ETF_PREC3",
                "market": "CN_EXCHANGE",
                "trade_type": "sell",
                "shares": 6837.31,
                "price": 1.6,
                "platform_code": "PREC_QPLAT2",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_SHARES"

    def test_redeem_four_decimal_input_quantized_and_accepted(self, client, admin_headers, test_db):
        """赎回：可用 6837.29，输入 6837.2949 → 量化为 6837.29 后通过校验"""
        create_portfolio(test_db, code="PREC_Q3", status="active")
        create_investor(test_db, code="PREC_Q3I")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)

        create_value_snapshot(test_db, "PREC_Q3", date(2025, 8, 29),
                              total_value=6837.29, total_shares=6837.29, unit_price=1.0)
        create_investor_holding(test_db, "PREC_Q3", "PREC_Q3I",
                                date(2025, 8, 29), shares=6837.29)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "PREC_Q3",
                "investor_code": "PREC_Q3I",
                "sub_type": "redeem",
                "shares": 6837.2949,
                "apply_date": "2025-09-01",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        sub = test_db.query(Subscription).filter(Subscription.id == resp.json()["id"]).first()
        assert Decimal(str(sub.shares)) == Decimal("6837.29")

    def test_redeem_quantized_input_exceeding_available_rejected(self, client, admin_headers, test_db):
        """赎回：可用 6837.29，输入 6837.31（量化后仍超出）应被 INSUFFICIENT_SHARES 拒绝"""
        create_portfolio(test_db, code="PREC_Q4", status="active")
        create_investor(test_db, code="PREC_Q4I")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)

        create_value_snapshot(test_db, "PREC_Q4", date(2025, 8, 29),
                              total_value=6837.29, total_shares=6837.29, unit_price=1.0)
        create_investor_holding(test_db, "PREC_Q4", "PREC_Q4I",
                                date(2025, 8, 29), shares=6837.29)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "PREC_Q4",
                "investor_code": "PREC_Q4I",
                "sub_type": "redeem",
                "shares": 6837.31,
                "apply_date": "2025-09-01",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_SHARES"
