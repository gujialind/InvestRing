# ============================================================================
# 集成测试：申购赎回 (test_subscriptions.py)
# ============================================================================

import pytest
from datetime import date
from decimal import Decimal

from tests.factories import (
    create_portfolio, create_investor, create_subscription,
    create_investor_holding, create_value_snapshot, ensure_trading_day,
    create_trade, create_platform,
)
from app.models.subscription import Subscription
from app.models.trade import Trade


def _started_date(p):
    """started_at 为 DateTime 列但承载日期语义，读回可能是 date/datetime，归一后断言"""
    return p.started_at.date() if p.started_at else None


class TestSubscriptionCreate:
    """申购创建测试"""

    def test_create_subscribe_pending(self, client, admin_headers, test_db):
        """申购提交后应为 pending 状态"""
        create_portfolio(test_db, code="SUB_P1", status="active")
        create_investor(test_db, code="SUB_I1")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "SUB_P1",
                "investor_code": "SUB_I1",
                "sub_type": "subscribe",
                "amount": 10000.0,
                "apply_date": "2025-09-01",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["status"] == "pending"
        assert data["sub_type"] == "subscribe"

    def test_create_sets_confirm_date_next_trading_day(self, client, admin_headers, test_db):
        """#33改动1：创建时即设 confirm_date = 申请日下一交易日（恒 T+1）"""
        create_portfolio(test_db, code="SUB_CD", status="active")
        create_investor(test_db, code="SUB_ICD")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "SUB_CD",
                "investor_code": "SUB_ICD",
                "sub_type": "subscribe",
                "amount": 10000.0,
                "apply_date": "2025-09-01",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        sub = test_db.query(Subscription).filter(
            Subscription.portfolio_code == "SUB_CD"
        ).first()
        assert sub.confirm_date == date(2025, 9, 2)

    def test_subscribe_zero_amount_rejected(self, client, admin_headers, test_db):
        """申购金额为 0 应被拒绝"""
        create_portfolio(test_db, code="SUB_Z", status="active")
        create_investor(test_db, code="SUB_IZ")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "SUB_Z",
                "investor_code": "SUB_IZ",
                "sub_type": "subscribe",
                "amount": 0,
                "apply_date": "2025-09-01",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)

    def test_subscribe_non_trading_day_rejected(self, client, admin_headers, test_db):
        """非交易日申购应被拒绝"""
        create_portfolio(test_db, code="SUB_NTD", status="active")
        create_investor(test_db, code="SUB_INTD")
        ensure_trading_day(test_db, date(2025, 9, 6), is_open=False)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "SUB_NTD",
                "investor_code": "SUB_INTD",
                "sub_type": "subscribe",
                "amount": 5000.0,
                "apply_date": "2025-09-06",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)


