# ============================================================================
# 集成测试：快照负现金 warning（issue #71）
# ============================================================================
# 覆盖：
# - generate_daily_snapshots 负现金日返回 negative_cash warning 且快照正常落库
# - 正常场景 warnings 为 None
# - recalculate 区间含负现金日时对应 result 带 warnings 且整体成功
# - status 端点返回 negative_cash_platforms（负现金平台列出、正常为空）
# ============================================================================

from datetime import date
from decimal import Decimal

from app.models import PortfolioPosition, PortfolioValueSnapshot
from tests.factories import (
    create_portfolio,
    create_position_snapshot,
    create_value_snapshot,
    create_investor_holding,
    create_trade,
)


def _setup_cash_snapshot(db, portfolio_code: str, snapshot_date: date, amount: float = 1000.0):
    """为组合制造指定日的完整三表快照（仅 CASH 持仓，无需行情数据）"""
    create_position_snapshot(
        db, portfolio_code, "CASH", "",
        snapshot_date=snapshot_date,
        cash_amount=amount, unit_price=None, cost_price=None,
        market_value=amount, platform_code="MYCF",
    )
    create_value_snapshot(
        db, portfolio_code, snapshot_date,
        total_value=amount, total_shares=amount, unit_price=1.0,
    )
    create_investor_holding(
        db, portfolio_code, "VIEWER", snapshot_date, shares=amount,
    )


