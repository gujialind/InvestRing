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
        create_asset_classification(test_db, code="ASSET_STOCK")
        create_asset_classification(test_db, code="REGION_CN", dimension="region")
        create_asset_classification(test_db, code="STYLE_BALANCED", dimension="style")
        create_asset_classification(test_db, code="SIZE_LARGE", dimension="size")
        resp = client.post(
            "/api/products",
            json={
                "code": "999001.OF",
                "market": "CN_OTC",
                "name": "测试新基金",
                "product_type": "OEF",
                "asset_class_code": "ASSET_STOCK",
                "region_code": "REGION_CN",
                "style_code": "STYLE_BALANCED",
                "size_code": "SIZE_LARGE",
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


def _seed_dims(test_db):
    """种子矩阵校验所需维度值（issue #128）"""
    create_asset_classification(test_db, code="ASSET_STOCK")
    create_asset_classification(test_db, code="ASSET_BOND")
    create_asset_classification(test_db, code="ASSET_COMMODITY")
    create_asset_classification(test_db, code="ASSET_CASH")
    create_asset_classification(test_db, code="REGION_CN", dimension="region")
    create_asset_classification(test_db, code="STYLE_GROWTH", dimension="style")
    create_asset_classification(test_db, code="STYLE_BALANCED", dimension="style")
    create_asset_classification(test_db, code="SIZE_LARGE", dimension="size")
    create_asset_classification(test_db, code="SEG_COMPOSITE", dimension="segment")
    create_asset_classification(test_db, code="SEG_BOND_SHORT", dimension="segment")
    create_asset_classification(test_db, code="SEG_GOLD", dimension="segment")


class TestDimensionMatrixValidation:
    """维度适用矩阵校验（issue #128）：非法组合 422 INVALID_DIMENSION_TAGS"""

    def _post(self, client, admin_headers, **dims):
        json = {
            "code": "999002.OF",
            "market": "CN_OTC",
            "name": "矩阵测试基金",
            "product_type": "OEF",
            "is_qdii": False,
        }
        json.update(dims)
        return client.post("/api/products", json=json, headers=admin_headers)

    def test_stock_missing_region_422(self, client, admin_headers, test_db):
        """股票缺 region → 422"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_STOCK",
            style_code="STYLE_BALANCED",
            size_code="SIZE_LARGE",
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_stock_missing_style_422(self, client, admin_headers, test_db):
        """股票缺 style → 422"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_STOCK",
            region_code="REGION_CN",
            size_code="SIZE_LARGE",
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_bond_with_style_422(self, client, admin_headers, test_db):
        """债券带 style → 422"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_BOND",
            region_code="REGION_CN",
            segment_code="SEG_BOND_SHORT",
            style_code="STYLE_BALANCED",
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_commodity_with_region_422(self, client, admin_headers, test_db):
        """商品带 region → 422"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_COMMODITY",
            segment_code="SEG_GOLD",
            region_code="REGION_CN",
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_cash_with_region_422(self, client, admin_headers, test_db):
        """现金带 region → 422"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_CASH",
            region_code="REGION_CN",
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_dimension_mismatch_422(self, client, admin_headers, test_db):
        """维度错位（region 字段填 style 值）→ 422"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_STOCK",
            region_code="STYLE_GROWTH",
            style_code="STYLE_BALANCED",
            size_code="SIZE_LARGE",
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_nonexistent_code_422(self, client, admin_headers, test_db):
        """引用不存在的维度值 → 422"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_STOCK",
            region_code="REGION_MOON",
            style_code="STYLE_BALANCED",
            size_code="SIZE_LARGE",
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_other_dims_without_asset_class_422(self, client, admin_headers, test_db):
        """未指定 asset_class 却带其他维度 → 422"""
        _seed_dims(test_db)
        resp = self._post(client, admin_headers, region_code="REGION_CN")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_undefined_matrix_asset_class_422(self, client, admin_headers, test_db):
        """字典新增大类值但适用矩阵未登记 → 422（而非 KeyError → 500，PR #130 评审 M1）"""
        _seed_dims(test_db)
        create_asset_classification(test_db, code="ASSET_ALTERNATIVE")
        resp = self._post(client, admin_headers, asset_class_code="ASSET_ALTERNATIVE")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_valid_stock_ok(self, client, admin_headers, test_db):
        """合法股票组合 → 创建成功且维度落库"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_STOCK",
            region_code="REGION_CN",
            style_code="STYLE_GROWTH",
            size_code="SIZE_LARGE",
            segment_code="SEG_COMPOSITE",
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["region_code"] == "REGION_CN"
        assert data["style_code"] == "STYLE_GROWTH"
        assert data["size_code"] == "SIZE_LARGE"
        assert data["segment_code"] == "SEG_COMPOSITE"

    def test_valid_bond_ok(self, client, admin_headers, test_db):
        """合法债券组合（region+segment，无 style/size）→ 创建成功"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_BOND",
            region_code="REGION_CN",
            segment_code="SEG_BOND_SHORT",
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["style_code"] is None
        assert data["size_code"] is None

    def test_update_to_invalid_combo_422(self, client, admin_headers, test_db):
        """更新为非法组合（合并校验）→ 422 且不落库"""
        _seed_dims(test_db)
        create_product(test_db, code="999003.OF", market="CN_OTC")
        resp = client.put(
            "/api/products/999003.OF/CN_OTC",
            json={"asset_class_code": "ASSET_BOND"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"


class TestAssetClassificationsEndpoint:
    """维度字典只读端点（issue #128）"""

    def test_list_all(self, client, admin_headers):
        """全量字典：conftest 种子 34 条，按 dimension+sort_order 排序"""
        resp = client.get("/api/asset-classifications", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == len(data["items"]) > 0
        keys = [(i["dimension"], i["sort_order"]) for i in data["items"]]
        assert keys == sorted(keys)
        asset_classes = [i for i in data["items"] if i["dimension"] == "asset_class"]
        assert [i["code"] for i in asset_classes] == [
            "ASSET_STOCK", "ASSET_BOND", "ASSET_COMMODITY", "ASSET_CASH",
        ]

    def test_filter_by_dimension(self, client, admin_headers):
        """dimension 过滤"""
        resp = client.get(
            "/api/asset-classifications?dimension=region", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        assert all(i["dimension"] == "region" for i in data["items"])