class TestRedeemCreate:
    """赎回创建测试"""

    def test_create_redeem_pending(self, client, admin_headers, test_db):
        """赎回提交后应为 pending 状态"""
        create_portfolio(test_db, code="RED_P1", status="active")
        create_investor(test_db, code="RED_I1")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)

        # 先创建持仓快照（有份额才能赎回）
        create_value_snapshot(test_db, "RED_P1", date(2025, 8, 29),
                              total_value=10000, total_shares=10000, unit_price=1.0)
        create_investor_holding(test_db, "RED_P1", "RED_I1", date(2025, 8, 29), shares=10000)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "RED_P1",
                "investor_code": "RED_I1",
                "sub_type": "redeem",
                "shares": 5000.0,
                "apply_date": "2025-09-01",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["status"] == "pending"
        assert data["sub_type"] == "redeem"

    def test_redeem_exceeds_available_shares_rejected(self, client, admin_headers, test_db):
        """赎回份额超过可用份额应被拒绝"""
        create_portfolio(test_db, code="RED_EX", status="active")
        create_investor(test_db, code="RED_IEX")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)

        create_value_snapshot(test_db, "RED_EX", date(2025, 8, 29),
                              total_value=5000, total_shares=5000, unit_price=1.0)
        create_investor_holding(test_db, "RED_EX", "RED_IEX", date(2025, 8, 29), shares=5000)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "RED_EX",
                "investor_code": "RED_IEX",
                "sub_type": "redeem",
                "shares": 99999.0,
                "apply_date": "2025-09-01",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestSubscriptionCancel:
    """申购赎回取消测试"""

    def test_cancel_pending_subscription(self, client, admin_headers, test_db):
        """取消 pending 申购"""
        create_portfolio(test_db, code="CAN_P", status="active")
        create_investor(test_db, code="CAN_I")
        sub = create_subscription(
            test_db, "CAN_P", "CAN_I", status="pending",
            apply_date=date(2025, 9, 1),
        )
        resp = client.post(
            f"/api/subscriptions/{sub.id}/cancel",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        updated = test_db.query(Subscription).filter(Subscription.id == sub.id).first()
        assert updated.status == "cancelled"


class TestSubscriptionPermissions:
    """申购赎回权限测试"""

    def test_viewer_cannot_subscribe(self, client, viewer_headers, test_db):
        """viewer 不能提交申购"""
        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "X",
                "investor_code": "X",
                "sub_type": "subscribe",
                "amount": 1000,
                "apply_date": "2025-09-01",
                "platform_code": "MYCF",
            },
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_list_subscriptions(self, client, admin_headers, test_db):
        """获取申购赎回列表"""
        resp = client.get("/api/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        assert "items" in resp.json()


class TestAsOfDateRedeemValidation:
    """#47 补录历史赎回时 as_of_date 排除后续 confirmed"""

    def test_backfill_redeem_not_blocked_by_later_confirmed(self, client, admin_headers, test_db):
        """补录历史日赎回，后续 confirmed 赎回不应计入扣减"""
        create_portfolio(test_db, code="ASOF_RP", status="active")
        create_investor(test_db, code="ASOF_RI")
        ensure_trading_day(test_db, date(2025, 1, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 1, 7), is_open=True)
        ensure_trading_day(test_db, date(2025, 1, 8), is_open=True)
        ensure_trading_day(test_db, date(2025, 1, 9), is_open=True)
        # 快照：投资人份额=1000
        create_value_snapshot(test_db, "ASOF_RP", date(2025, 1, 6),
                              total_value=1000, total_shares=1000, unit_price=1.0)
        create_investor_holding(test_db, "ASOF_RP", "ASOF_RI", date(2025, 1, 6), shares=1000)
        # 后续 confirmed 赎回 800（confirm_date=1/8，快照后）
        create_subscription(
            test_db, "ASOF_RP", "ASOF_RI", sub_type="redeem",
            shares=800, apply_date=date(2025, 1, 7),
            confirm_date=date(2025, 1, 8), status="confirmed",
        )
        # 补录 1/7 赎回 500：as_of=1/7 时后续 confirm_date=1/8 不计入，可用=1000
        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "ASOF_RP",
                "investor_code": "ASOF_RI",
                "sub_type": "redeem",
                "shares": 500,
                "apply_date": "2025-01-07",
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        # 不应被 INSUFFICIENT_SHARES 拒绝
        assert resp.status_code in (200, 201), f"Expected success, got {resp.status_code}: {resp.json()}"


class TestUnconfirmSubscriptionSnapshotProtection:
    """unconfirm 申赎快照保护（SNAPSHOT_DEPENDENCY 检查已内嵌 subscription_service）"""

    def test_unconfirm_blocked_by_snapshot(self, client, admin_headers, test_db):
        """confirm_date 及之后已有快照时，unconfirm 返回 422 SNAPSHOT_DEPENDENCY 且状态不变"""
        create_portfolio(test_db, code="SUB_UC1", status="active")
        create_investor(test_db, code="SUB_UCI1")
        sub = create_subscription(
            test_db, "SUB_UC1", "SUB_UCI1",
            sub_type="subscribe", amount=10000.0, shares=10000.0,
            unit_price=1.0, apply_date=date(2025, 9, 1),
            confirm_date=date(2025, 9, 2), status="confirmed",
        )
        # 在 confirm_date 生成组合快照 → 快照依赖成立
        create_value_snapshot(
            test_db, "SUB_UC1", date(2025, 9, 2),
            total_value=10000, total_shares=10000, unit_price=1.0,
        )

        resp = client.post(
            f"/api/subscriptions/{sub.id}/unconfirm",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "SNAPSHOT_DEPENDENCY"
        # 检查发生在改字段之前，状态未被回退
        still = test_db.query(Subscription).filter(Subscription.id == sub.id).first()
        assert still.status == "confirmed"

    def test_unconfirm_ok_without_snapshot(self, client, admin_headers, test_db):
        """无快照依赖时 unconfirm 成功回退 pending 并级联删除配对 CASH trade"""
        create_portfolio(test_db, code="SUB_UC2", status="active")
        create_investor(test_db, code="SUB_UCI2")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)
        sub = create_subscription(
            test_db, "SUB_UC2", "SUB_UCI2",
            sub_type="subscribe", amount=10000.0, shares=10000.0,
            unit_price=1.0, apply_date=date(2025, 9, 1),
            confirm_date=date(2025, 9, 2), status="confirmed",
        )
        # 配对 CASH trade（transfer_group=sub_{id}），unconfirm 应级联物理删除
        create_trade(
            test_db, "SUB_UC2", "CASH", "",
            trade_type="buy", amount=10000.0, price=1.0,
            trade_date=date(2025, 9, 1), confirm_date=date(2025, 9, 2),
            actual_amount=10000.0, status="confirmed",
            transfer_group=f"sub_{sub.id}",
        )

        resp = client.post(
            f"/api/subscriptions/{sub.id}/unconfirm",
            headers=admin_headers,
        )
        assert resp.status_code == 200

        updated = test_db.query(Subscription).filter(Subscription.id == sub.id).first()
        assert updated.status == "pending"
        # confirm_date 不置 None，重算为 T+1，避免快照校验 NULL 漏检
        assert updated.confirm_date == date(2025, 9, 2)
        # 配对 CASH trade 已物理删除
        remaining = test_db.query(Trade).filter(
            Trade.transfer_group == f"sub_{sub.id}"
        ).count()
        assert remaining == 0


class TestListSubscriptionFilters:
    """申赎列表筛选/排序（issue #125）"""

    def test_filter_by_status(self, client, admin_headers, test_db):
        """三种状态各造 1 条，分别过滤只回目标状态"""
        create_portfolio(test_db, code="LS_P1", status="active")
        create_investor(test_db, code="LS_I1")
        create_subscription(test_db, "LS_P1", "LS_I1", status="pending",
                            apply_date=date(2025, 9, 1))
        create_subscription(test_db, "LS_P1", "LS_I1", status="confirmed",
                            apply_date=date(2025, 9, 2), confirm_date=date(2025, 9, 3))
        create_subscription(test_db, "LS_P1", "LS_I1", status="cancelled",
                            apply_date=date(2025, 9, 3))

        for st in ("pending", "confirmed", "cancelled"):
            resp = client.get(f"/api/subscriptions?status={st}", headers=admin_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert all(item["status"] == st for item in data["items"])

    def test_filter_by_sub_type_and_platform(self, client, admin_headers, test_db):
        """sub_type + platform_code 组合过滤取交集"""
        create_portfolio(test_db, code="LS_P2", status="active")
        create_investor(test_db, code="LS_I2")
        create_platform(test_db, code="LS_PLAT")
        create_subscription(test_db, "LS_P2", "LS_I2", sub_type="redeem", shares=100,
                            platform_code="LS_PLAT", apply_date=date(2025, 9, 1))
        create_subscription(test_db, "LS_P2", "LS_I2", sub_type="redeem", shares=100,
                            platform_code="MYCF", apply_date=date(2025, 9, 1))
        create_subscription(test_db, "LS_P2", "LS_I2", sub_type="subscribe",
                            platform_code="LS_PLAT", apply_date=date(2025, 9, 1))

        resp = client.get(
            "/api/subscriptions?sub_type=redeem&platform_code=LS_PLAT",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["sub_type"] == "redeem"
        assert data["items"][0]["platform_code"] == "LS_PLAT"

    def test_filter_apply_date_range_closed(self, client, admin_headers, test_db):
        """申请日期区间为闭区间：边界日记录包含"""
        create_portfolio(test_db, code="LS_P3", status="active")
        create_investor(test_db, code="LS_I3")
        create_subscription(test_db, "LS_P3", "LS_I3", apply_date=date(2025, 9, 1))
        create_subscription(test_db, "LS_P3", "LS_I3", apply_date=date(2025, 9, 5))
        create_subscription(test_db, "LS_P3", "LS_I3", apply_date=date(2025, 9, 10))

        resp = client.get(
            "/api/subscriptions?apply_date_start=2025-09-01&apply_date_end=2025-09-05",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        dates = sorted(item["apply_date"] for item in data["items"])
        assert dates == ["2025-09-01", "2025-09-05"]

    def test_filter_confirm_date_includes_pending_expected(self, client, admin_headers, test_db):
        """pending 记录按预计确认日命中确认日期区间（决策②）"""
        create_portfolio(test_db, code="LS_P4", status="active")
        create_investor(test_db, code="LS_I4")
        # pending：confirm_date 为预计确认日（创建时按 T+1 设定、保持非空）
        create_subscription(test_db, "LS_P4", "LS_I4", status="pending",
                            apply_date=date(2025, 9, 1), confirm_date=date(2025, 9, 2))
        create_subscription(test_db, "LS_P4", "LS_I4", status="confirmed",
                            apply_date=date(2025, 9, 3), confirm_date=date(2025, 9, 4))

        resp = client.get(
            "/api/subscriptions?confirm_date_start=2025-09-02&confirm_date_end=2025-09-02",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "pending"
        assert data["items"][0]["confirm_date"] == "2025-09-02"

    def test_inverted_range_returns_422(self, client, admin_headers, test_db):
        """start > end 返回 422 INVALID_DATE_RANGE（apply/confirm 两组同理）"""
        resp = client.get(
            "/api/subscriptions?apply_date_start=2025-09-10&apply_date_end=2025-09-01",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DATE_RANGE"

        resp = client.get(
            "/api/subscriptions?confirm_date_start=2025-09-10&confirm_date_end=2025-09-01",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DATE_RANGE"

    def test_sort_apply_date_desc(self, client, admin_headers, test_db):
        """排序 apply_date DESC, id DESC（同日期新记录在前）"""
        create_portfolio(test_db, code="LS_P5", status="active")
        create_investor(test_db, code="LS_I5")
        s1 = create_subscription(test_db, "LS_P5", "LS_I5", apply_date=date(2025, 9, 1))
        s2 = create_subscription(test_db, "LS_P5", "LS_I5", apply_date=date(2025, 9, 10))
        s3 = create_subscription(test_db, "LS_P5", "LS_I5", apply_date=date(2025, 9, 10))
        s4 = create_subscription(test_db, "LS_P5", "LS_I5", apply_date=date(2025, 9, 5))

        resp = client.get("/api/subscriptions", headers=admin_headers)
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert ids == [s3.id, s2.id, s4.id, s1.id]

    def test_viewer_restriction_with_filters(self, client, viewer_headers, test_db):
        """viewer 带 status 过滤仍只见自己记录；显式传他人 investor_code 被覆盖"""
        create_portfolio(test_db, code="LS_P6", status="active")
        create_investor(test_db, code="LS_I6")
        create_subscription(test_db, "LS_P6", "VIEWER", status="pending",
                            apply_date=date(2025, 9, 1))
        create_subscription(test_db, "LS_P6", "LS_I6", status="pending",
                            apply_date=date(2025, 9, 1))

        resp = client.get("/api/subscriptions?status=pending", headers=viewer_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["investor_code"] == "VIEWER"

        # 显式传他人 investor_code 被 router 强制覆盖
        resp = client.get(
            "/api/subscriptions?status=pending&investor_code=LS_I6",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["investor_code"] == "VIEWER"


# ============================================================================
# issue #179：首窗 1.0 定价（三级决策）+ CONFIRM_BEFORE_STARTED 硬闸门
# ============================================================================

class TestFirstWindowPricingAndGate:
    """首日多平台申购不再死循环；乱序补录被闸门阻断"""

    def test_same_day_multi_platform_all_confirm_at_1(self, client, admin_headers, test_db):
        """原场景（PORT005）：同日多平台申购全部可确认，unit_price 均 1.0000，
        confirm_date == started_at 放行，各自生成配对 CASH buy"""
        create_portfolio(test_db, code="FW_P1")  # draft
        create_investor(test_db, code="FW_I1")
        create_platform(test_db, code="FW_PLAT2")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)

        sub_ids = []
        for plat, amount in (("MYCF", 143560.82), ("FW_PLAT2", 39105.99)):
            resp = client.post(
                "/api/subscriptions",
                json={
                    "portfolio_code": "FW_P1", "investor_code": "FW_I1",
                    "sub_type": "subscribe", "amount": amount,
                    "apply_date": "2025-09-01", "platform_code": plat,
                },
                headers=admin_headers,
            )
            assert resp.status_code in (200, 201)
            sub_ids.append(resp.json()["id"])

        for sid in sub_ids:
            resp = client.post(f"/api/subscriptions/{sid}/confirm", headers=admin_headers)
            assert resp.status_code == 200, resp.json()
            data = resp.json()
            assert Decimal(str(data["unit_price"])) == Decimal("1.0000")
            # 配对 CASH buy 落库
            legs = test_db.query(Trade).filter(
                Trade.transfer_group == f"sub_{sid}"
            ).all()
            assert len(legs) == 1
            assert legs[0].trade_type == "buy" and legs[0].status == "confirmed"

        from app.models.portfolio import Portfolio
        p = test_db.query(Portfolio).filter(Portfolio.code == "FW_P1").first()
        assert p.status == "active"
        assert _started_date(p) == date(2025, 9, 2)

    def test_apply_date_with_prior_arrival_needs_snapshot(self, client, admin_headers, test_db):
        """边界守卫：A apply=D-1 已 confirmed（confirm=D），B apply=D 且无快照 →
        NAV_NOT_AVAILABLE（当日已有资金到账，不适用首窗例外）"""
        create_portfolio(test_db, code="FW_P2")
        create_investor(test_db, code="FW_I2")
        for d in (1, 2, 3):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "FW_P2", "investor_code": "FW_I2",
                "sub_type": "subscribe", "amount": 10000.0,
                "apply_date": "2025-09-01", "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        a_id = resp.json()["id"]
        assert client.post(f"/api/subscriptions/{a_id}/confirm", headers=admin_headers).status_code == 200

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "FW_P2", "investor_code": "FW_I2",
                "sub_type": "subscribe", "amount": 5000.0,
                "apply_date": "2025-09-02", "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        b_id = resp.json()["id"]
        resp = client.post(f"/api/subscriptions/{b_id}/confirm", headers=admin_headers)
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "NAV_NOT_AVAILABLE"

    def test_out_of_order_confirm_blocked(self, client, admin_headers, test_db):
        """乱序补录：confirm_date < started_at 被 CONFIRM_BEFORE_STARTED 阻断且不落库；
        首笔确认（started_at 尚空）豁免"""
        create_portfolio(test_db, code="FW_P3")
        create_investor(test_db, code="FW_I3")
        ensure_trading_day(test_db, date(2025, 8, 29), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)

        # 首笔（started_at 空）豁免阻断
        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "FW_P3", "investor_code": "FW_I3",
                "sub_type": "subscribe", "amount": 10000.0,
                "apply_date": "2025-09-01", "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        s1_id = resp.json()["id"]
        assert client.post(f"/api/subscriptions/{s1_id}/confirm", headers=admin_headers).status_code == 200

        # 补录更早申购：confirm=09-01 < started_at=09-02 → 阻断
        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "FW_P3", "investor_code": "FW_I3",
                "sub_type": "subscribe", "amount": 8000.0,
                "apply_date": "2025-08-29", "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        s0_id = resp.json()["id"]
        resp = client.post(f"/api/subscriptions/{s0_id}/confirm", headers=admin_headers)
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "CONFIRM_BEFORE_STARTED"
        still = test_db.query(Subscription).filter(Subscription.id == s0_id).first()
        assert still.status == "pending"

    def test_unconfirm_first_then_confirm_another(self, client, admin_headers, test_db):
        """首笔 unconfirm 后组合回 draft/started_at 清空（#180），
        再 confirm 另一笔仍走 1.0 且重设 started_at"""
        create_portfolio(test_db, code="FW_P4")
        create_investor(test_db, code="FW_I4")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "FW_P4", "investor_code": "FW_I4",
                "sub_type": "subscribe", "amount": 10000.0,
                "apply_date": "2025-09-01", "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        s1_id = resp.json()["id"]
        assert client.post(f"/api/subscriptions/{s1_id}/confirm", headers=admin_headers).status_code == 200
        assert client.post(f"/api/subscriptions/{s1_id}/unconfirm", headers=admin_headers).status_code == 200

        from app.models.portfolio import Portfolio
        p = test_db.query(Portfolio).filter(Portfolio.code == "FW_P4").first()
        assert p.status == "draft" and p.started_at is None

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "FW_P4", "investor_code": "FW_I4",
                "sub_type": "subscribe", "amount": 6000.0,
                "apply_date": "2025-09-01", "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        s2_id = resp.json()["id"]
        resp = client.post(f"/api/subscriptions/{s2_id}/confirm", headers=admin_headers)
        assert resp.status_code == 200
        assert Decimal(str(resp.json()["unit_price"])) == Decimal("1.0000")
        test_db.refresh(p)
        assert p.status == "active" and _started_date(p) == date(2025, 9, 2)

    def test_snapshot_nav_takes_precedence(self, client, admin_headers, test_db):
        """回归：申请日快照存在时取快照净值（三级决策 branch 1）"""
        create_portfolio(test_db, code="FW_P5", status="active")
        create_investor(test_db, code="FW_I5")
        for d in (1, 2, 3):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        create_value_snapshot(test_db, "FW_P5", date(2025, 9, 1),
                              total_value=12345, total_shares=10000, unit_price=1.2345)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "FW_P5", "investor_code": "FW_I5",
                "sub_type": "subscribe", "amount": 10000.0,
                "apply_date": "2025-09-02", "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        sub_id = resp.json()["id"]
        # 创建后再补申请日快照（模拟快照生成先于确认的正常流程）
        create_value_snapshot(test_db, "FW_P5", date(2025, 9, 2),
                              total_value=12500, total_shares=10000, unit_price=1.25)

        resp = client.post(f"/api/subscriptions/{sub_id}/confirm", headers=admin_headers)
        assert resp.status_code == 200
        assert Decimal(str(resp.json()["unit_price"])) == Decimal("1.25")


# ============================================================================
# issue #180：started_at = 现存最小 confirm_date（重算不变量）+ 回滚链防护
# ============================================================================

def _confirmed_sub_with_cash_leg(
    db, portfolio_code, investor_code, amount, apply_date, confirm_date,
):
    """工厂造 confirmed 申购 + 配对 CASH buy 腿（模拟真实确认产物）"""
    sub = create_subscription(
        db, portfolio_code, investor_code,
        sub_type="subscribe", amount=amount, shares=amount,
        unit_price=1.0, apply_date=apply_date,
        confirm_date=confirm_date, status="confirmed",
    )
    create_trade(
        db, portfolio_code, "CASH", "",
        trade_type="buy", amount=amount, price=1.0,
        trade_date=apply_date, confirm_date=confirm_date,
        actual_amount=amount, status="confirmed",
        transfer_group=f"sub_{sub.id}",
    )
    return sub


class TestStartedAtInvariant:
    """started_at 重算不变量（#180 定稿方案）"""

    def test_unconfirm_earliest_recomputes_to_next(self, client, admin_headers, test_db):
        """定稿反例：unconfirm 最早那笔（还有更晚 B）→ started_at = 次小 confirm_date"""
        from app.models.portfolio import Portfolio
        create_portfolio(test_db, code="SR_P1", status="active")
        create_investor(test_db, code="SR_I1")
        for d in (1, 2, 3):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        s1 = _confirmed_sub_with_cash_leg(
            test_db, "SR_P1", "SR_I1", 10000.0, date(2025, 9, 1), date(2025, 9, 2))
        _confirmed_sub_with_cash_leg(
            test_db, "SR_P1", "SR_I1", 5000.0, date(2025, 9, 2), date(2025, 9, 3))
        p = test_db.query(Portfolio).filter(Portfolio.code == "SR_P1").first()
        p.started_at = date(2025, 9, 2)
        test_db.commit()

        resp = client.post(f"/api/subscriptions/{s1.id}/unconfirm", headers=admin_headers)
        assert resp.status_code == 200, resp.json()
        test_db.refresh(p)
        assert _started_date(p) == date(2025, 9, 3)  # 不再悬空在已撤销交易的确认日
        assert p.status == "active"

    def test_unconfirm_non_earliest_keeps_started_at(self, client, admin_headers, test_db):
        """unconfirm 非最早笔 → started_at 不变，多笔时 status 保持 active"""
        from app.models.portfolio import Portfolio
        create_portfolio(test_db, code="SR_P2", status="active")
        create_investor(test_db, code="SR_I2")
        for d in (1, 2, 3):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        _confirmed_sub_with_cash_leg(
            test_db, "SR_P2", "SR_I2", 10000.0, date(2025, 9, 1), date(2025, 9, 2))
        s2 = _confirmed_sub_with_cash_leg(
            test_db, "SR_P2", "SR_I2", 5000.0, date(2025, 9, 2), date(2025, 9, 3))
        p = test_db.query(Portfolio).filter(Portfolio.code == "SR_P2").first()
        p.started_at = date(2025, 9, 2)
        test_db.commit()

        resp = client.post(f"/api/subscriptions/{s2.id}/unconfirm", headers=admin_headers)
        assert resp.status_code == 200
        test_db.refresh(p)
        assert _started_date(p) == date(2025, 9, 2)
        assert p.status == "active"

    def test_unconfirm_to_zero_reverts_draft(self, client, admin_headers, test_db):
        """unconfirm 至零确认申购 → draft + started_at NULL"""
        from app.models.portfolio import Portfolio
        create_portfolio(test_db, code="SR_P3", status="active")
        create_investor(test_db, code="SR_I3")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)
        s1 = _confirmed_sub_with_cash_leg(
            test_db, "SR_P3", "SR_I3", 10000.0, date(2025, 9, 1), date(2025, 9, 2))

        resp = client.post(f"/api/subscriptions/{s1.id}/unconfirm", headers=admin_headers)
        assert resp.status_code == 200
        p = test_db.query(Portfolio).filter(Portfolio.code == "SR_P3").first()
        assert p.status == "draft" and p.started_at is None

    def test_unconfirm_recomputes_started_at_without_autoflush(self, test_db):
        """回归：生产 session autoflush=False 时 started_at 重算不得脏读

        生产 SessionLocal 配置 autoflush=False（app/database.py），而测试会话默认
        autoflush=True 会掩盖「status=pending 未落库、min 聚合把本条仍算作
        confirmed」的脏读。本用例用同连接上的 autoflush=False 会话直连 service，
        模拟生产行为。
        """
        from sqlalchemy.orm import sessionmaker
        from app.models.portfolio import Portfolio
        from app.models.subscription import Subscription
        from app.services.subscription_service import unconfirm_single_subscription
        create_portfolio(test_db, code="SR_P5", status="active")
        create_investor(test_db, code="SR_I5")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)
        s1 = _confirmed_sub_with_cash_leg(
            test_db, "SR_P5", "SR_I5", 10000.0, date(2025, 9, 1), date(2025, 9, 2))
        test_db.commit()

        NoAutoflush = sessionmaker(
            bind=test_db.get_bind(), autoflush=False, expire_on_commit=False)
        db2 = NoAutoflush()
        try:
            sub = db2.query(Subscription).filter(Subscription.id == s1.id).first()
            unconfirm_single_subscription(db2, sub, check_snapshot=False)
            p = db2.query(Portfolio).filter(Portfolio.code == "SR_P5").first()
            assert p.started_at is None and p.status == "draft"
        finally:
            db2.close()

    def test_closed_not_reverted_by_cascade_unconfirm(self, test_db):
        """closed 组合经级联回退（check_snapshot=False）至零确认时保持 closed"""
        from app.models.portfolio import Portfolio
        from app.services.subscription_service import unconfirm_single_subscription
        create_portfolio(test_db, code="SR_P4", status="closed")
        create_investor(test_db, code="SR_I4")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)
        s1 = _confirmed_sub_with_cash_leg(
            test_db, "SR_P4", "SR_I4", 10000.0, date(2025, 9, 1), date(2025, 9, 2))

        unconfirm_single_subscription(test_db, s1, check_snapshot=False)
        test_db.commit()
        p = test_db.query(Portfolio).filter(Portfolio.code == "SR_P4").first()
        assert p.status == "closed" and p.started_at is None

    def test_reactivate_keeps_started_at_and_relaxed_write(self, client, admin_headers, test_db):
        """close/reactivate 不碰 started_at；空组合 reactivate 后新首购仍能写入
        （写入条件放宽为 started_at is None）"""
        from app.models.portfolio import Portfolio
        from app.services.subscription_service import unconfirm_single_subscription
        create_portfolio(test_db, code="RA_P1", status="active")
        create_investor(test_db, code="RA_I1")
        for d in (1, 2, 8, 9):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        s1 = _confirmed_sub_with_cash_leg(
            test_db, "RA_P1", "RA_I1", 10000.0, date(2025, 9, 1), date(2025, 9, 2))
        p = test_db.query(Portfolio).filter(Portfolio.code == "RA_P1").first()
        p.started_at = date(2025, 9, 2)
        test_db.commit()

        # 级联回退至零确认（closed 保持），再 close/reactivate 流转
        p.status = "closed"
        test_db.commit()
        unconfirm_single_subscription(test_db, s1, check_snapshot=False)
        test_db.commit()
        assert client.post("/api/portfolios/RA_P1/reactivate", headers=admin_headers).status_code == 200
        test_db.refresh(p)
        assert p.status == "active" and p.started_at is None

        # reactivate 后的新首购：status 已是 active，旧 draft 条件会漏设 started_at
        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "RA_P1", "investor_code": "RA_I1",
                "sub_type": "subscribe", "amount": 7000.0,
                "apply_date": "2025-09-08", "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        new_id = resp.json()["id"]
        resp = client.post(f"/api/subscriptions/{new_id}/confirm", headers=admin_headers)
        assert resp.status_code == 200
        assert Decimal(str(resp.json()["unit_price"])) == Decimal("1.0000")
        test_db.refresh(p)
        assert p.started_at == date(2025, 9, 9) or _started_date(p) == date(2025, 9, 9)

    def test_close_reactivate_keeps_started_at_regression(self, client, admin_headers, test_db):
        """回归：close/reactivate 流转前后 started_at 完全不变"""
        from app.models.portfolio import Portfolio
        create_portfolio(test_db, code="RA_P2", status="active")
        create_investor(test_db, code="RA_I2")
        p = test_db.query(Portfolio).filter(Portfolio.code == "RA_P2").first()
        p.started_at = date(2025, 9, 2)
        test_db.commit()

        assert client.post("/api/portfolios/RA_P2/close", headers=admin_headers).status_code == 200
        assert client.post("/api/portfolios/RA_P2/reactivate", headers=admin_headers).status_code == 200
        test_db.refresh(p)
        assert _started_date(p) == date(2025, 9, 2)


class TestUnconfirmNegativeCashGuard:
    """回滚链防护：入金已被消耗时拒绝 unconfirm"""

    def test_unconfirm_blocked_when_cash_consumed(self, client, admin_headers, test_db):
        create_portfolio(test_db, code="RC_P1")
        create_investor(test_db, code="RC_I1")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)

        resp = client.post(
            "/api/subscriptions",
            json={
                "portfolio_code": "RC_P1", "investor_code": "RC_I1",
                "sub_type": "subscribe", "amount": 10000.0,
                "apply_date": "2025-09-01", "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        s1_id = resp.json()["id"]
        assert client.post(f"/api/subscriptions/{s1_id}/confirm", headers=admin_headers).status_code == 200

        # 模拟现金被后续交易消耗（confirmed CASH sell 8000，余额仅剩 2000）
        create_trade(
            test_db, "RC_P1", "CASH", "",
            trade_type="sell", amount=8000.0, price=1.0,
            trade_date=date(2025, 9, 2), confirm_date=date(2025, 9, 2),
            actual_amount=8000.0, status="confirmed",
            transfer_group="rc_consume",
        )

        resp = client.post(f"/api/subscriptions/{s1_id}/unconfirm", headers=admin_headers)
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "UNCONFIRM_WOULD_NEGATIVE_CASH"
        still = test_db.query(Subscription).filter(Subscription.id == s1_id).first()
        assert still.status == "confirmed"


# ============================================================================
# issue #180：零快照 + 目标日前有确认交易 → 拒绝单日 generate（防首快照失忆）
# ============================================================================

class TestSnapshotHistoryGapGuard:

    def test_generate_rejected_when_earlier_arrivals_exist(self, test_db):
        from app.services.snapshot_service import generate_daily_snapshots
        from app.services.exceptions import BusinessError
        create_portfolio(test_db, code="SG_P1", status="active")
        create_investor(test_db, code="SG_I1")
        for d in (1, 2, 3, 4):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        _confirmed_sub_with_cash_leg(
            test_db, "SG_P1", "SG_I1", 10000.0, date(2025, 9, 1), date(2025, 9, 2))

        with pytest.raises(BusinessError) as exc_info:
            generate_daily_snapshots(test_db, "SG_P1", date(2025, 9, 4))
        assert exc_info.value.code == "SNAPSHOT_REQUIRES_RECALCULATE"

    def test_generate_at_earliest_confirm_date_allowed(self, test_db):
        """目标日即最早到账日的真正首次生成不受守卫影响（须真实生成成功）"""
        from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
        from app.services.snapshot_service import generate_daily_snapshots
        create_portfolio(test_db, code="SG_P2", status="active")
        create_investor(test_db, code="SG_I2")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 2), is_open=True)
        _confirmed_sub_with_cash_leg(
            test_db, "SG_P2", "SG_I2", 10000.0, date(2025, 9, 1), date(2025, 9, 2))

        # 不捕获异常：任何 BusinessError 都直接使测试失败
        generate_daily_snapshots(test_db, "SG_P2", date(2025, 9, 2))

        snap = test_db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == "SG_P2",
            PortfolioValueSnapshot.snapshot_date == date(2025, 9, 2),
        ).first()
        assert snap is not None

    def test_recalculate_captures_history_cash(self, test_db):
        """recalculate 从最早 confirm_date 逐日重建，首张快照含历史 CASH 到账"""
        from app.models.portfolio_position import PortfolioPosition
        from app.services.snapshot_service import recalculate_snapshots
        create_portfolio(test_db, code="SG_P3", status="active")
        create_investor(test_db, code="SG_I3")
        for d in (1, 2, 3):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        _confirmed_sub_with_cash_leg(
            test_db, "SG_P3", "SG_I3", 10000.0, date(2025, 9, 1), date(2025, 9, 2))

        result = recalculate_snapshots(test_db, "SG_P3", date(2025, 9, 2), date(2025, 9, 3))
        assert not result.get("errors"), result
        test_db.commit()

        pos = test_db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == "SG_P3",
            PortfolioPosition.snapshot_date == date(2025, 9, 2),
            PortfolioPosition.product_code == "CASH",
        ).first()
        assert pos is not None
        assert Decimal(str(pos.cash_amount)) == Decimal("10000")


class TestAutoConfirmOutOfOrder:

    def test_out_of_order_sub_fails_not_blocking(self, test_db):
        """乱序早期申购在 auto_confirm 下 fail 为 auto_confirm_failed，不阻断整批"""
        from app.models.portfolio import Portfolio
        from app.services.snapshot_service import auto_confirm_after_snapshot
        create_portfolio(test_db, code="AC_P1", status="active")
        create_investor(test_db, code="AC_I1")
        for d in (1, 2, 3):
            ensure_trading_day(test_db, date(2025, 8, d), is_open=True)
        for d in (1, 2, 3, 4):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        s1 = _confirmed_sub_with_cash_leg(
            test_db, "AC_P1", "AC_I1", 10000.0, date(2025, 9, 1), date(2025, 9, 2))
        p = test_db.query(Portfolio).filter(Portfolio.code == "AC_P1").first()
        p.started_at = s1.confirm_date
        test_db.commit()
        # 乱序 pending 早期申购：confirm=09-01 < started_at=09-02
        s0 = create_subscription(
            test_db, "AC_P1", "AC_I1", sub_type="subscribe", amount=8000.0,
            apply_date=date(2025, 8, 29), confirm_date=date(2025, 9, 1),
            status="pending",
        )

        results = auto_confirm_after_snapshot(test_db, "AC_P1", date(2025, 9, 2))
        failed = [r for r in results if r["id"] == s0.id]
        assert failed and failed[0]["action"] == "auto_confirm_failed"
        assert "首笔到账日" in failed[0]["error"]  # CONFIRM_BEFORE_STARTED 闸门文案
        test_db.refresh(s0)
        assert s0.status == "pending"


class TestSubscriptionUpdate:
    """申赎编辑测试（issue #202：PUT /api/subscriptions/{id} 支持 apply_date 编辑）"""

    def test_update_pending_amount_quantized(self, client, admin_headers, test_db):
        """pending 申购改金额：量化 2 位落库"""
        create_portfolio(test_db, code="UPD_P1", status="active")
        create_investor(test_db, code="UPD_I1")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        sub = create_subscription(
            test_db, "UPD_P1", "UPD_I1", sub_type="subscribe",
            amount=10000.0, apply_date=date(2025, 9, 1),
        )

        resp = client.put(
            f"/api/subscriptions/{sub.id}", json={"amount": 12000.555},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        test_db.refresh(sub)
        assert sub.amount == Decimal("12000.56")  # ROUND_HALF_UP

    def test_update_apply_date_recomputes_confirm_date(self, client, admin_headers, test_db):
        """改申请日：预计确认日按 T+1 重算"""
        create_portfolio(test_db, code="UPD_P2", status="active")
        create_investor(test_db, code="UPD_I2")
        for d in (1, 2, 3):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        sub = create_subscription(
            test_db, "UPD_P2", "UPD_I2", sub_type="subscribe",
            amount=10000.0, apply_date=date(2025, 9, 1),
            confirm_date=date(2025, 9, 2),
        )

        resp = client.put(
            f"/api/subscriptions/{sub.id}", json={"apply_date": "2025-09-02"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        test_db.refresh(sub)
        assert sub.apply_date == date(2025, 9, 2)
        assert sub.confirm_date == date(2025, 9, 3)

    def test_update_apply_date_non_trading_day_rejected(self, client, admin_headers, test_db):
        """改到非交易日拒绝 NON_TRADING_DAY"""
        create_portfolio(test_db, code="UPD_P3", status="active")
        create_investor(test_db, code="UPD_I3")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        ensure_trading_day(test_db, date(2025, 9, 6), is_open=False)
        sub = create_subscription(
            test_db, "UPD_P3", "UPD_I3", sub_type="subscribe",
            amount=10000.0, apply_date=date(2025, 9, 1),
        )

        resp = client.put(
            f"/api/subscriptions/{sub.id}", json={"apply_date": "2025-09-06"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "NON_TRADING_DAY"

    def test_update_apply_date_before_snapshot_rejected(self, client, admin_headers, test_db):
        """改到最新快照日及之前拒绝 DATE_BEFORE_SNAPSHOT"""
        create_portfolio(test_db, code="UPD_P4", status="active")
        create_investor(test_db, code="UPD_I4")
        for d in (1, 2, 3):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        create_value_snapshot(test_db, "UPD_P4", date(2025, 9, 2), 10000, 10000, 1.0)
        sub = create_subscription(
            test_db, "UPD_P4", "UPD_I4", sub_type="subscribe",
            amount=10000.0, apply_date=date(2025, 9, 3),
        )

        resp = client.put(
            f"/api/subscriptions/{sub.id}", json={"apply_date": "2025-09-02"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "DATE_BEFORE_SNAPSHOT"

    def test_update_confirmed_rejected(self, client, admin_headers, test_db):
        """confirmed 拒绝修改 CANNOT_MODIFY_CONFIRMED"""
        create_portfolio(test_db, code="UPD_P5", status="active")
        create_investor(test_db, code="UPD_I5")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        sub = create_subscription(
            test_db, "UPD_P5", "UPD_I5", sub_type="subscribe",
            amount=10000.0, apply_date=date(2025, 9, 1),
            confirm_date=date(2025, 9, 2), status="confirmed",
        )

        resp = client.put(
            f"/api/subscriptions/{sub.id}", json={"amount": 20000.0},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "CANNOT_MODIFY_CONFIRMED"

    def test_update_cancelled_rejected(self, client, admin_headers, test_db):
        """cancelled 拒绝修改 INVALID_STATUS（终态不可复活改值，与 update_trade 同口径）"""
        create_portfolio(test_db, code="UPD_P7", status="active")
        create_investor(test_db, code="UPD_I7")
        ensure_trading_day(test_db, date(2025, 9, 1), is_open=True)
        sub = create_subscription(
            test_db, "UPD_P7", "UPD_I7", sub_type="subscribe",
            amount=10000.0, apply_date=date(2025, 9, 1), status="cancelled",
        )

        resp = client.put(
            f"/api/subscriptions/{sub.id}", json={"apply_date": "2025-09-01"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_STATUS"

    def test_update_redeem_shares_adds_back_own_pending(self, client, admin_headers, test_db):
        """赎回改份额：加回自身 pending 旧份额后与可用份额精确比较"""
        create_portfolio(test_db, code="UPD_P6", status="active")
        create_investor(test_db, code="UPD_I6")
        for d in (1, 2):
            ensure_trading_day(test_db, date(2025, 9, d), is_open=True)
        create_investor_holding(
            test_db, "UPD_P6", "UPD_I6", snapshot_date=date(2025, 9, 1), shares=1000,
        )
        sub = create_subscription(
            test_db, "UPD_P6", "UPD_I6", sub_type="redeem",
            shares=500.0, apply_date=date(2025, 9, 1),
        )

        # 可用 = 1000 - 500(自身) + 500(加回) = 1000，改到 1000 应放行
        resp = client.put(
            f"/api/subscriptions/{sub.id}", json={"shares": 1000},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.json()
        # 超出 1 分即拒 INSUFFICIENT_SHARES（精确比较无容差）
        resp = client.put(
            f"/api/subscriptions/{sub.id}", json={"shares": 1000.01},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_SHARES"