class TestGenerateNegativeCashWarning:
    """单日生成快照的负现金 warning（issue #71）

    日期基于 conftest 交易日历（工作日均为交易日）：
    - D0 = 2025-06-06（周五）
    - 下一交易日 = 2025-06-09（周一）
    """

    D0 = date(2025, 6, 6)
    NEXT_DAY = date(2025, 6, 9)

    def test_negative_cash_warns_and_persists(self, client, admin_headers, test_db):
        """confirmed CASH sell 使现金转负 → warnings 含 negative_cash，快照仍落库"""
        port = create_portfolio(test_db, code="NEGC_GEN", status="active")
        _setup_cash_snapshot(test_db, port.code, self.D0, amount=1000.0)
        # 窗口内 confirmed CASH sell 3000 → 1000 - 3000 = -2000
        create_trade(
            test_db, port.code, "CASH", "",
            trade_type="sell", amount=3000.0, price=None,
            platform_code="MYCF", trade_date=self.NEXT_DAY,
            confirm_date=self.NEXT_DAY, status="confirmed",
        )

        resp = client.post(
            "/api/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": self.NEXT_DAY.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # warnings 含 negative_cash 条目
        assert data["warnings"], "负现金日应返回 warnings"
        neg = [w for w in data["warnings"] if w["type"] == "negative_cash"]
        assert len(neg) == 1
        assert neg[0]["platform_code"] == "MYCF"
        assert neg[0]["cash_amount"] == -2000.0
        assert neg[0]["snapshot_date"] == self.NEXT_DAY.isoformat()

        # 快照正常落库（不阻断生成）
        pos = test_db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == port.code,
            PortfolioPosition.snapshot_date == self.NEXT_DAY,
            PortfolioPosition.product_code == "CASH",
        ).first()
        assert pos is not None
        assert Decimal(str(pos.cash_amount)) == Decimal("-2000")

    def test_normal_cash_warnings_none(self, client, admin_headers, test_db):
        """正常正现金场景 → warnings 为 None"""
        port = create_portfolio(test_db, code="NEGC_OK", status="active")
        _setup_cash_snapshot(test_db, port.code, self.D0, amount=1000.0)

        resp = client.post(
            "/api/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": self.NEXT_DAY.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["warnings"] is None


class TestRecalculateNegativeCashWarning:
    """区间重算含负现金日的 warnings 聚合（issue #71）"""

    PREV_DAY = date(2025, 6, 5)  # 基线日（周四）
    D0 = date(2025, 6, 6)
    NEXT_DAY = date(2025, 6, 9)

    def test_recalculate_collects_warnings_and_succeeds(self, client, admin_headers, test_db):
        """区间含负现金日 → 对应 result 带 warnings，重算整体成功并落库"""
        port = create_portfolio(test_db, code="NEGC_REC", status="active")
        _setup_cash_snapshot(test_db, port.code, self.PREV_DAY, amount=1000.0)
        _setup_cash_snapshot(test_db, port.code, self.D0, amount=1000.0)
        _setup_cash_snapshot(test_db, port.code, self.NEXT_DAY, amount=1000.0)
        # D0 生效的 confirmed CASH sell 3000 → 重建 D0 时 1000 - 3000 = -2000
        create_trade(
            test_db, port.code, "CASH", "",
            trade_type="sell", amount=3000.0, price=None,
            platform_code="MYCF", trade_date=self.D0,
            confirm_date=self.D0, status="confirmed",
        )

        resp = client.post(
            "/api/snapshots/recalculate",
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
        result = data["results"][0]
        assert result["errors"] == []
        assert result["total_processed"] == 2

        # 负现金 warnings 已累积（D0 转负后 NEXT_DAY 继承基线仍为负，两日均告警）
        assert result["warnings"], "重算区间含负现金日应带 warnings"
        neg = [w for w in result["warnings"] if w["type"] == "negative_cash"]
        assert len(neg) == 2
        assert {w["snapshot_date"] for w in neg} == {
            self.D0.isoformat(), self.NEXT_DAY.isoformat()
        }
        assert all(w["platform_code"] == "MYCF" for w in neg)
        assert all(w["cash_amount"] == -2000.0 for w in neg)

        # 重算成功落库：负现金快照已重建
        test_db.expire_all()
        pos = test_db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == port.code,
            PortfolioPosition.snapshot_date == self.D0,
            PortfolioPosition.product_code == "CASH",
        ).first()
        assert pos is not None
        assert Decimal(str(pos.cash_amount)) == Decimal("-2000")

    def test_recalculate_no_negative_cash_empty_warnings(self, client, admin_headers, test_db):
        """区间无负现金 → warnings 为空"""
        port = create_portfolio(test_db, code="NEGC_REC_OK", status="active")
        _setup_cash_snapshot(test_db, port.code, self.PREV_DAY, amount=1000.0)
        _setup_cash_snapshot(test_db, port.code, self.D0, amount=1000.0)

        resp = client.post(
            "/api/snapshots/recalculate",
            json={
                "portfolio_code": port.code,
                "start_date": self.D0.isoformat(),
                "end_date": self.D0.isoformat(),
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        result = data["results"][0]
        assert result["errors"] == []
        assert not result["warnings"]


class TestSnapshotStatusNegativeCash:
    """status 端点的 negative_cash_platforms 字段（issue #71）"""

    D0 = date(2025, 6, 6)

    def test_negative_cash_platform_listed(self, client, admin_headers, test_db):
        """最新快照日存在负现金 CASH 行 → 平台被列出，正现金平台不列"""
        port = create_portfolio(test_db, code="NEGC_ST", status="active")
        create_value_snapshot(
            test_db, port.code, self.D0,
            total_value=500, total_shares=1000, unit_price=0.5,
        )
        # MYCF 平台负现金，TTJJ 平台正现金
        create_position_snapshot(
            test_db, port.code, "CASH", "",
            snapshot_date=self.D0, cash_amount=-500.0, unit_price=None,
            cost_price=None, market_value=-500.0,
            platform_code="MYCF",
        )
        create_position_snapshot(
            test_db, port.code, "CASH", "",
            snapshot_date=self.D0, cash_amount=1000.0, unit_price=None,
            cost_price=None, market_value=1000.0,
            platform_code="TTJJ",
        )

        resp = client.get(
            f"/api/snapshots/portfolios/{port.code}/status",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["negative_cash_platforms"] == ["MYCF"]

    def test_normal_cash_empty_list(self, client, admin_headers, test_db):
        """最新快照日现金均为正 → negative_cash_platforms 为空列表"""
        port = create_portfolio(test_db, code="NEGC_ST_OK", status="active")
        _setup_cash_snapshot(test_db, port.code, self.D0, amount=1000.0)

        resp = client.get(
            f"/api/snapshots/portfolios/{port.code}/status",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["negative_cash_platforms"] == []

    def test_no_snapshot_empty_list(self, client, admin_headers, test_db):
        """无任何快照 → negative_cash_platforms 为空列表"""
        port = create_portfolio(test_db, code="NEGC_ST_NONE", status="active")

        resp = client.get(
            f"/api/snapshots/portfolios/{port.code}/status",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["negative_cash_platforms"] == []
