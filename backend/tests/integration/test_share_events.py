# ============================================================================
# 集成测试：份额变动事件 (test_share_events.py)
# ============================================================================

import pytest
from datetime import date, datetime
from decimal import Decimal

from tests.factories import (
    create_portfolio, create_product, create_platform,
    create_share_change_event, create_position_snapshot,
    create_value_snapshot, ensure_trading_day,
)
from app.models.share_change_event import ShareChangeEvent


class TestShareChangeEventCreate:
    """份额变动事件创建测试"""

    def test_create_cash_dividend_event(self, client, admin_headers, test_db):
        """创建现金分红事件"""
        create_portfolio(test_db, code="SCE_P1", status="active")
        create_product(test_db, code="FUND_SC1", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
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
                "platform_code": "MYCF",  # 平台级事件必填
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
                       product_type="OEF", asset_class_code="ASSET_STOCK")
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
                "platform_code": "MYCF",  # 平台级事件必填
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["event_type"] == "reinvest_dividend"

    def test_create_share_split_event(self, client, admin_headers, test_db):
        """创建份额拆分事件"""
        create_portfolio(test_db, code="SCE_P3", status="active")
        create_product(test_db, code="FUND_SC3", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
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
                       product_type="OEF", asset_class_code="ASSET_STOCK")
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
                "platform_code": "MYCF",  # 平台级事件必填
            },
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)

    def test_platform_coverage_default_blocked(self, client, admin_headers, test_db):
        """#40 改进3：多平台持仓只录 1 平台 → 默认阻断 PLATFORM_NOT_COVERED"""
        create_portfolio(test_db, code="SCE_FC1", status="active")
        create_product(test_db, code="FUND_FC1", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        ensure_trading_day(test_db, date(2025, 12, 8), is_open=True)
        # 2 平台均有持仓
        create_position_snapshot(
            test_db, portfolio_code="SCE_FC1", product_code="FUND_FC1",
            market="CN_OTC", snapshot_date=date(2025, 12, 8),
            shares=100.0, platform_code="MYCF", market_value=100.0,
        )
        create_position_snapshot(
            test_db, portfolio_code="SCE_FC1", product_code="FUND_FC1",
            market="CN_OTC", snapshot_date=date(2025, 12, 8),
            shares=200.0, platform_code="HBZQ", market_value=200.0,
        )
        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "SCE_FC1",
                "product_code": "FUND_FC1",
                "market": "CN_OTC",
                "event_type": "cash_dividend",
                "ex_date": "2025-12-10",
                "entitlement_date": "2025-12-08",
                "event_source": "manual",
                "div_cash": 0.5,
                "platform_code": "MYCF",  # 只覆盖 MYCF，HBZQ 未覆盖
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "PLATFORM_NOT_COVERED"

    def test_force_cover_allows_creation(self, client, admin_headers, test_db):
        """#40 改进3：force_cover=true 降为 warning，创建成功"""
        create_portfolio(test_db, code="SCE_FC2", status="active")
        create_product(test_db, code="FUND_FC2", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        ensure_trading_day(test_db, date(2025, 12, 8), is_open=True)
        create_position_snapshot(
            test_db, portfolio_code="SCE_FC2", product_code="FUND_FC2",
            market="CN_OTC", snapshot_date=date(2025, 12, 8),
            shares=100.0, platform_code="MYCF", market_value=100.0,
        )
        create_position_snapshot(
            test_db, portfolio_code="SCE_FC2", product_code="FUND_FC2",
            market="CN_OTC", snapshot_date=date(2025, 12, 8),
            shares=200.0, platform_code="HBZQ", market_value=200.0,
        )
        resp = client.post(
            "/api/share-change-events?force_cover=true",
            json={
                "portfolio_code": "SCE_FC2",
                "product_code": "FUND_FC2",
                "market": "CN_OTC",
                "event_type": "cash_dividend",
                "ex_date": "2025-12-10",
                "entitlement_date": "2025-12-08",
                "event_source": "manual",
                "div_cash": 0.5,
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["status"] == "pending"


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
                       product_type="OEF", asset_class_code="ASSET_STOCK")
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


class TestShareChangeEventUnconfirm:
    """#38 份额变动事件 unconfirm 接口"""

    def _seed_confirmed_platform_event(self, test_db, portfolio_code="SCE_UNC",
                                        platform_code="SCE_PLAT"):
        create_portfolio(test_db, code=portfolio_code, status="active")
        create_product(test_db, code="FUND_UNC", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code=platform_code)
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 10, 8), is_open=True)
        create_value_snapshot(test_db, portfolio_code, date(2025, 10, 6),
                              total_value=1000, total_shares=1000, unit_price=1.0)
        create_position_snapshot(
            test_db, portfolio_code, "FUND_UNC", "CN_OTC", date(2025, 10, 6),
            shares=1000, platform_code=platform_code,
        )
        event = create_share_change_event(
            test_db, portfolio_code, "FUND_UNC", "CN_OTC",
            event_type="cash_dividend", ex_date=date(2025, 10, 8),
            entitlement_date=date(2025, 10, 6), status="pending",
            platform_code=platform_code, div_cash=Decimal("0.1"),
        )
        event.entitlement_shares = Decimal("1000")
        event.shares_before = Decimal("1000")
        event.cash_change = Decimal("100")
        event.shares_change = Decimal("0")
        event.shares_after = Decimal("1000")
        event.status = "confirmed"
        event.confirmed_at = datetime.now()
        test_db.commit()
        return event

    def test_unconfirm_platform_event_success(self, client, admin_headers, test_db):
        """平台级事件 unconfirm 成功，计算字段清空"""
        event = self._seed_confirmed_platform_event(test_db)
        resp = client.post(
            f"/api/share-change-events/{event.id}/unconfirm",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        test_db.expire_all()
        updated = test_db.query(ShareChangeEvent).get(event.id)
        assert updated.status == "pending"
        assert updated.confirmed_at is None
        assert updated.cash_change is None
        assert updated.entitlement_shares is None

    def test_unconfirm_blocked_by_snapshot(self, client, admin_headers, test_db):
        """ex_date 及之后已有快照时拒绝（SNAPSHOT_DEPENDENCY）"""
        event = self._seed_confirmed_platform_event(test_db)
        # 在 ex_date 上生成快照
        create_value_snapshot(test_db, "SCE_UNC", date(2025, 10, 8),
                              total_value=1100, total_shares=1000, unit_price=1.1)
        resp = client.post(
            f"/api/share-change-events/{event.id}/unconfirm",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "SNAPSHOT_DEPENDENCY"

    def test_unconfirm_fund_level_cascades_children(self, client, admin_headers, test_db):
        """基金级父记录 unconfirm 级联删除所有子记录"""
        create_portfolio(test_db, code="SCE_FL", status="active")
        create_product(test_db, code="FUND_FL", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="FL_P1")
        create_platform(test_db, code="FL_P2")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 10, 8), is_open=True)
        create_value_snapshot(test_db, "SCE_FL", date(2025, 10, 6),
                              total_value=2000, total_shares=2000, unit_price=1.0)
        create_position_snapshot(
            test_db, "SCE_FL", "FUND_FL", "CN_OTC", date(2025, 10, 6),
            shares=1000, platform_code="FL_P1",
        )
        create_position_snapshot(
            test_db, "SCE_FL", "FUND_FL", "CN_OTC", date(2025, 10, 6),
            shares=1000, platform_code="FL_P2",
        )
        # 父记录
        parent = create_share_change_event(
            test_db, "SCE_FL", "FUND_FL", "CN_OTC",
            event_type="share_split", ex_date=date(2025, 10, 8),
            entitlement_date=date(2025, 10, 6), status="confirmed",
            ratio=2.0,
        )
        # 两个子记录
        for plat in ("FL_P1", "FL_P2"):
            child = create_share_change_event(
                test_db, "SCE_FL", "FUND_FL", "CN_OTC",
                event_type="share_split", ex_date=date(2025, 10, 8),
                entitlement_date=date(2025, 10, 6), status="confirmed",
                platform_code=plat, ratio=2.0, parent_event_id=parent.id,
                entitlement_shares=Decimal("1000"), shares_before=Decimal("1000"),
                shares_change=Decimal("1000"), shares_after=Decimal("2000"),
            )
        before = test_db.query(ShareChangeEvent).filter(
            ShareChangeEvent.parent_event_id == parent.id
        ).count()
        assert before == 2

        resp = client.post(
            f"/api/share-change-events/{parent.id}/unconfirm",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        test_db.expire_all()
        after = test_db.query(ShareChangeEvent).filter(
            ShareChangeEvent.parent_event_id == parent.id
        ).count()
        assert after == 0
        updated = test_db.query(ShareChangeEvent).get(parent.id)
        assert updated.status == "pending"

    def test_unconfirm_child_rejected(self, client, admin_headers, test_db):
        """子记录单独 unconfirm 拒绝（CANNOT_UNCONFIRM_CHILD）"""
        create_portfolio(test_db, code="SCE_CH", status="active")
        create_product(test_db, code="FUND_CH", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="CH_P1")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 10, 8), is_open=True)
        create_value_snapshot(test_db, "SCE_CH", date(2025, 10, 6),
                              total_value=1000, total_shares=1000, unit_price=1.0)
        create_position_snapshot(
            test_db, "SCE_CH", "FUND_CH", "CN_OTC", date(2025, 10, 6),
            shares=1000, platform_code="CH_P1",
        )
        parent = create_share_change_event(
            test_db, "SCE_CH", "FUND_CH", "CN_OTC",
            event_type="share_split", ex_date=date(2025, 10, 8),
            entitlement_date=date(2025, 10, 6), status="confirmed", ratio=2.0,
        )
        child = create_share_change_event(
            test_db, "SCE_CH", "FUND_CH", "CN_OTC",
            event_type="share_split", ex_date=date(2025, 10, 8),
            entitlement_date=date(2025, 10, 6), status="confirmed",
            platform_code="CH_P1", ratio=2.0, parent_event_id=parent.id,
            entitlement_shares=Decimal("1000"), shares_before=Decimal("1000"),
            shares_change=Decimal("1000"), shares_after=Decimal("2000"),
        )
        resp = client.post(
            f"/api/share-change-events/{child.id}/unconfirm",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "CANNOT_UNCONFIRM_CHILD"

    def test_unconfirm_only_confirmed_allowed(self, client, admin_headers, test_db):
        """仅 confirmed 状态可 unconfirm"""
        create_portfolio(test_db, code="SCE_PD", status="active")
        create_product(test_db, code="FUND_PD", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="PD_P1")
        ensure_trading_day(test_db, date(2025, 10, 6), is_open=True)
        ensure_trading_day(test_db, date(2025, 10, 8), is_open=True)
        create_value_snapshot(test_db, "SCE_PD", date(2025, 10, 6),
                              total_value=1000, total_shares=1000, unit_price=1.0)
        create_position_snapshot(
            test_db, "SCE_PD", "FUND_PD", "CN_OTC", date(2025, 10, 6),
            shares=1000, platform_code="PD_P1",
        )
        event = create_share_change_event(
            test_db, "SCE_PD", "FUND_PD", "CN_OTC",
            event_type="cash_dividend", ex_date=date(2025, 10, 8),
            entitlement_date=date(2025, 10, 6), status="pending",
            platform_code="PD_P1", div_cash=Decimal("0.1"),
        )
        resp = client.post(
            f"/api/share-change-events/{event.id}/unconfirm",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_STATUS"


class TestUpdateShareChangeEvent:
    """PUT 更新事件：confirmed 阻断、日期重校验、status 直改忽略"""

    def test_update_confirmed_event_rejected(self, client, admin_headers, test_db):
        """confirmed 事件不可直接修改，须先 unconfirm"""
        create_portfolio(test_db, code="UPE_P1", status="active")
        create_product(test_db, code="FUND_UPE1", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="UPE_PLAT1")
        ensure_trading_day(test_db, date(2025, 11, 10), is_open=True)
        ensure_trading_day(test_db, date(2025, 11, 12), is_open=True)
        event = create_share_change_event(
            test_db, "UPE_P1", "FUND_UPE1", "CN_OTC",
            event_type="cash_dividend", ex_date=date(2025, 11, 12),
            entitlement_date=date(2025, 11, 10), status="confirmed",
            platform_code="UPE_PLAT1", div_cash=Decimal("0.1"),
        )

        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"notes": "try modify confirmed"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "CANNOT_MODIFY_CONFIRMED"

    def test_update_pending_event_dates_revalidated(self, client, admin_headers, test_db):
        """pending 事件改日期时重跑创建时的双日期校验"""
        create_portfolio(test_db, code="UPE_P2", status="active")
        create_product(test_db, code="FUND_UPE2", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="UPE_PLAT2")
        ensure_trading_day(test_db, date(2025, 11, 10), is_open=True)
        ensure_trading_day(test_db, date(2025, 11, 12), is_open=True)
        ensure_trading_day(test_db, date(2025, 11, 15), is_open=False)  # 周六
        event = create_share_change_event(
            test_db, "UPE_P2", "FUND_UPE2", "CN_OTC",
            event_type="cash_dividend", ex_date=date(2025, 11, 12),
            entitlement_date=date(2025, 11, 10), status="pending",
            platform_code="UPE_PLAT2", div_cash=Decimal("0.1"),
        )

        # 除息日非交易日
        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"ex_date": "2025-11-15"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_EX_DATE"

        # 除息日 <= 权益登记日
        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"ex_date": "2025-11-10"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DATE_ORDER"

        # 除息日 <= 最新快照日
        create_value_snapshot(test_db, "UPE_P2", date(2025, 11, 14),
                              total_value=1000, total_shares=1000, unit_price=1.0)
        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"ex_date": "2025-11-13"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "DATE_BEFORE_SNAPSHOT"

        # 合法新日期（交易日、晚于登记日与最新快照日）可正常更新
        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"ex_date": "2025-11-17"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        test_db.expire_all()
        updated = test_db.query(ShareChangeEvent).get(event.id)
        assert updated.ex_date == date(2025, 11, 17)

    def test_update_status_field_ignored(self, client, admin_headers, test_db):
        """PUT 传 status 被忽略（状态流转只走 confirm/cancel/unconfirm 端点）"""
        create_portfolio(test_db, code="UPE_P3", status="active")
        create_product(test_db, code="FUND_UPE3", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        create_platform(test_db, code="UPE_PLAT3")
        ensure_trading_day(test_db, date(2025, 11, 10), is_open=True)
        ensure_trading_day(test_db, date(2025, 11, 12), is_open=True)
        event = create_share_change_event(
            test_db, "UPE_P3", "FUND_UPE3", "CN_OTC",
            event_type="cash_dividend", ex_date=date(2025, 11, 12),
            entitlement_date=date(2025, 11, 10), status="pending",
            platform_code="UPE_PLAT3", div_cash=Decimal("0.1"),
        )

        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"status": "confirmed", "notes": "n1"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        test_db.expire_all()
        updated = test_db.query(ShareChangeEvent).get(event.id)
        # status 字段被 schema 忽略，仍为 pending；其余合法字段正常更新
        assert updated.status == "pending"
        assert updated.notes == "n1"


class TestForcedAdjustmentInputValidation:
    """issue #279：forced_adjustment 双空字段与现金型产品份额变动的输入校验"""

    ENT = date(2025, 12, 8)   # 权益登记日（周一）
    EX = date(2025, 12, 10)   # 除息日（周三）

    def _setup(self, test_db, port_code: str):
        create_portfolio(test_db, code=port_code, status="active")
        ensure_trading_day(test_db, self.ENT, is_open=True)
        ensure_trading_day(test_db, self.EX, is_open=True)

    def test_create_double_empty_adjustment_rejected(self, client, admin_headers, test_db):
        """验收：双空 forced_adjustment 创建即拒绝且不落库"""
        self._setup(test_db, "FAV_P1")
        create_product(test_db, code="FUND_FAV1", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")

        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "FAV_P1",
                "product_code": "FUND_FAV1",
                "market": "CN_OTC",
                "event_type": "forced_adjustment",
                "ex_date": self.EX.isoformat(),
                "entitlement_date": self.ENT.isoformat(),
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "EMPTY_ADJUSTMENT"
        assert test_db.query(ShareChangeEvent).filter(
            ShareChangeEvent.portfolio_code == "FAV_P1"
        ).count() == 0

        # 正向对照：只填一项照常创建
        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "FAV_P1",
                "product_code": "FUND_FAV1",
                "market": "CN_OTC",
                "event_type": "forced_adjustment",
                "ex_date": self.EX.isoformat(),
                "entitlement_date": self.ENT.isoformat(),
                "platform_code": "MYCF",
                "shares_change": 1.0,
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)

    def test_update_to_double_empty_rejected(self, client, admin_headers, test_db):
        """验收：PUT 改成双空被拒（封死 update 绕过）"""
        self._setup(test_db, "FAV_P2")
        create_product(test_db, code="FUND_FAV2", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        event = create_share_change_event(
            test_db, "FAV_P2", "FUND_FAV2", "CN_OTC",
            event_type="forced_adjustment", ex_date=self.EX,
            entitlement_date=self.ENT, status="pending",
            platform_code="MYCF", shares_change=Decimal("1.00"),
        )

        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"shares_change": None},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "EMPTY_ADJUSTMENT"

        # 正常单字段更新不受影响（回归）
        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"notes": "adjust"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_create_shares_change_on_cash_product_rejected(self, client, admin_headers, test_db):
        """验收：CASH / IN_TRANSIT 产品录入含 shares_change 的事件被拒"""
        self._setup(test_db, "FAV_P3")

        for product_code in ("CASH", "IN_TRANSIT_BUY"):
            resp = client.post(
                "/api/share-change-events",
                json={
                    "portfolio_code": "FAV_P3",
                    "product_code": product_code,
                    "market": "",
                    "event_type": "forced_adjustment",
                    "ex_date": self.EX.isoformat(),
                    "entitlement_date": self.ENT.isoformat(),
                    "platform_code": "MYCF",
                    "shares_change": 1.0,
                },
                headers=admin_headers,
            )
            assert resp.status_code == 422, product_code
            assert resp.json()["detail"]["error"] == "SHARES_CHANGE_ON_CASH_PRODUCT", product_code

    def test_create_structural_event_on_cash_product_rejected(self, client, admin_headers, test_db):
        """结构上必产生份额变动的事件类型在现金型产品上无条件拒绝"""
        self._setup(test_db, "FAV_P4")

        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "FAV_P4",
                "product_code": "CASH",
                "market": "",
                "event_type": "share_split",
                "ex_date": self.EX.isoformat(),
                "entitlement_date": self.ENT.isoformat(),
                "ratio": 2.0,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "SHARES_CHANGE_ON_CASH_PRODUCT"

    def test_cash_only_adjustment_on_cash_product_allowed(self, client, admin_headers, test_db):
        """边界：现金型产品上的纯现金调整（无份额语义）仍放行"""
        self._setup(test_db, "FAV_P5")

        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "FAV_P5",
                "product_code": "CASH",
                "market": "",
                "event_type": "forced_adjustment",
                "ex_date": self.EX.isoformat(),
                "entitlement_date": self.ENT.isoformat(),
                "platform_code": "MYCF",
                "cash_change": -5.0,
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)

    def test_confirm_fallback_validation(self, test_db):
        """验收：确认侧兜底——绕过创建入口直造的脏事件在确认时被拒"""
        from app.services.exceptions import BusinessError
        from app.services.share_change_event_service import confirm_share_change_event

        self._setup(test_db, "FAV_P6")
        create_product(test_db, code="FUND_FAV6", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")

        # 双空 pending（模拟存量脏数据）
        empty_event = create_share_change_event(
            test_db, "FAV_P6", "FUND_FAV6", "CN_OTC",
            event_type="forced_adjustment", ex_date=self.EX,
            entitlement_date=self.ENT, status="pending",
            platform_code="MYCF",
        )
        with pytest.raises(BusinessError) as exc:
            confirm_share_change_event(test_db, empty_event)
        assert exc.value.code == "EMPTY_ADJUSTMENT"

        # 现金型产品带份额变动（模拟存量脏数据）
        cash_event = create_share_change_event(
            test_db, "FAV_P6", "CASH", "",
            event_type="forced_adjustment", ex_date=self.EX,
            entitlement_date=self.ENT, status="pending",
            platform_code="MYCF", shares_change=Decimal("1.00"),
        )
        with pytest.raises(BusinessError) as exc:
            confirm_share_change_event(test_db, cash_event)
        assert exc.value.code == "SHARES_CHANGE_ON_CASH_PRODUCT"

    def test_update_clears_shares_change_on_cash_product_allowed(self, client, admin_headers, test_db):
        """边界：现金型产品存量脏事件（带份额变动）经 PUT 清 null 修正放行"""
        self._setup(test_db, "FAV_P7")
        event = create_share_change_event(
            test_db, "FAV_P7", "CASH", "",
            event_type="forced_adjustment", ex_date=self.EX,
            entitlement_date=self.ENT, status="pending",
            platform_code="MYCF", shares_change=Decimal("1.00"),
            cash_change=Decimal("-5.00"),
        )

        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"shares_change": None},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        test_db.refresh(event)
        assert event.shares_change is None
        assert Decimal(str(event.cash_change)) == Decimal("-5.00")

    def test_update_fills_shares_change_on_cash_product_rejected(self, client, admin_headers, test_db):
        """验收：PUT 给现金型产品补填 shares_change 同样被拒（封死 update 绕过）"""
        self._setup(test_db, "FAV_P8")
        event = create_share_change_event(
            test_db, "FAV_P8", "CASH", "",
            event_type="forced_adjustment", ex_date=self.EX,
            entitlement_date=self.ENT, status="pending",
            platform_code="MYCF", cash_change=Decimal("-5.00"),
        )

        resp = client.put(
            f"/api/share-change-events/{event.id}",
            json={"shares_change": 2.0},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "SHARES_CHANGE_ON_CASH_PRODUCT"

    def test_reinvest_dividend_on_cash_product_rejected(self, client, admin_headers, test_db):
        """结构型成员完整性：reinvest_dividend（唯一平台级结构型）在现金型产品上无条件拒"""
        self._setup(test_db, "FAV_P9")

        resp = client.post(
            "/api/share-change-events",
            json={
                "portfolio_code": "FAV_P9",
                "product_code": "CASH",
                "market": "",
                "event_type": "reinvest_dividend",
                "ex_date": self.EX.isoformat(),
                "entitlement_date": self.ENT.isoformat(),
                "div_cash": 0.5,
                "reinvest_nav": 1.2,
                "platform_code": "MYCF",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "SHARES_CHANGE_ON_CASH_PRODUCT"
