# ============================================================================
# 集成测试：快照管理 (test_snapshots.py)
# ============================================================================
# 覆盖批量删除端点的 CONFIRM_REQUIRED 守卫与基本分支。
# 覆盖单日生成的快照连续性校验（#55 SNAPSHOT_NOT_CONTINUOUS）。
# ============================================================================

from datetime import date

import pytest

from app.models import PortfolioValueSnapshot
from tests.factories import (
    create_portfolio,
    create_position_snapshot,
    create_value_snapshot,
    create_investor_holding,
)


def _setup_cash_snapshot(db, portfolio_code: str, snapshot_date: date, amount: float = 10000.0):
    """为组合制造指定日的完整三表快照（仅 CASH 持仓，无需行情数据）"""
    create_position_snapshot(
        db, portfolio_code, "CASH", "",
        snapshot_date=snapshot_date,
        amount=amount, unit_price=None, cost_price=None,
        market_value=amount, platform_code="MYCF", asset_type="cash",
    )
    create_value_snapshot(
        db, portfolio_code, snapshot_date,
        total_value=amount, total_shares=amount, unit_price=1.0,
    )
    create_investor_holding(
        db, portfolio_code, "VIEWER", snapshot_date, shares=amount,
    )


class TestSnapshotContinuity:
    """单日生成快照的连续性校验（#55）

    日期基于 conftest 交易日历（工作日均为交易日）：
    - D0 = 2025-06-06（周五）
    - 下一交易日 = 2025-06-09（周一）
    - 跳日目标 = 2025-06-10（周二）
    """

    D0 = date(2025, 6, 6)
    NEXT_DAY = date(2025, 6, 9)
    SKIP_DAY = date(2025, 6, 10)

    def _portfolio(self, db, code="SNAP_CONT"):
        return create_portfolio(db, code=code, status="active")

    def test_generate_skip_day_rejected(self, client, admin_headers, test_db):
        """跳过紧邻交易日直接生成 → 422 SNAPSHOT_NOT_CONTINUOUS，不产生空洞"""
        port = self._portfolio(test_db)
        _setup_cash_snapshot(test_db, port.code, self.D0)

        resp = client.post(
            "/api/v1/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": self.SKIP_DAY.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "SNAPSHOT_NOT_CONTINUOUS"

        # 未生成跳日快照
        assert test_db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == port.code,
            PortfolioValueSnapshot.snapshot_date == self.SKIP_DAY,
        ).first() is None

    def test_generate_next_trading_day_ok(self, client, admin_headers, test_db):
        """顺延生成下一交易日 → 成功"""
        port = self._portfolio(test_db, code="SNAP_NEXT")
        _setup_cash_snapshot(test_db, port.code, self.D0)

        resp = client.post(
            "/api/v1/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": self.NEXT_DAY.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert test_db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == port.code,
            PortfolioValueSnapshot.snapshot_date == self.NEXT_DAY,
        ).first() is not None

    def test_generate_rebuild_latest_ok(self, client, admin_headers, test_db):
        """重建最新一日（target_date == 最新快照日）→ 成功"""
        port = self._portfolio(test_db, code="SNAP_LATEST")
        _setup_cash_snapshot(test_db, port.code, self.D0)

        resp = client.post(
            "/api/v1/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": self.D0.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_generate_mid_day_rejected(self, client, admin_headers, test_db):
        """重建其后仍有快照的中间日 → 422 SNAPSHOT_NOT_CONTINUOUS（应走 recalculate）"""
        port = self._portfolio(test_db, code="SNAP_MID")
        _setup_cash_snapshot(test_db, port.code, self.D0)
        _setup_cash_snapshot(test_db, port.code, self.NEXT_DAY)

        resp = client.post(
            "/api/v1/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": self.D0.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "SNAPSHOT_NOT_CONTINUOUS"

    def test_first_snapshot_no_continuity_restriction(self, client, admin_headers, test_db):
        """无任何快照时首次生成 → 不因连续性被拒（无持仓时返回跳过）"""
        port = self._portfolio(test_db, code="SNAP_FIRST")

        resp = client.post(
            "/api/v1/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": self.D0.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_recalculate_bypasses_continuity(self, client, admin_headers, test_db):
        """重算覆盖已有快照区间（逐日重建时其后快照仍存在）不受连续性校验阻断"""
        port = self._portfolio(test_db, code="SNAP_RECALC")
        _setup_cash_snapshot(test_db, port.code, self.D0)
        _setup_cash_snapshot(test_db, port.code, self.NEXT_DAY)

        resp = client.post(
            "/api/v1/snapshots/recalculate",
            json={
                "portfolio_code": port.code,
                "start_date": self.D0.isoformat(),
                "end_date": self.NEXT_DAY.isoformat(),
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        errors = data["results"][0]["errors"]
        assert not any("SNAPSHOT_NOT_CONTINUOUS" in str(e) for e in errors)


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
