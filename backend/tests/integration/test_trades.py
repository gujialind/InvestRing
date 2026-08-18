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
from app.schemas.trade import TradeResponse


class TestBuyTrade:
    """买入交易测试"""

    def test_create_buy_trade_pending(self, client, admin_headers, test_db):
        """买入交易创建后应为 pending"""
        create_portfolio(test_db, code="TRD_P1", status="active")
        create_product(test_db, code="ETF01", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK")
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
                       product_type="ETF", asset_class_code="ASSET_STOCK")
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
                       product_type="ETF", asset_class_code="ASSET_STOCK")
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

    def test_buy_succeeds_with_manual_override(self, client, admin_headers, test_db):
        """manual 覆盖 baked in 快照后，买入金额在覆盖值内应成功（回归 issue #52）"""
        create_portfolio(test_db, code="TRD_OVR", status="active")
        create_product(test_db, code="ETF_OVR", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="TRD_OVR_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        # 快照日 + 持仓快照（模拟快照生成时已 bake in manual 覆盖值 6001.39）
        create_value_snapshot(test_db, "TRD_OVR", date(2025, 10, 3),
                              total_value=6001.39, total_shares=6001.39, unit_price=1.0)
        create_position_snapshot(
            test_db, "TRD_OVR", "CASH", "",
            snapshot_date=date(2025, 10, 3),
            cash_amount=6001.39, unit_price=None, cost_price=None,
            market_value=6001.39, platform_code="TRD_OVR_PLAT",
        )

        # 买入 6001（< 快照基线 6001.39）→ 应成功
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "TRD_OVR",
                "product_code": "ETF_OVR",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 6001.0,
                "price": 1.5,
                "platform_code": "TRD_OVR_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"


class TestSellTrade:
    """卖出交易测试"""

    def test_create_sell_trade_pending(self, client, admin_headers, test_db):
        """卖出交易创建后应为 pending"""
        create_portfolio(test_db, code="SEL_P1", status="active")
        create_product(test_db, code="ETF04", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK")
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
                       product_type="ETF", asset_class_code="ASSET_STOCK")
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


class TestNonQDIIrigorousNav:
    """#24 非QDII净值严格 T 日：禁止向前查找"""

    def test_confirm_oef_missing_t_nav_rejected(self, client, admin_headers, test_db):
        """场外基金确认时，T 日净值缺失应拒绝（不再向前回溯）"""
        create_portfolio(test_db, code="NAV_P1", status="active")
        create_product(test_db, code="FUND_NAV1", market="CN_OTC",
                       product_type="OEF", confirm_days=1, is_qdii=False)
        create_platform(test_db, code="NAV_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 10, 7), is_open=True)
        # 提供现金
        create_trade(
            test_db, "NAV_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="NAV_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        # 仅写入 T-1 净值，T 日缺失
        create_price_record(test_db, "FUND_NAV1", "CN_OTC",
                            date(2025, 10, 3), unit_price=1.2)

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "NAV_P1",
                "product_code": "FUND_NAV1",
                "market": "CN_OTC",
                "trade_type": "buy",
                "amount": 10000.0,
                "platform_code": "NAV_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        trade_id = resp.json()["id"]

        confirm = client.post(f"/api/trades/{trade_id}/confirm", headers=admin_headers)
        assert confirm.status_code == 422
        assert confirm.json()["detail"]["error"] == "MISSING_NAV"


class TestUnconfirmTradeSnapshotProtection:
    """#25 unconfirm_trade 快照保护"""

    def test_unconfirm_blocked_by_snapshot(self, client, admin_headers, test_db):
        """confirm_date 及之后已有快照时，unconfirm 返回 SNAPSHOT_DEPENDENCY"""
        create_portfolio(test_db, code="UC_P1", status="active")
        create_product(test_db, code="ETF_UC", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK",
                       confirm_days=0)
        create_platform(test_db, code="UC_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        create_trade(
            test_db, "UC_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="UC_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        # 创建并确认一笔场内 ETF 买入（当天确认）
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "UC_P1",
                "product_code": "ETF_UC",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "UC_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        trade_id = resp.json()["id"]
        conf = client.post(f"/api/trades/{trade_id}/confirm", headers=admin_headers)
        assert conf.status_code == 200
        confirmed_trade = conf.json()["trade"]
        # 在 confirm_date 上生成快照
        create_value_snapshot(
            test_db, "UC_P1", date(2025, 10, 6),
            total_value=60000, total_shares=60000, unit_price=1.0,
        )

        unconf = client.post(f"/api/trades/{trade_id}/unconfirm", headers=admin_headers)
        assert unconf.status_code == 422
        assert unconf.json()["detail"]["error"] == "SNAPSHOT_DEPENDENCY"

    def test_unconfirm_ok_without_snapshot(self, client, admin_headers, test_db):
        """无快照依赖时，unconfirm 成功且配对 CASH 腿同步回 pending"""
        create_portfolio(test_db, code="UC_P2", status="active")
        create_product(test_db, code="ETF_UC2", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK",
                       confirm_days=0)
        create_platform(test_db, code="UC_PLAT2")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        create_trade(
            test_db, "UC_P2", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="UC_PLAT2", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "UC_P2",
                "product_code": "ETF_UC2",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "UC_PLAT2",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        trade_id = resp.json()["id"]
        conf = client.post(f"/api/trades/{trade_id}/confirm", headers=admin_headers)
        assert conf.status_code == 200

        unconf = client.post(f"/api/trades/{trade_id}/unconfirm", headers=admin_headers)
        assert unconf.status_code == 200
        # 验证主腿与配对 CASH 腿均回 pending（按 transfer_group 过滤，排除预置现金腿）
        fund_leg = test_db.query(Trade).get(trade_id)
        tg = fund_leg.transfer_group
        paired = test_db.query(Trade).filter(
            Trade.transfer_group == tg, Trade.id != trade_id
        ).first()
        assert fund_leg.status == "pending"
        assert paired.status == "pending"


class TestUpdateDeletePairedSync:
    """#26 PUT/DELETE 配对 CASH 腿同步"""

    def test_update_trade_date_syncs_cash_leg(self, client, admin_headers, test_db):
        """update 改动 trade_date 时 confirm_date 联动重算，并同步配对 CASH 腿"""
        create_portfolio(test_db, code="UPD_P1", status="active")
        create_product(test_db, code="ETF_UPD", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK",
                       confirm_days=0)
        create_platform(test_db, code="UPD_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 10, 8), is_open=True)
        create_trade(
            test_db, "UPD_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="UPD_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "UPD_P1",
                "product_code": "ETF_UPD",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "UPD_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        trade_id = resp.json()["id"]
        fund_leg = test_db.query(Trade).get(trade_id)
        tg = fund_leg.transfer_group
        cash_leg = test_db.query(Trade).filter(
            Trade.transfer_group == tg, Trade.id != trade_id
        ).first()
        # #93: CASH sell 腿独立确认日 = trade_date（T日扣款），不依赖基金腿
        assert cash_leg.confirm_date == date(2025, 10, 6)

        # confirm_date 不开放直改：额外字段被 schema 忽略，不产生变更
        upd = client.put(
            f"/api/trades/{trade_id}",
            json={"confirm_date": "2025-10-08", "notes": "try direct set"},
            headers=admin_headers,
        )
        assert upd.status_code == 200
        test_db.expire_all()
        fund_leg = test_db.query(Trade).get(trade_id)
        assert fund_leg.confirm_date == date(2025, 10, 6)

        # 改 trade_date → 基金腿按 confirm_days 联动重算；CASH sell 腿独立取 trade_date（#93）
        upd = client.put(
            f"/api/trades/{trade_id}",
            json={"trade_date": "2025-10-08"},
            headers=admin_headers,
        )
        assert upd.status_code == 200
        test_db.expire_all()
        fund_leg = test_db.query(Trade).get(trade_id)
        assert fund_leg.confirm_date == date(2025, 10, 8)
        cash_leg = test_db.query(Trade).filter(
            Trade.transfer_group == tg, Trade.id != trade_id
        ).first()
        # #93: CASH sell 腿独立确认日 = 新 trade_date
        assert cash_leg.confirm_date == date(2025, 10, 8)
        # CASH 腿 trade_date 随基金腿同步（组内不变量）
        assert cash_leg.trade_date == date(2025, 10, 8)

        # #93: confirm → unconfirm 后各腿独立回退默认确认日
        # CASH sell 腿回退到 trade_date（T日扣款），基金腿按 confirm_days 重算
        conf = client.post(f"/api/trades/{trade_id}/confirm", headers=admin_headers)
        assert conf.status_code == 200
        unconf = client.post(f"/api/trades/{trade_id}/unconfirm", headers=admin_headers)
        assert unconf.status_code == 200
        test_db.expire_all()
        fund_leg = test_db.query(Trade).get(trade_id)
        cash_leg = test_db.query(Trade).filter(
            Trade.transfer_group == tg, Trade.id != trade_id
        ).first()
        assert fund_leg.status == "pending" and cash_leg.status == "pending"
        assert cash_leg.trade_date == date(2025, 10, 8)
        # #93: CASH sell 腿独立确认日 = trade_date，基金腿独立按 confirm_days 重算
        # 此处 confirm_days=0 所以两值相等，但语义独立（不再互相同步）
        assert cash_leg.confirm_date == date(2025, 10, 8)  # = trade_date（T日扣款）
        assert fund_leg.confirm_date == date(2025, 10, 8)  # = T+0（confirm_days=0）

    def test_update_trade_status_field_ignored(self, client, admin_headers, test_db):
        """PUT 传 status 被忽略（状态流转只走 confirm/cancel/unconfirm 端点）"""
        create_portfolio(test_db, code="UPD_P2", status="active")
        create_product(test_db, code="ETF_UPD2", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK",
                       confirm_days=0)
        create_platform(test_db, code="UPD_PLAT2")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        create_trade(
            test_db, "UPD_P2", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="UPD_PLAT2", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "UPD_P2",
                "product_code": "ETF_UPD2",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "UPD_PLAT2",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        trade_id = resp.json()["id"]

        upd = client.put(
            f"/api/trades/{trade_id}",
            json={"status": "confirmed"},
            headers=admin_headers,
        )
        assert upd.status_code == 200
        test_db.expire_all()
        fund_leg = test_db.query(Trade).get(trade_id)
        cash_leg = test_db.query(Trade).filter(
            Trade.transfer_group == fund_leg.transfer_group,
            Trade.id != trade_id,
        ).first()
        # status 字段被 schema 忽略，两腿均保持 pending
        assert fund_leg.status == "pending"
        assert cash_leg.status == "pending"

    def test_delete_trade_cascades_cash_leg(self, client, admin_headers, test_db):
        """delete 主腿时级联删除配对 CASH 腿"""
        create_portfolio(test_db, code="DEL_P1", status="active")
        create_product(test_db, code="ETF_DEL", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK",
                       confirm_days=0)
        create_platform(test_db, code="DEL_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        create_trade(
            test_db, "DEL_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="DEL_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "DEL_P1",
                "product_code": "ETF_DEL",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "DEL_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        trade_id = resp.json()["id"]
        fund_leg = test_db.query(Trade).get(trade_id)
        tg = fund_leg.transfer_group
        before = test_db.query(Trade).filter(Trade.transfer_group == tg).count()
        assert before == 2

        dele = client.delete(f"/api/trades/{trade_id}", headers=admin_headers)
        assert dele.status_code == 200
        test_db.expire_all()
        after = test_db.query(Trade).filter(Trade.transfer_group == tg).count()
        assert after == 0


class TestUpdateAmountSyncCashLeg:
    """#46 PUT 改金额后配对 CASH 腿同步"""

    def test_update_actual_amount_syncs_cash_leg(self, client, admin_headers, test_db):
        """修改基金腿 actual_amount 后，配对 CASH 腿 amount 同步更新"""
        create_portfolio(test_db, code="AMT_P1", status="active")
        create_product(test_db, code="ETF_AMT", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK",
                       confirm_days=0)
        create_platform(test_db, code="AMT_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        create_trade(
            test_db, "AMT_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="AMT_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        # 创建基金买入（自动生成配对 CASH 腿）
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "AMT_P1",
                "product_code": "ETF_AMT",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "AMT_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        trade_id = resp.json()["id"]
        fund_leg = test_db.query(Trade).get(trade_id)
        tg = fund_leg.transfer_group
        paired = test_db.query(Trade).filter(
            Trade.transfer_group == tg, Trade.id != trade_id
        ).first()
        assert paired is not None
        original_paired_amount = float(paired.amount)

        # PUT 修改 actual_amount
        upd = client.put(
            f"/api/trades/{trade_id}",
            json={"actual_amount": 8000.0},
            headers=admin_headers,
        )
        assert upd.status_code == 200
        test_db.expire_all()
        paired_after = test_db.query(Trade).filter(
            Trade.transfer_group == tg, Trade.id != trade_id
        ).first()
        # 配对 CASH 腿金额应同步为新的 actual_amount
        assert float(paired_after.amount) == 8000.0
        assert float(paired_after.actual_amount) == 8000.0
        assert float(paired_after.amount) != original_paired_amount


class TestAsOfDateSellValidation:
    """#47 补录历史卖出时 as_of_date 排除后续 confirmed"""

    def test_backfill_sell_not_blocked_by_later_confirmed(self, client, admin_headers, test_db):
        """补录历史日卖出，后续 confirmed 卖出不应计入扣减"""
        create_portfolio(test_db, code="ASOF_P1", status="active")
        create_product(test_db, code="FUND_ASOF", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK",
                       confirm_days=1)
        create_platform(test_db, code="ASOF_PLAT")
        ensure_trading_day(test_db, date(2025, 1, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 1, 7), is_open=True)
        ensure_trading_day(test_db, date(2025, 1, 8), is_open=True)
        ensure_trading_day(test_db, date(2025, 1, 9), is_open=True)
        ensure_trading_day(test_db, date(2025, 1, 10), is_open=True)
        # 快照：shares=1000
        create_value_snapshot(test_db, "ASOF_P1", date(2025, 1, 6),
                              total_value=1000, total_shares=1000, unit_price=1.0)
        create_position_snapshot(
            test_db, "ASOF_P1", "FUND_ASOF", "CN_OTC", date(2025, 1, 6),
            shares=1000, platform_code="ASOF_PLAT",
        )
        # 后续 confirmed 卖出 800（confirm_date=1/9，快照后）
        create_trade(
            test_db, "ASOF_P1", "FUND_ASOF", "CN_OTC",
            trade_type="sell", shares=800, status="confirmed",
            trade_date=date(2025, 1, 8), confirm_date=date(2025, 1, 9),
            platform_code="ASOF_PLAT",
        )
        # 补录 1/7 卖出 500：as_of=1/7 时后续 1/9 confirmed 不计入，可用=1000
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "ASOF_P1",
                "product_code": "FUND_ASOF",
                "market": "CN_OTC",
                "trade_type": "sell",
                "shares": 500,
                "price": 1.0,
                "platform_code": "ASOF_PLAT",
                "trade_date": "2025-01-07",
            },
            headers=admin_headers,
        )
        # 不应被 INSUFFICIENT_SHARES 拒绝
        assert resp.status_code in (200, 201), f"Expected success, got {resp.status_code}: {resp.json()}"


class TestCancelExchangeErrorMessage:
    """#49 场内 cancel 错误信息包含修正路径"""

    def test_cancel_exchange_message_has_correction_path(self, client, admin_headers, test_db):
        """场内交易 cancel 拒绝时 message 包含 PUT 和 DELETE 关键词"""
        create_portfolio(test_db, code="MSG_P1", status="active")
        create_product(test_db, code="ETF_MSG", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK",
                       confirm_days=0)
        create_platform(test_db, code="MSG_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        create_trade(
            test_db, "MSG_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="MSG_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        # 创建场内 pending trade（手动插入，因为场内创建后一般当天确认）
        from decimal import Decimal
        t = Trade(
            portfolio_code="MSG_P1", product_code="ETF_MSG", market="CN_EXCHANGE",
            platform_code="MSG_PLAT", trade_type="buy",
            amount=Decimal("5000"), price=Decimal("1.5"),
            fee=Decimal("0"), actual_amount=Decimal("5000"),
            trade_date=date(2025, 10, 6), status="pending",
            transfer_group="rebal_msgtest001",
        )
        test_db.add(t)
        test_db.commit()
        test_db.refresh(t)

        resp = client.post(f"/api/trades/{t.id}/cancel", headers=admin_headers)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "CANNOT_CANCEL_EXCHANGE"
        assert "PUT" in detail["message"]
        assert "DELETE" in detail["message"]


class TestCashTradeForbidden:
    """#53 禁止直接创建裸 CASH 交易"""

    def test_create_cash_trade_rejected(self, client, admin_headers, test_db):
        """REST POST /api/trades 传 product_code=CASH 应被 422 CASH_TRADE_FORBIDDEN 拒绝"""
        create_portfolio(test_db, code="CASH_FBD", status="active")
        create_platform(test_db, code="CASH_FBD_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "CASH_FBD",
                "product_code": "CASH",
                "market": "",
                "trade_type": "buy",
                "amount": 10000.0,
                "platform_code": "CASH_FBD_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422, f"Response: {resp.status_code} {resp.json()}"
        assert resp.json()["detail"]["error"] == "CASH_TRADE_FORBIDDEN"

    def test_create_fund_buy_generates_paired_cash_leg(self, client, admin_headers, test_db):
        """REST 基金买入自动生成共享 transfer_group 的配对 CASH 腿"""
        create_portfolio(test_db, code="PAIR_P1", status="active")
        create_product(test_db, code="ETF_PAIR", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="ASSET_STOCK",
                       confirm_days=0)
        create_platform(test_db, code="PAIR_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        create_trade(
            test_db, "PAIR_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="PAIR_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "PAIR_P1",
                "product_code": "ETF_PAIR",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "PAIR_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        fund_id = resp.json()["id"]
        fund_leg = test_db.query(Trade).get(fund_id)
        assert fund_leg.transfer_group is not None
        assert fund_leg.transfer_group.startswith("rebal_")
        paired = test_db.query(Trade).filter(
            Trade.transfer_group == fund_leg.transfer_group,
            Trade.id != fund_id,
        ).all()
        assert len(paired) == 1
        assert paired[0].product_code == "CASH"
        assert paired[0].trade_type == "sell"
        assert float(paired[0].amount) == 10000.0


class TestTradePreview:
    """#65 确认前预览：GET /api/trades/{id}/preview 与真实 confirm 完全一致"""

    def _setup_base(self, test_db, *, portfolio, product, platform,
                    confirm_days=1, is_qdii=False, nav=None):
        """创建组合/产品/平台/交易日/可用现金，可选写入 T 日净值"""
        create_portfolio(test_db, code=portfolio, status="active")
        create_product(test_db, code=product, market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK",
                       confirm_days=confirm_days, is_qdii=is_qdii)
        create_platform(test_db, code=platform)
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 10, 7), is_open=True)
        ensure_trading_day(test_db, date(2025, 10, 8), is_open=True)
        create_trade(
            test_db, portfolio, "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code=platform, trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )
        if nav is not None:
            create_price_record(test_db, product, "CN_OTC", date(2025, 10, 6), unit_price=nav)

    def _create_otc_buy(self, client, admin_headers, *, portfolio, product, platform,
                        amount=10000.0, fee=0.0):
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": portfolio,
                "product_code": product,
                "market": "CN_OTC",
                "trade_type": "buy",
                "amount": amount,
                "fee": fee,
                "platform_code": platform,
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        return resp.json()["id"]

    def test_preview_matches_confirm_otc_buy(self, client, admin_headers, test_db):
        """场外 OEF 买入：preview 各字段与 confirm 后 trade 逐一相等，CASH 腿金额 == paired_cash_amount"""
        self._setup_base(test_db, portfolio="PRV_B1", product="FUND_PRV1",
                         platform="PRV_PLAT1", nav=1.25)
        trade_id = self._create_otc_buy(
            client, admin_headers,
            portfolio="PRV_B1", product="FUND_PRV1", platform="PRV_PLAT1",
        )

        prev = client.get(f"/api/trades/{trade_id}/preview", headers=admin_headers)
        assert prev.status_code == 200, f"Response: {prev.status_code} {prev.json()}"
        data = prev.json()
        preview = data["preview"]
        assert preview["is_otc_nav_fund"] is True
        assert preview["nav_date"] == "2025-10-06"

        conf = client.post(f"/api/trades/{trade_id}/confirm", headers=admin_headers)
        assert conf.status_code == 200, f"Response: {conf.status_code} {conf.json()}"
        confirmed = conf.json()["trade"]

        # preview 与真实确认逐字段一致
        assert float(preview["price"]) == float(confirmed["price"])
        assert float(preview["shares"]) == float(confirmed["shares"])
        assert float(preview["amount"]) == float(confirmed["amount"])
        assert float(preview["actual_amount"]) == float(confirmed["actual_amount"])
        assert preview["confirm_date"] == confirmed["confirm_date"]

        # 配对 CASH 腿金额 == paired_cash_amount
        test_db.expire_all()
        fund_leg = test_db.query(Trade).get(trade_id)
        paired = test_db.query(Trade).filter(
            Trade.transfer_group == fund_leg.transfer_group,
            Trade.id != trade_id,
        ).first()
        assert float(paired.amount) == float(data["paired_cash_amount"])

    def test_preview_matches_confirm_otc_sell(self, client, admin_headers, test_db):
        """场外 OEF 卖出：preview 与 confirm 结果一致"""
        self._setup_base(test_db, portfolio="PRV_S1", product="FUND_PRV2",
                         platform="PRV_PLAT2", nav=1.25)
        # 先有持仓可卖
        create_position_snapshot(
            test_db, "PRV_S1", "FUND_PRV2", "CN_OTC",
            snapshot_date=date(2025, 10, 3),
            shares=1000.0, unit_price=1.2, cost_price=1.2,
            market_value=1200.0, platform_code="PRV_PLAT2",
        )
        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "PRV_S1",
                "product_code": "FUND_PRV2",
                "market": "CN_OTC",
                "trade_type": "sell",
                "shares": 400.0,
                "platform_code": "PRV_PLAT2",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"
        trade_id = resp.json()["id"]

        prev = client.get(f"/api/trades/{trade_id}/preview", headers=admin_headers)
        assert prev.status_code == 200, f"Response: {prev.status_code} {prev.json()}"
        data = prev.json()
        preview = data["preview"]
        # 卖出：amount = 400 × 1.25 = 500，actual = 500 - 0
        assert float(preview["amount"]) == 500.0
        assert float(preview["actual_amount"]) == 500.0

        conf = client.post(f"/api/trades/{trade_id}/confirm", headers=admin_headers)
        assert conf.status_code == 200, f"Response: {conf.status_code} {conf.json()}"
        confirmed = conf.json()["trade"]
        assert float(preview["price"]) == float(confirmed["price"])
        assert float(preview["shares"]) == float(confirmed["shares"])
        assert float(preview["amount"]) == float(confirmed["amount"])
        assert float(preview["actual_amount"]) == float(confirmed["actual_amount"])
        assert preview["confirm_date"] == confirmed["confirm_date"]

        test_db.expire_all()
        fund_leg = test_db.query(Trade).get(trade_id)
        paired = test_db.query(Trade).filter(
            Trade.transfer_group == fund_leg.transfer_group,
            Trade.id != trade_id,
        ).first()
        assert float(paired.amount) == float(data["paired_cash_amount"])

    def test_preview_qdii_confirm_date_consistent(self, client, admin_headers, test_db):
        """QDII（confirm_days=2）：preview 的 confirm_date 与 confirm 后一致（T+2）"""
        self._setup_base(test_db, portfolio="PRV_Q1", product="FUND_PRVQ",
                         platform="PRV_PLATQ", confirm_days=2, is_qdii=True, nav=1.25)
        trade_id = self._create_otc_buy(
            client, admin_headers,
            portfolio="PRV_Q1", product="FUND_PRVQ", platform="PRV_PLATQ",
        )

        prev = client.get(f"/api/trades/{trade_id}/preview", headers=admin_headers)
        assert prev.status_code == 200, f"Response: {prev.status_code} {prev.json()}"
        preview = prev.json()["preview"]
        assert preview["confirm_date"] == "2025-10-08"

        conf = client.post(f"/api/trades/{trade_id}/confirm", headers=admin_headers)
        assert conf.status_code == 200, f"Response: {conf.status_code} {conf.json()}"
        assert preview["confirm_date"] == conf.json()["trade"]["confirm_date"]

    def test_preview_missing_nav_rejected(self, client, admin_headers, test_db):
        """T 日净值缺失：preview 返回 422 MISSING_NAV"""
        self._setup_base(test_db, portfolio="PRV_N1", product="FUND_PRVN",
                         platform="PRV_PLATN", nav=None)
        trade_id = self._create_otc_buy(
            client, admin_headers,
            portfolio="PRV_N1", product="FUND_PRVN", platform="PRV_PLATN",
        )

        prev = client.get(f"/api/trades/{trade_id}/preview", headers=admin_headers)
        assert prev.status_code == 422
        assert prev.json()["detail"]["error"] == "MISSING_NAV"

    def test_preview_price_nav_mismatch_rejected(self, client, admin_headers, test_db):
        """传入与 T 日净值不一致的 price：preview 返回 422 PRICE_NAV_MISMATCH"""
        self._setup_base(test_db, portfolio="PRV_M1", product="FUND_PRVM",
                         platform="PRV_PLATM", nav=1.25)
        trade_id = self._create_otc_buy(
            client, admin_headers,
            portfolio="PRV_M1", product="FUND_PRVM", platform="PRV_PLATM",
        )

        prev = client.get(
            f"/api/trades/{trade_id}/preview", params={"price": 1.30},
            headers=admin_headers,
        )
        assert prev.status_code == 422
        assert prev.json()["detail"]["error"] == "PRICE_NAV_MISMATCH"

    def test_preview_confirmed_trade_rejected(self, client, admin_headers, test_db):
        """对已 confirmed 交易 preview：422 INVALID_STATUS"""
        self._setup_base(test_db, portfolio="PRV_C1", product="FUND_PRVC",
                         platform="PRV_PLATC", nav=1.25)
        trade_id = self._create_otc_buy(
            client, admin_headers,
            portfolio="PRV_C1", product="FUND_PRVC", platform="PRV_PLATC",
        )
        conf = client.post(f"/api/trades/{trade_id}/confirm", headers=admin_headers)
        assert conf.status_code == 200

        prev = client.get(f"/api/trades/{trade_id}/preview", headers=admin_headers)
        assert prev.status_code == 422
        assert prev.json()["detail"]["error"] == "INVALID_STATUS"

    def test_preview_has_zero_side_effects(self, client, admin_headers, test_db):
        """preview 后 trade 仍 pending、price 仍 null，CASH 腿状态/金额未变"""
        self._setup_base(test_db, portfolio="PRV_Z1", product="FUND_PRVZ",
                         platform="PRV_PLATZ", nav=1.25)
        trade_id = self._create_otc_buy(
            client, admin_headers,
            portfolio="PRV_Z1", product="FUND_PRVZ", platform="PRV_PLATZ",
        )
        fund_leg = test_db.query(Trade).get(trade_id)
        tg = fund_leg.transfer_group
        cash_before = test_db.query(Trade).filter(
            Trade.transfer_group == tg, Trade.id != trade_id
        ).first()
        cash_status_before = cash_before.status
        cash_amount_before = float(cash_before.amount)

        prev = client.get(f"/api/trades/{trade_id}/preview", headers=admin_headers)
        assert prev.status_code == 200

        # 重新 GET trade：零副作用
        got = client.get(f"/api/trades/{trade_id}", headers=admin_headers)
        assert got.status_code == 200
        assert got.json()["status"] == "pending"
        assert got.json()["price"] is None

        test_db.expire_all()
        cash_after = test_db.query(Trade).filter(
            Trade.transfer_group == tg, Trade.id != trade_id
        ).first()
        assert cash_after.status == cash_status_before
        assert float(cash_after.amount) == cash_amount_before


class TestListTradeFilters:
    """调仓列表筛选/排序（issue #126）"""

    def test_filter_by_status(self, client, admin_headers, test_db):
        """三种状态各造 1 条，分别过滤只回目标状态"""
        create_portfolio(test_db, code="LT_P1", status="active")
        create_trade(test_db, "LT_P1", "CASH", "", trade_type="buy", status="pending",
                     trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P1", "CASH", "", trade_type="buy", status="confirmed",
                     trade_date=date(2025, 9, 2), confirm_date=date(2025, 9, 2))
        create_trade(test_db, "LT_P1", "CASH", "", trade_type="buy", status="cancelled",
                     trade_date=date(2025, 9, 3))

        for st in ("pending", "confirmed", "cancelled"):
            resp = client.get(f"/api/trades?status={st}", headers=admin_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert all(item["status"] == st for item in data["items"])

    def test_filter_by_trade_type_and_platform(self, client, admin_headers, test_db):
        """trade_type + platform_code 组合过滤取交集"""
        create_portfolio(test_db, code="LT_P2", status="active")
        create_platform(test_db, code="LT_PLAT")
        create_trade(test_db, "LT_P2", "CASH", "", trade_type="sell",
                     platform_code="LT_PLAT", trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P2", "CASH", "", trade_type="sell",
                     platform_code="MYCF", trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P2", "CASH", "", trade_type="buy",
                     platform_code="LT_PLAT", trade_date=date(2025, 9, 1))

        resp = client.get(
            "/api/trades?trade_type=sell&platform_code=LT_PLAT",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trade_type"] == "sell"
        assert data["items"][0]["platform_code"] == "LT_PLAT"

    def test_filter_trade_date_range_closed(self, client, admin_headers, test_db):
        """交易日期区间为闭区间：边界日记录包含"""
        create_portfolio(test_db, code="LT_P3", status="active")
        create_trade(test_db, "LT_P3", "CASH", "", trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P3", "CASH", "", trade_date=date(2025, 9, 5))
        create_trade(test_db, "LT_P3", "CASH", "", trade_date=date(2025, 9, 10))

        resp = client.get(
            "/api/trades?trade_date_start=2025-09-01&trade_date_end=2025-09-05",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        dates = sorted(item["trade_date"] for item in data["items"])
        assert dates == ["2025-09-01", "2025-09-05"]

    def test_filter_confirm_date_range(self, client, admin_headers, test_db):
        """确认日期区间过滤（含 pending 预计确认日）"""
        create_portfolio(test_db, code="LT_P8", status="active")
        create_trade(test_db, "LT_P8", "CASH", "", status="pending",
                     trade_date=date(2025, 9, 1), confirm_date=date(2025, 9, 2))
        create_trade(test_db, "LT_P8", "CASH", "", status="confirmed",
                     trade_date=date(2025, 9, 3), confirm_date=date(2025, 9, 4))

        resp = client.get(
            "/api/trades?confirm_date_start=2025-09-02&confirm_date_end=2025-09-02",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "pending"
        assert data["items"][0]["confirm_date"] == "2025-09-02"

    def test_inverted_range_returns_422(self, client, admin_headers, test_db):
        """start > end 返回 422 INVALID_DATE_RANGE（trade/confirm 两组同理）"""
        resp = client.get(
            "/api/trades?trade_date_start=2025-09-10&trade_date_end=2025-09-01",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DATE_RANGE"

        resp = client.get(
            "/api/trades?confirm_date_start=2025-09-10&confirm_date_end=2025-09-01",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DATE_RANGE"

    def test_sort_trade_date_desc(self, client, admin_headers, test_db):
        """排序 trade_date DESC（不同日期降序）"""
        create_portfolio(test_db, code="LT_P4", status="active")
        t1 = create_trade(test_db, "LT_P4", "CASH", "", trade_date=date(2025, 9, 1))
        t2 = create_trade(test_db, "LT_P4", "CASH", "", trade_date=date(2025, 9, 10))
        t3 = create_trade(test_db, "LT_P4", "CASH", "", trade_date=date(2025, 9, 5))

        resp = client.get("/api/trades", headers=admin_headers)
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert ids == [t2.id, t3.id, t1.id]

    def test_sort_groups_adjacent(self, client, admin_headers, test_db):
        """同 transfer_group 两腿在结果中相邻（排序键含 transfer_group，决策⑪）"""
        create_portfolio(test_db, code="LT_P5", status="active")
        # 同交易日两个组：trade_date 相同时按 transfer_group 聚集
        fund_leg = create_trade(test_db, "LT_P5", "510300.SH", "CN_EXCHANGE",
                                trade_type="buy", trade_date=date(2025, 9, 1),
                                transfer_group="rebal_adj01")
        cash_leg = create_trade(test_db, "LT_P5", "CASH", "",
                                trade_type="sell", trade_date=date(2025, 9, 1),
                                transfer_group="rebal_adj01")
        other = create_trade(test_db, "LT_P5", "CASH", "",
                             trade_type="buy", trade_date=date(2025, 9, 1),
                             transfer_group="rebal_adj02")

        resp = client.get("/api/trades", headers=admin_headers)
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        # 同组两腿相邻，且整组排在 adj02 组之前（transfer_group 升序）
        assert abs(ids.index(fund_leg.id) - ids.index(cash_leg.id)) == 1
        assert ids.index(fund_leg.id) < ids.index(other.id)
        assert ids.index(cash_leg.id) < ids.index(other.id)

    def test_filter_product_code_only_matches_all_markets(self, client, admin_headers, test_db):
        """仅 product_code 时 LOF 一码多市场全命中"""
        create_portfolio(test_db, code="LT_P6", status="active")
        create_product(test_db, code="LOF01", market="CN_EXCHANGE", product_type="LOF")
        create_product(test_db, code="LOF01", market="CN_OTC", product_type="LOF")
        create_trade(test_db, "LT_P6", "LOF01", "CN_EXCHANGE", trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P6", "LOF01", "CN_OTC", trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P6", "CASH", "", trade_date=date(2025, 9, 1))

        resp = client.get("/api/trades?product_code=LOF01", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        markets = sorted(item["market"] for item in data["items"])
        assert markets == ["CN_EXCHANGE", "CN_OTC"]

    def test_filter_product_code_with_market_exact(self, client, admin_headers, test_db):
        """product_code + market 精确过滤（LOF 只命中指定市场）"""
        create_portfolio(test_db, code="LT_P7", status="active")
        create_product(test_db, code="LOF02", market="CN_EXCHANGE", product_type="LOF")
        create_product(test_db, code="LOF02", market="CN_OTC", product_type="LOF")
        create_trade(test_db, "LT_P7", "LOF02", "CN_EXCHANGE", trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P7", "LOF02", "CN_OTC", trade_date=date(2025, 9, 1))

        resp = client.get(
            "/api/trades?product_code=LOF02&market=CN_OTC",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["market"] == "CN_OTC"

    def test_filter_products_multi_pairs(self, client, admin_headers, test_db):
        """products=A|CN_OTC,B|CN_EXCHANGE 复合多选命中两笔，LOF 不串市场（issue #155）"""
        create_portfolio(test_db, code="LT_P9", status="active")
        create_product(test_db, code="LOF03", market="CN_EXCHANGE", product_type="LOF")
        create_product(test_db, code="LOF03", market="CN_OTC", product_type="LOF")
        create_product(test_db, code="ETF03", market="CN_EXCHANGE", product_type="ETF")
        create_trade(test_db, "LT_P9", "LOF03", "CN_OTC", trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P9", "LOF03", "CN_EXCHANGE", trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P9", "ETF03", "CN_EXCHANGE", trade_date=date(2025, 9, 1))

        resp = client.get(
            "/api/trades?products=LOF03|CN_OTC,ETF03|CN_EXCHANGE",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        pairs = sorted((item["product_code"], item["market"]) for item in data["items"])
        assert pairs == [("ETF03", "CN_EXCHANGE"), ("LOF03", "CN_OTC")]

    def test_filter_products_empty_market_segment(self, client, admin_headers, test_db):
        """products 单值 code|（空 market 段）匹配 market="" 的 CASH 腿"""
        create_portfolio(test_db, code="LT_P10", status="active")
        create_trade(test_db, "LT_P10", "CASH", "", trade_type="sell",
                     trade_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P10", "510300.SH", "CN_EXCHANGE",
                     trade_date=date(2025, 9, 1))

        resp = client.get("/api/trades?products=CASH|", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["product_code"] == "CASH"
        assert data["items"][0]["market"] == ""

    def test_filter_products_conflict_with_single_params(self, client, admin_headers, test_db):
        """products 与 product_code/market 同传 → 422 PRODUCTS_PARAM_CONFLICT"""
        resp = client.get(
            "/api/trades?products=CASH|&product_code=CASH",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "PRODUCTS_PARAM_CONFLICT"

        resp = client.get(
            "/api/trades?products=CASH|&market=CN_OTC",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "PRODUCTS_PARAM_CONFLICT"

    def test_filter_products_with_date_and_status(self, client, admin_headers, test_db):
        """products 与既有日期/状态筛选 AND 叠加"""
        create_portfolio(test_db, code="LT_P11", status="active")
        create_trade(test_db, "LT_P11", "CASH", "", status="confirmed",
                     trade_date=date(2025, 9, 1), confirm_date=date(2025, 9, 1))
        create_trade(test_db, "LT_P11", "CASH", "", status="pending",
                     trade_date=date(2025, 9, 5))
        create_trade(test_db, "LT_P11", "510300.SH", "CN_EXCHANGE", status="confirmed",
                     trade_date=date(2025, 9, 3), confirm_date=date(2025, 9, 3))

        resp = client.get(
            "/api/trades?products=CASH|,510300.SH|CN_EXCHANGE"
            "&status=confirmed&trade_date_start=2025-09-01&trade_date_end=2025-09-02",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["product_code"] == "CASH"
        assert data["items"][0]["status"] == "confirmed"


class TestListTradeProductName:
    """list 响应读侧派生 product_name（issue #175）"""

    def test_list_trades_includes_product_name(self, client, admin_headers, test_db):
        """基金买入产生基金腿 + 配对 CASH 腿，list 每条 item 均应带 product_name
        （基金腿=基金名，CASH 腿=CASH 种子产品名）。
        注：>100 产品的名称回退是前端分页映射问题，后端 join 与产品总数无关，
        无需构造 100+ 产品。"""
        create_portfolio(test_db, code="PN_P1", status="active")
        create_product(test_db, code="ETF_PN", market="CN_EXCHANGE",
                       name="测试ETF产品", product_type="ETF",
                       asset_class_code="ASSET_STOCK", confirm_days=0)
        create_platform(test_db, code="PN_PLAT")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        create_trade(
            test_db, "PN_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="PN_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )

        resp = client.post(
            "/api/trades",
            json={
                "portfolio_code": "PN_P1",
                "product_code": "ETF_PN",
                "market": "CN_EXCHANGE",
                "trade_type": "buy",
                "amount": 10000.0,
                "price": 1.5,
                "platform_code": "PN_PLAT",
                "trade_date": "2025-10-06",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), f"Response: {resp.status_code} {resp.json()}"

        resp = client.get("/api/trades?portfolio_code=PN_P1", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # 现金流入 1 条 + 基金腿 1 条 + 配对 CASH 腿 1 条
        assert data["total"] == 3
        name_by_leg = {
            (item["product_code"], item["trade_type"]): item["product_name"]
            for item in data["items"]
        }
        assert all(item["product_name"] for item in data["items"])
        assert name_by_leg[("ETF_PN", "buy")] == "测试ETF产品"
        assert name_by_leg[("CASH", "sell")] == "现金类资产"
        assert name_by_leg[("CASH", "buy")] == "现金类资产"
        # 字段完整性（issue #183）：挂 response_model 后字段过滤以 TradeResponse
        # 为准，断言实际响应键与 schema 声明一一对应、无字段丢失
        assert set(data["items"][0].keys()) == set(TradeResponse.model_fields.keys())


class TestTradesOpenApiContract:
    """openapi 契约守护（issue #183）：GET /api/trades 分页响应结构化"""

    def test_trades_list_openapi_references_paginated_schema(self, client):
        """openapi.json 中 /api/trades GET 200 应引用 PaginatedTradeResponse，
        且 items 元素指向 TradeResponse（含 product_name），而非空 schema。"""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()

        get_op = spec["paths"]["/api/trades"]["get"]
        schema_ref = get_op["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema_ref == {"$ref": "#/components/schemas/PaginatedTradeResponse"}

        schemas = spec["components"]["schemas"]
        paginated = schemas["PaginatedTradeResponse"]
        assert set(paginated["required"]) == {"items", "total", "page", "page_size"}
        assert set(paginated["properties"].keys()) == {
            "items", "total", "page", "page_size",
        }
        assert paginated["properties"]["items"]["items"] == {
            "$ref": "#/components/schemas/TradeResponse"
        }

        trade_props = schemas["TradeResponse"]["properties"]
        assert "product_name" in trade_props  # 防止误删读侧派生字段声明

