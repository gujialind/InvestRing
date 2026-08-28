# ============================================================================
# 集成测试：market-data 端点鉴权矩阵（issue #256）
# ============================================================================
# 修复前 4 个端点无任何鉴权（CWE-306）。验收矩阵：
# - 无 token / 无效 token → 401
# - 普通用户（viewer）：读 200，写（同步）403
# - 管理员（admin）：读写均 200
# ============================================================================

from unittest.mock import patch


class TestMarketDataAuth:
    """issue #256: market_data 4 端点鉴权矩阵"""

    PRICE_DATA = "/api/market-data/products/510300.SH/CN_EXCHANGE/price-data"
    NAV_COVERAGE = "/api/market-data/products/000300.OF/CN_OTC/nav-coverage"
    SYNC = "/api/market-data/products/510300.SH/CN_EXCHANGE/sync-price-data"
    SYNC_HISTORY = "/api/market-data/products/510300.SH/CN_EXCHANGE/sync-history"

    ENDPOINTS = [
        ("get", PRICE_DATA, {}),
        ("get", NAV_COVERAGE, {"start_date": "2025-01-06"}),
        ("post", SYNC, None),
        ("post", SYNC_HISTORY, None),
    ]

    def test_no_token_401(self, client):
        """4 端点无 token 访问一律 401"""
        for method, url, params in self.ENDPOINTS:
            resp = getattr(client, method)(url, params=params)
            assert resp.status_code == 401, f"{method.upper()} {url} -> {resp.status_code}"

    def test_invalid_token_401(self, client):
        """4 端点伪造无效 token 一律 401"""
        headers = {"Authorization": "Bearer invalid.token.here"}
        for method, url, params in self.ENDPOINTS:
            resp = getattr(client, method)(url, params=params, headers=headers)
            assert resp.status_code == 401, f"{method.upper()} {url} -> {resp.status_code}"

    def test_viewer_can_read(self, client, viewer_headers):
        """viewer 可读价格数据与净值覆盖"""
        resp = client.get(self.PRICE_DATA, headers=viewer_headers)
        assert resp.status_code == 200

        resp = client.get(
            self.NAV_COVERAGE,
            params={"start_date": "2025-01-06"},
            headers=viewer_headers,
        )
        assert resp.status_code == 200

    def test_viewer_cannot_sync(self, client, viewer_headers):
        """viewer 触发同步（写库 + 外部数据源）一律 403"""
        resp = client.post(
            self.SYNC,
            json={"start_date": "2025-06-06", "end_date": "2025-06-06"},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

        resp = client.post(self.SYNC_HISTORY, headers=viewer_headers)
        assert resp.status_code == 403

    @patch("app.services.market_data_service.get_fund_daily")
    def test_admin_can_sync(self, mock_daily, client, admin_headers, test_db):
        """admin 可触发同步（外部数据源已 mock）"""
        mock_daily.return_value = [
            {"trade_date": "20250606", "close": 4.0, "pre_close": 3.9, "pct_chg": 2.56},
        ]
        resp = client.post(
            self.SYNC,
            json={"start_date": "2025-06-06", "end_date": "2025-06-06"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = client.post(self.SYNC_HISTORY, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
