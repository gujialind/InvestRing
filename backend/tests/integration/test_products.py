# ============================================================================
# 集成测试：产品管理 (test_products.py)
# ============================================================================

import pytest
from tests.factories import create_product, create_asset_classification


class TestProductCRUD:
    """产品 CRUD API 测试"""

    def test_list_products(self, client, admin_headers):
        """获取产品列表"""
        resp = client.get("/api/products", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_create_product(self, client, admin_headers, test_db):
        """创建产品"""
        create_asset_classification(test_db, code="STOCK_CN_LARGE")
        resp = client.post(
            "/api/products",
            json={
                "code": "999001.OF",
                "market": "CN_OTC",
                "name": "测试新基金",
                "product_type": "OEF",
                "asset_class_code": "STOCK_CN_LARGE",
                "confirm_days": 1,
                "is_qdii": False,
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["code"] == "999001.OF"
        assert data["product_type"] == "OEF"

    def test_get_product_detail(self, client, admin_headers, test_db):
        """获取产品详情"""
        create_product(test_db, code="888001.OF", market="CN_OTC")
        resp = client.get("/api/products/888001.OF/CN_OTC", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == "888001.OF"

    def test_viewer_cannot_create_product(self, client, viewer_headers):
        """viewer 不能创建产品"""
        resp = client.post(
            "/api/products",
            json={"code": "X", "market": "CN_OTC", "name": "X", "product_type": "OEF"},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_list_products_pagination(self, client, admin_headers):
        """产品列表分页"""
        resp = client.get("/api/products?page=1&page_size=5", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["page"] == 1
        assert data["page_size"] == 5
