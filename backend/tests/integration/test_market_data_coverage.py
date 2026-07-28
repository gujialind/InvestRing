# ============================================================================
# 集成测试：market-data limit 放宽 / nav-history 拍平 / nav-coverage（issue #60/#62/#63）
# ============================================================================

from datetime import date, timedelta
from decimal import Decimal

from tests.factories import create_portfolio
from app.models import PriceRecord, PortfolioValueSnapshot


def _seed_prices(test_db, dates, code="510300.SH", market="CN_EXCHANGE"):
    """为指定产品批量写入价格记录"""
    for d in dates:
        test_db.add(PriceRecord(
            product_code=code, market=market, price_date=d,
            unit_price=Decimal("1.2345"), source="test",
        ))
    test_db.commit()


class TestPriceDataLimit:
    """issue #60: price-data limit 上限放宽到 1000"""

    def test_limit_1000_returns_all_records(self, client, test_db):
        """limit=1000 应返回 200，条数 = min(1000, 实际条数)"""
        dates = [date(2025, 3, 3) + timedelta(days=i) for i in range(10)]
        _seed_prices(test_db, dates)
        resp = client.get(
            "/api/market-data/products/510300.SH/CN_EXCHANGE/price-data",
            params={"limit": 1000, "start_date": "2025-03-03", "end_date": "2025-03-31"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 10

    def test_limit_1001_rejected_422(self, client):
        """limit=1001 超出上限应返回 422"""
        resp = client.get(
            "/api/market-data/products/510300.SH/CN_EXCHANGE/price-data",
            params={"limit": 1001},
        )
        assert resp.status_code == 422


class TestNavHistoryFlat:
    """issue #62: nav-history 返回单层列表，date 更名为 snapshot_date"""

    def test_nav_history_returns_flat_list(self, client, admin_headers, test_db):
        create_portfolio(test_db, code="P_NAVH", status="active")
        for i, d in enumerate([date(2025, 1, 6), date(2025, 1, 7)]):
            test_db.add(PortfolioValueSnapshot(
                portfolio_code="P_NAVH", snapshot_date=d,
                total_value=Decimal("100000") + i * 1000,
                total_shares=Decimal("100000"),
                unit_price=Decimal("1") + Decimal("0.01") * i,
            ))
        test_db.commit()

        resp = client.get("/api/portfolios/P_NAVH/nav-history", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2
        # 单层结构：行内含 snapshot_date，且无旧的 date 字段与外层包装
        assert body[0]["snapshot_date"] == "2025-01-06"
        assert "date" not in body[0]
        assert body[0]["unit_price"] == 1.0
        assert body[1]["snapshot_date"] == "2025-01-07"

    def test_nav_history_portfolio_not_found_404(self, client, admin_headers):
        resp = client.get("/api/portfolios/NO_SUCH_P/nav-history", headers=admin_headers)
        assert resp.status_code == 404


class TestNavCoverage:
    """issue #63: nav-coverage 覆盖校验端点"""

    # 2025-01-06(一) ~ 2025-01-10(五)，conftest 日历中均为交易日
    WEEK = [date(2025, 1, 6) + timedelta(days=i) for i in range(5)]

    def test_full_coverage(self, client, test_db):
        """区间内全部交易日均有净值：coverage=1.0，missing 为空"""
        _seed_prices(test_db, self.WEEK, code="000300.OF", market="CN_OTC")
        resp = client.get(
            "/api/market-data/products/000300.OF/CN_OTC/nav-coverage",
            params={"start_date": "2025-01-06", "end_date": "2025-01-10"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_code"] == "000300.OF"
        assert data["market"] == "CN_OTC"
        assert data["total_trading_days"] == 5
        assert data["synced_days"] == 5
        assert data["coverage"] == 1.0
        assert data["missing_dates"] == []

    def test_partial_missing(self, client, test_db):
        """缺 2025-01-08：missing_dates 精确列出，coverage=0.8"""
        seeded = [d for d in self.WEEK if d != date(2025, 1, 8)]
        _seed_prices(test_db, seeded, code="000300.OF", market="CN_OTC")
        resp = client.get(
            "/api/market-data/products/000300.OF/CN_OTC/nav-coverage",
            params={"start_date": "2025-01-06", "end_date": "2025-01-10"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trading_days"] == 5
        assert data["synced_days"] == 4
        assert data["coverage"] == 0.8
        assert data["missing_dates"] == ["2025-01-08"]

    def test_product_not_found_404(self, client):
        resp = client.get(
            "/api/market-data/products/NO_SUCH.OF/CN_OTC/nav-coverage",
            params={"start_date": "2025-01-06"},
        )
        assert resp.status_code == 404

    def test_start_after_end_422(self, client):
        resp = client.get(
            "/api/market-data/products/000300.OF/CN_OTC/nav-coverage",
            params={"start_date": "2025-01-10", "end_date": "2025-01-06"},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "INVALID_DATE_RANGE"

    def test_no_trading_days_coverage_none(self, client, test_db):
        """区间只含周末（无交易日）：total=0，coverage 为 null"""
        resp = client.get(
            "/api/market-data/products/000300.OF/CN_OTC/nav-coverage",
            params={"start_date": "2025-01-04", "end_date": "2025-01-05"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trading_days"] == 0
        assert data["synced_days"] == 0
        assert data["coverage"] is None
        assert data["missing_dates"] == []
