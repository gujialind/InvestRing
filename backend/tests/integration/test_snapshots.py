# ============================================================================
# 集成测试：快照管理 (test_snapshots.py)
# ============================================================================
# 覆盖批量删除端点的 CONFIRM_REQUIRED 守卫与基本分支。
# ============================================================================

import pytest


class TestSnapshotBulkDeleteGuard:
    """批量删除快照的确认守卫测试"""

    def test_bulk_delete_without_confirm_rejected(self, client, admin_headers, active_portfolio):
        """不带 confirm 参数 → 422 CONFIRM_REQUIRED，不执行删除"""
        resp = client.delete(
            f"/api/v1/snapshots/{active_portfolio.code}/bulk/2025-01-06",
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "CONFIRM_REQUIRED"

    def test_bulk_delete_confirm_false_rejected(self, client, admin_headers, active_portfolio):
        """显式传 confirm=false 同样拒绝"""
        resp = client.delete(
            f"/api/v1/snapshots/{active_portfolio.code}/bulk/2025-01-06",
            params={"confirm": False},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "CONFIRM_REQUIRED"

    def test_bulk_delete_with_confirm_no_snapshots(self, client, admin_headers, active_portfolio):
        """带 confirm=true 且无快照 → 200，deleted_count == 0"""
        resp = client.delete(
            f"/api/v1/snapshots/{active_portfolio.code}/bulk/2025-01-06",
            params={"confirm": True},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["deleted_count"] == 0

    def test_bulk_delete_portfolio_not_found(self, client, admin_headers):
        """组合不存在 → 404"""
        resp = client.delete(
            "/api/v1/snapshots/NO_SUCH_PORT/bulk/2025-01-06",
            params={"confirm": True},
            headers=admin_headers,
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "PORTFOLIO_NOT_FOUND"

    def test_viewer_cannot_bulk_delete(self, client, viewer_headers, active_portfolio):
        """viewer 无权限 → 403"""
        resp = client.delete(
            f"/api/v1/snapshots/{active_portfolio.code}/bulk/2025-01-06",
            params={"confirm": True},
            headers=viewer_headers,
        )
        assert resp.status_code == 403
