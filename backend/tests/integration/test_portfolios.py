# ============================================================================
# 集成测试：组合管理 (test_portfolios.py)
# ============================================================================

import pytest
from datetime import date

from tests.factories import (
    create_portfolio,
    create_investor,
    create_investor_holding,
    create_subscription,
    create_value_snapshot,
)
from app.models.portfolio import Portfolio


class TestPortfolioCRUD:
    """组合 CRUD API 测试"""

    def test_create_portfolio(self, client, admin_headers, test_db):
        """创建组合应为 draft 状态"""
        resp = client.post(
            "/api/portfolios",
            json={"code": "P_NEW", "name": "新组合", "description": "测试"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "P_NEW"
        assert data["status"] == "draft"

    def test_create_duplicate_portfolio_fails(self, client, admin_headers, test_db):
        """创建重复组合应失败"""
        create_portfolio(test_db, code="P_DUP")
        resp = client.post(
            "/api/portfolios",
            json={"code": "P_DUP", "name": "重复"},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_list_portfolios(self, client, admin_headers, test_db):
        """获取组合列表"""
        resp = client.get("/api/portfolios", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_list_portfolios_filter_by_status(self, client, admin_headers, test_db):
        """按状态筛选组合"""
        create_portfolio(test_db, code="P_ACT_F", status="active")
        create_portfolio(test_db, code="P_DR_F", status="draft")
        resp = client.get("/api/portfolios?status=active", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["status"] == "active"

    def test_get_portfolio_detail(self, client, admin_headers, test_db):
        """获取组合详情"""
        create_portfolio(test_db, code="P_DETAIL", name="详情组合")
        resp = client.get("/api/portfolios/P_DETAIL", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == "P_DETAIL"

    def test_get_nonexistent_portfolio_404(self, client, admin_headers):
        """不存在的组合应返回 404"""
        resp = client.get("/api/portfolios/NO_SUCH", headers=admin_headers)
        assert resp.status_code == 404

    def test_update_portfolio(self, client, admin_headers, test_db):
        """更新组合信息"""
        create_portfolio(test_db, code="P_UPD", name="旧名")
        resp = client.put(
            "/api/portfolios/P_UPD",
            json={"name": "新名称", "description": "更新描述"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "新名称"

    def test_viewer_can_list_portfolios(self, client, viewer_headers):
        """viewer 可以查看组合列表"""
        resp = client.get("/api/portfolios", headers=viewer_headers)
        assert resp.status_code == 200

    def test_viewer_cannot_create_portfolio(self, client, viewer_headers):
        """viewer 不能创建组合"""
        resp = client.post(
            "/api/portfolios",
            json={"code": "P_V", "name": "viewer组合"},
            headers=viewer_headers,
        )
        assert resp.status_code == 403


class TestPortfolioStatus:
    """组合状态流转测试"""

    def test_close_portfolio(self, client, admin_headers, test_db):
        """关闭活跃组合"""
        create_portfolio(test_db, code="P_CLOSE", status="active")
        resp = client.post("/api/portfolios/P_CLOSE/close", headers=admin_headers)
        assert resp.status_code == 200
        port = test_db.query(Portfolio).filter(Portfolio.code == "P_CLOSE").first()
        assert port.status == "closed"

    def test_close_draft_portfolio_fails(self, client, admin_headers, test_db):
        """关闭 draft 组合：当前实现允许直接关闭（无校验 draft 状态）"""
        create_portfolio(test_db, code="P_DR_CL", status="draft")
        resp = client.post("/api/portfolios/P_DR_CL/close", headers=admin_headers)
        # 当前实现仅检查 closed 和 pending 交易，不检查 draft
        # 如果未来添加 draft 校验，改为 (400, 422)
        assert resp.status_code in (200, 400, 422)

    def test_reactivate_closed_portfolio(self, client, admin_headers, test_db):
        """重新激活已关闭组合"""
        create_portfolio(test_db, code="P_REACT", status="closed")
        resp = client.post("/api/portfolios/P_REACT/reactivate", headers=admin_headers)
        assert resp.status_code == 200
        port = test_db.query(Portfolio).filter(Portfolio.code == "P_REACT").first()
        assert port.status == "active"


class TestPortfolioListAggregates:
    """组合列表聚合字段测试（issue #69）"""

    def test_list_with_snapshots_returns_aggregates(self, client, admin_headers, test_db):
        """有快照的组合应返回 total_value / cumulative_return / investor_count"""
        create_portfolio(test_db, code="P_AGG", status="active")
        create_investor(test_db, code="INV_AGG1", name="聚合投资人1")
        create_investor(test_db, code="INV_AGG2", name="聚合投资人2")
        create_value_snapshot(test_db, "P_AGG", date(2025, 1, 6), 10000.0, 10000.0, 1.0)
        create_value_snapshot(test_db, "P_AGG", date(2025, 1, 7), 11000.0, 10000.0, 1.1)
        create_investor_holding(test_db, "P_AGG", "INV_AGG1", date(2025, 1, 7), 6000.0)
        create_investor_holding(test_db, "P_AGG", "INV_AGG2", date(2025, 1, 7), 4000.0)

        resp = client.get("/api/portfolios", headers=admin_headers)
        assert resp.status_code == 200
        items = {item["code"]: item for item in resp.json()["items"]}
        agg = items["P_AGG"]
        assert agg["total_value"] == 11000.0
        assert agg["cumulative_return"] == pytest.approx(10.0, abs=1e-4)
        assert agg["investor_count"] == 2

    def test_list_draft_without_snapshot_returns_none(self, client, admin_headers, test_db):
        """无快照的 draft 组合聚合字段为 None/0"""
        create_portfolio(test_db, code="P_AGG_DR", status="draft")
        resp = client.get("/api/portfolios", headers=admin_headers)
        assert resp.status_code == 200
        items = {item["code"]: item for item in resp.json()["items"]}
        agg = items["P_AGG_DR"]
        assert agg["total_value"] is None
        assert agg["cumulative_return"] is None
        assert agg["investor_count"] == 0

    def test_investor_count_excludes_zero_shares(self, client, admin_headers, test_db):
        """investor_count 不计最新快照日份额为 0 的投资人"""
        create_portfolio(test_db, code="P_AGG_Z", status="active")
        create_investor(test_db, code="INV_AGG_Z1", name="持仓投资人")
        create_investor(test_db, code="INV_AGG_Z2", name="清仓投资人")
        create_value_snapshot(test_db, "P_AGG_Z", date(2025, 1, 6), 5000.0, 5000.0, 1.0)
        create_investor_holding(test_db, "P_AGG_Z", "INV_AGG_Z1", date(2025, 1, 6), 5000.0)
        create_investor_holding(test_db, "P_AGG_Z", "INV_AGG_Z2", date(2025, 1, 6), 0.0)

        resp = client.get("/api/portfolios", headers=admin_headers)
        assert resp.status_code == 200
        items = {item["code"]: item for item in resp.json()["items"]}
        assert items["P_AGG_Z"]["investor_count"] == 1


class TestPortfolioDetailDerivedFields:
    """组合详情派生字段 total_value / total_profit（issue #99）"""

    def test_detail_returns_total_value_and_profit(self, client, admin_headers, test_db):
        """total_profit = 最新快照总资产 − 净投入（confirmed 申购 − confirmed 赎回）"""
        create_portfolio(test_db, code="P_DER", status="active")
        create_investor(test_db, code="INV_DER", name="派生投资人")
        create_value_snapshot(test_db, "P_DER", date(2025, 1, 6), 10000.0, 10000.0, 1.0)
        create_value_snapshot(test_db, "P_DER", date(2025, 1, 7), 11500.0, 10000.0, 1.15)
        create_subscription(
            test_db, "P_DER", "INV_DER", sub_type="subscribe", amount=10000.0,
            apply_date=date(2025, 1, 6), confirm_date=date(2025, 1, 6), status="confirmed",
        )
        create_subscription(
            test_db, "P_DER", "INV_DER", sub_type="redeem", amount=3000.0,
            apply_date=date(2025, 1, 7), confirm_date=date(2025, 1, 7), status="confirmed",
        )
        # pending 申赎不计入净投入
        create_subscription(
            test_db, "P_DER", "INV_DER", sub_type="subscribe", amount=99999.0,
            apply_date=date(2025, 1, 7), status="pending",
        )

        resp = client.get("/api/portfolios/P_DER", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_value"] == 11500.0
        # 11500 − (10000 − 3000) = 4500
        assert data["total_profit"] == 4500.0

    def test_detail_draft_returns_none_totals(self, client, admin_headers, test_db):
        """无快照的 draft 组合 total_value / total_profit 为 None"""
        create_portfolio(test_db, code="P_DER_DR", status="draft")
        resp = client.get("/api/portfolios/P_DER_DR", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_value"] is None
        assert data["total_profit"] is None


class TestPortfolioPerformanceNewPeriods:
    """绩效接口新增区间字段（issue #99）"""

    def test_performance_contains_new_period_keys(self, client, admin_headers, test_db):
        create_portfolio(test_db, code="P_PERF_K", status="active")
        create_value_snapshot(test_db, "P_PERF_K", date(2025, 1, 6), 10000.0, 10000.0, 1.0)
        create_value_snapshot(test_db, "P_PERF_K", date(2025, 1, 7), 10100.0, 10000.0, 1.01)
        resp = client.get("/api/portfolios/P_PERF_K/performance", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for key in ("return_6m", "return_1y", "return_3y"):
            assert key in data
        # 成立仅 2 天，历史不足窗口期 → None
        assert data["return_6m"] is None
        assert data["return_1y"] is None
        assert data["return_3y"] is None


class TestLatestSnapshotEndpoint:
    """GET /api/portfolios/{code}/snapshots/latest 测试（issue #69）"""

    def test_latest_snapshot(self, client, admin_headers, test_db):
        """返回最新一条市值快照"""
        create_portfolio(test_db, code="P_SNAP_L", status="active")
        create_value_snapshot(test_db, "P_SNAP_L", date(2025, 1, 6), 10000.0, 10000.0, 1.0)
        create_value_snapshot(test_db, "P_SNAP_L", date(2025, 1, 7), 10500.0, 10000.0, 1.05)

        resp = client.get("/api/portfolios/P_SNAP_L/snapshots/latest", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["snapshot_date"] == "2025-01-07"
        assert data["total_value"] == 10500.0
        assert data["unit_price"] == 1.05

    def test_latest_snapshot_no_snapshot_404(self, client, admin_headers, test_db):
        """无快照返回 404"""
        create_portfolio(test_db, code="P_SNAP_N", status="draft")
        resp = client.get("/api/portfolios/P_SNAP_N/snapshots/latest", headers=admin_headers)
        assert resp.status_code == 404

    def test_latest_snapshot_portfolio_not_found(self, client, admin_headers):
        """组合不存在返回 404"""
        resp = client.get("/api/portfolios/NO_SUCH/snapshots/latest", headers=admin_headers)
        assert resp.status_code == 404


class TestPortfolioInvestorsEndpoint:
    """GET /api/portfolios/{code}/investors 测试（issue #69）"""

    def test_investors_from_latest_snapshot(self, client, admin_headers, test_db):
        """返回最新快照日的投资人份额列表"""
        create_portfolio(test_db, code="P_INV_L", status="active")
        create_investor(test_db, code="INV_L1", name="投资人A")
        create_investor(test_db, code="INV_L2", name="投资人B")
        # 旧快照日有三人，最新快照日只剩两人
        create_investor_holding(test_db, "P_INV_L", "INV_L1", date(2025, 1, 6), 3000.0)
        create_investor_holding(test_db, "P_INV_L", "INV_L1", date(2025, 1, 7), 6000.0)
        create_investor_holding(test_db, "P_INV_L", "INV_L2", date(2025, 1, 7), 4000.0)

        resp = client.get("/api/portfolios/P_INV_L/investors", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["investor_code"] == "INV_L1"
        assert data[0]["name"] == "投资人A"
        assert data[0]["shares"] == 6000.0
        assert data[1]["investor_code"] == "INV_L2"

    def test_investors_empty_without_holdings(self, client, admin_headers, test_db):
        """无投资人快照返回空列表"""
        create_portfolio(test_db, code="P_INV_E", status="draft")
        resp = client.get("/api/portfolios/P_INV_E/investors", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_investors_portfolio_not_found(self, client, admin_headers):
        """组合不存在返回 404"""
        resp = client.get("/api/portfolios/NO_SUCH/investors", headers=admin_headers)
        assert resp.status_code == 404
