# ============================================================================
# 集成测试：产品管理 (test_products.py)
# ============================================================================

import time

import pytest
from tests.factories import create_product, create_asset_classification

from app.models.asset_classification import (
    AssetClassification,
    AssetClassDimensionRule,
    AssetDimensionApplicability,
)


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


class TestConfirmDaysAndNavLagDays:
    """issue #228：confirm_days / nav_lag_days 更新纯显式（is_qdii 不再联动重算），
    calculate_confirm_days 仅保留创建时默认推导器角色"""

    def test_update_is_qdii_keeps_confirm_days(self, client, admin_headers, test_db):
        """PUT {"is_qdii": true} 不改 confirm_days（存量 7 → 仍 7）"""
        create_product(test_db, code="LAG001.OF", market="CN_OTC", confirm_days=7)
        resp = client.put(
            "/api/products/LAG001.OF/CN_OTC",
            json={"is_qdii": True},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["is_qdii"] is True
        assert resp.json()["confirm_days"] == 7

        got = client.get("/api/products/LAG001.OF/CN_OTC", headers=admin_headers)
        assert got.json()["confirm_days"] == 7

    def test_update_is_qdii_with_explicit_confirm_days_wins(self, client, admin_headers, test_db):
        """PUT {"is_qdii": true, "confirm_days": 5} → 显式值生效（旧逻辑会被覆盖成 2）"""
        create_product(test_db, code="LAG002.OF", market="CN_OTC", confirm_days=1)
        resp = client.put(
            "/api/products/LAG002.OF/CN_OTC",
            json={"is_qdii": True, "confirm_days": 5},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["confirm_days"] == 5

    def test_update_nav_lag_days(self, client, admin_headers, test_db):
        """PUT {"nav_lag_days": 1} 生效（互认基金上线后手动置 1 的路径），不影响 confirm_days"""
        create_product(test_db, code="LAG003", market="HK_MUTUAL", confirm_days=1)
        resp = client.put(
            "/api/products/LAG003/HK_MUTUAL",
            json={"nav_lag_days": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["nav_lag_days"] == 1
        assert resp.json()["confirm_days"] == 1

        got = client.get("/api/products/LAG003/HK_MUTUAL", headers=admin_headers)
        assert got.json()["nav_lag_days"] == 1

    def test_create_otc_qdii_derives_confirm_days_2(self, client, admin_headers, test_db):
        """创建场外 QDII 不传 confirm_days → 后端推导 2（创建时默认推导器仍在）"""
        resp = client.post(
            "/api/products",
            json={
                "code": "LAG004.OF",
                "market": "CN_OTC",
                "name": "测试QDII基金",
                "product_type": "OEF",
                "asset_class_code": "ASSET_STOCK",
                "region_code": "REGION_CN",
                "style_code": "STYLE_BALANCED",
                "size_code": "SIZE_LARGE",
                "is_qdii": True,
            },
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), resp.json()
        data = resp.json()
        assert data["confirm_days"] == 2
        # nav_lag_days 不做推导：创建未传即 0，需显式设置（迁移只回填存量场外 QDII）
        assert data["nav_lag_days"] == 0


class TestProductKeywordFilter:
    """产品列表 keyword 模糊筛选（issue #155）：code/name ilike OR 匹配"""

    def test_keyword_matches_code_fragment(self, client, admin_headers, test_db):
        """code 片段命中"""
        create_product(test_db, code="510300.SH", market="CN_EXCHANGE", name="沪深300ETF")
        create_product(test_db, code="000001.OF", market="CN_OTC", name="平安大华基金")
        resp = client.get("/api/products?keyword=5103", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["code"] == "510300.SH"

    def test_keyword_matches_name_fragment(self, client, admin_headers, test_db):
        """name 片段命中"""
        create_product(test_db, code="510300.SH", market="CN_EXCHANGE", name="沪深300ETF")
        create_product(test_db, code="000001.OF", market="CN_OTC", name="平安大华基金")
        resp = client.get("/api/products?keyword=大华", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "平安大华基金"

    def test_keyword_percent_literalized(self, client, admin_headers, test_db):
        """含 % 的输入被字面化，不触发通配"""
        create_product(test_db, code="900001.OF", market="CN_OTC", name="收益5%增强")
        create_product(test_db, code="900002.OF", market="CN_OTC", name="收益500增强")
        resp = client.get("/api/products?keyword=5%25", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # % 若未转义，"收益500增强" 也会被通配命中
        assert data["total"] == 1
        assert data["items"][0]["name"] == "收益5%增强"

    def test_keyword_and_other_filters(self, client, admin_headers, test_db):
        """keyword 与既有筛选参数 AND 叠加"""
        create_product(test_db, code="510300.SH", market="CN_EXCHANGE",
                       name="沪深300ETF", product_type="ETF")
        create_product(test_db, code="510300.OF", market="CN_OTC",
                       name="沪深300联接", product_type="OEF")
        resp = client.get(
            "/api/products?keyword=510300&product_type=OEF",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["code"] == "510300.OF"


class TestProductListAttrFilter:
    """产品列表属性等值筛选（issue #238）：confirm_days / nav_lag_days / is_qdii。

    断言风格：谓词全称（结果集每项都满足等值）+ 自建 code 必在/必不在结果集，
    不对种子无关的绝对 total 下断言（种子见 tests/seed_base.py）。
    0 / False 为合法筛选值，覆盖「if param: 假值陷阱」回归。
    """

    def test_confirm_days_filter(self, client, admin_headers, test_db):
        """?confirm_days=2 → 结果每项 confirm_days==2 且自建 code 在列"""
        create_product(test_db, code="AF001.OF", market="CN_OTC", confirm_days=2)
        create_product(test_db, code="AF002.OF", market="CN_OTC", confirm_days=1)
        resp = client.get("/api/products?confirm_days=2", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0
        assert all(i["confirm_days"] == 2 for i in items)
        codes = [i["code"] for i in items]
        assert "AF001.OF" in codes
        assert "AF002.OF" not in codes

    def test_confirm_days_zero_matches_virtual(self, client, admin_headers):
        """?confirm_days=0 → 含种子 CASH/IN_TRANSIT_BUY/IN_TRANSIT_SELL/510300.SH（全为 0），
        验证 0 值不被 `if param:` 假值陷阱跳过"""
        resp = client.get("/api/products?confirm_days=0", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["confirm_days"] == 0 for i in items)
        codes = [i["code"] for i in items]
        for seed_code in ("CASH", "IN_TRANSIT_BUY", "IN_TRANSIT_SELL", "510300.SH"):
            assert seed_code in codes

    def test_nav_lag_days_filter(self, client, admin_headers, test_db):
        """?nav_lag_days=1 → 谓词成立且自建 code 在列；?nav_lag_days=0 不含该 code"""
        create_product(test_db, code="AF003.OF", market="CN_OTC", nav_lag_days=1)
        resp = client.get("/api/products?nav_lag_days=1", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0
        assert all(i["nav_lag_days"] == 1 for i in items)
        assert "AF003.OF" in [i["code"] for i in items]

        resp0 = client.get("/api/products?nav_lag_days=0", headers=admin_headers)
        assert resp0.status_code == 200
        items0 = resp0.json()["items"]
        assert all(i["nav_lag_days"] == 0 for i in items0)
        assert "AF003.OF" not in [i["code"] for i in items0]

    def test_is_qdii_true_false(self, client, admin_headers, test_db):
        """?is_qdii=true 含自建 QDII；?is_qdii=false 不含（false 分支必测，防 `if is_qdii:` 回归）"""
        create_product(test_db, code="AF004.OF", market="CN_OTC", is_qdii=True, confirm_days=2)
        resp_true = client.get("/api/products?is_qdii=true", headers=admin_headers)
        assert resp_true.status_code == 200
        items_true = resp_true.json()["items"]
        assert all(i["is_qdii"] is True for i in items_true)
        assert "AF004.OF" in [i["code"] for i in items_true]

        resp_false = client.get("/api/products?is_qdii=false", headers=admin_headers)
        assert resp_false.status_code == 200
        items_false = resp_false.json()["items"]
        assert all(i["is_qdii"] is False for i in items_false)
        assert "AF004.OF" not in [i["code"] for i in items_false]

    def test_filters_and_combined(self, client, admin_headers, test_db):
        """三参数与既有参数 AND 叠加（仿 test_keyword_and_other_filters 风格）"""
        create_product(test_db, code="AF005.OF", market="CN_OTC",
                       product_type="OEF", confirm_days=1, is_qdii=False)
        create_product(test_db, code="AF006.OF", market="CN_OTC",
                       product_type="OEF", confirm_days=1, is_qdii=True)
        resp = client.get(
            "/api/products?confirm_days=1&is_qdii=false&product_type=OEF",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(
            i["confirm_days"] == 1 and i["is_qdii"] is False and i["product_type"] == "OEF"
            for i in items
        )
        codes = [i["code"] for i in items]
        assert "AF005.OF" in codes
        assert "AF006.OF" not in codes

    def test_backward_compat_no_params(self, client, admin_headers, test_db):
        """不传三参数时不过滤：结果集混合多种 confirm_days / is_qdii 取值"""
        create_product(test_db, code="AF007.OF", market="CN_OTC", confirm_days=2, is_qdii=True)
        resp = client.get("/api/products?page_size=100", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        codes = [i["code"] for i in items]
        assert "AF007.OF" in codes  # is_qdii=True 未被默认排除
        assert "CASH" in codes  # confirm_days=0 未被默认排除
        assert {i["is_qdii"] for i in items} == {True, False}
        assert len({i["confirm_days"] for i in items}) > 1


class TestProductListOrder:
    """产品 list 确定性排序（issue #165）：created_at DESC + code ASC"""

    def test_new_product_on_first_page(self, client, admin_headers, test_db):
        """新建产品必然出现在 page_size=50 首页（#162 下拉验收前提）"""
        create_product(test_db, code="960001.OF", market="CN_OTC", name="排序测试基金")
        resp = client.get("/api/products?page_size=50", headers=admin_headers)
        assert resp.status_code == 200
        codes = [i["code"] for i in resp.json()["items"]]
        assert "960001.OF" in codes

    def test_created_desc_tiebreak_code_and_stable(self, client, admin_headers, test_db):
        """新建优先；同秒并列按 code 定序；重复请求顺序稳定"""
        create_product(test_db, code="960010.OF", market="CN_OTC", name="排序旧基金")
        time.sleep(1.1)  # 跨秒创建（created_at 为 NOW() 秒级精度）
        create_product(test_db, code="960012.OF", market="CN_OTC", name="排序新基金B")
        create_product(test_db, code="960011.OF", market="CN_OTC", name="排序新基金A")

        resp = client.get("/api/products?page_size=100", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        codes = [i["code"] for i in items]
        # 新建优先：跨秒后创建的两个产品均排在旧产品之前
        assert codes.index("960012.OF") < codes.index("960010.OF")
        assert codes.index("960011.OF") < codes.index("960010.OF")
        # 同秒并列时按 code 升序定序
        by_code = {i["code"]: i for i in items}
        if by_code["960011.OF"]["created_at"] == by_code["960012.OF"]["created_at"]:
            assert codes.index("960011.OF") < codes.index("960012.OF")

        # 重复请求顺序稳定（确定性排序）
        resp2 = client.get("/api/products?page_size=100", headers=admin_headers)
        assert [i["code"] for i in resp2.json()["items"]] == codes


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

    def test_unruled_asset_class_defaults_cash_like(self, client, admin_headers, test_db):
        """#135 矩阵落库：无规则行的大类 = 现金型全 forbidden（替代旧「矩阵未定义」422）"""
        _seed_dims(test_db)
        create_asset_classification(test_db, code="ASSET_ALTERNATIVE")
        # 不带其他维度 → 合法（现金型语义，新建大类默认态）
        resp = self._post(client, admin_headers, asset_class_code="ASSET_ALTERNATIVE")
        assert resp.status_code in (200, 201)
        # 带任一其他维度 → 422（全 forbidden）
        resp = self._post(
            client, admin_headers,
            code="999004.OF",
            asset_class_code="ASSET_ALTERNATIVE",
            region_code="REGION_CN",
        )
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


class TestValueLevelApplicability:
    """值级适用校验（issue #135）：维度值必须关联产品的 asset_class"""

    def _post(self, client, admin_headers, code="999002.OF", **dims):
        json = {
            "code": code,
            "market": "CN_OTC",
            "name": "值级校验测试基金",
            "product_type": "OEF",
            "is_qdii": False,
        }
        json.update(dims)
        return client.post("/api/products", json=json, headers=admin_headers)

    def test_stock_with_commodity_segment_422(self, client, admin_headers, test_db):
        """股票传 segment=SEG_GOLD：维度级通过（segment 选填），值级拒绝"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_STOCK",
            region_code="REGION_CN",
            style_code="STYLE_BALANCED",
            size_code="SIZE_LARGE",
            segment_code="SEG_GOLD",
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "INVALID_DIMENSION_TAGS"
        assert detail["details"]["applicable_asset_classes"] == ["ASSET_COMMODITY"]

    def test_stock_with_bond_segment_422(self, client, admin_headers, test_db):
        """股票传 segment=SEG_BOND_SHORT → 422"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_STOCK",
            region_code="REGION_CN",
            style_code="STYLE_BALANCED",
            size_code="SIZE_LARGE",
            segment_code="SEG_BOND_SHORT",
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_bond_only_segment_passes(self, client, admin_headers, test_db):
        """仅关联债券的 SEG 值：债券产品引用成功"""
        _seed_dims(test_db)
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_BOND",
            region_code="REGION_CN",
            segment_code="SEG_BOND_SHORT",
        )
        assert resp.status_code in (200, 201)

    def test_new_bond_only_value_rejected_for_stock(self, client, admin_headers, test_db):
        """新建仅关联债券的 SEG 值 → 股票 422、债券通过（验收断言）"""
        _seed_dims(test_db)
        create_asset_classification(test_db, code="SEG_BOND_CONVERT", dimension="segment")
        test_db.add(AssetDimensionApplicability(
            dimension_value_code="SEG_BOND_CONVERT", asset_class_code="ASSET_BOND",
        ))
        test_db.commit()
        stock = self._post(
            client, admin_headers,
            asset_class_code="ASSET_STOCK",
            region_code="REGION_CN",
            style_code="STYLE_BALANCED",
            size_code="SIZE_LARGE",
            segment_code="SEG_BOND_CONVERT",
        )
        assert stock.status_code == 422
        bond = self._post(
            client, admin_headers,
            code="999005.OF",
            asset_class_code="ASSET_BOND",
            region_code="REGION_CN",
            segment_code="SEG_BOND_CONVERT",
        )
        assert bond.status_code in (200, 201)

    def test_rules_db_driven(self, client, admin_headers, test_db):
        """规则读库证明：把股票 segment 改为 required 后，缺 segment → 422"""
        _seed_dims(test_db)
        rule = test_db.query(AssetClassDimensionRule).filter_by(
            asset_class_code="ASSET_STOCK", dimension="segment",
        ).first()
        rule.rule = "required"
        test_db.commit()
        resp = self._post(
            client, admin_headers,
            asset_class_code="ASSET_STOCK",
            region_code="REGION_CN",
            style_code="STYLE_BALANCED",
            size_code="SIZE_LARGE",
        )
        assert resp.status_code == 422
        assert "segment_code" in resp.json()["detail"]["details"]["missing"]

    def test_update_path_value_level(self, client, admin_headers, test_db):
        """update merged 校验同样过值级：改为不适用值 → 422"""
        _seed_dims(test_db)
        create_product(test_db, code="999006.OF", market="CN_OTC")
        resp = client.put(
            "/api/products/999006.OF/CN_OTC",
            json={"segment_code": "SEG_GOLD"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"


class TestIsActiveValidation:
    """is_active 软失效（issue #135）：新赋值校验 active，存量引用不阻断"""

    def test_create_with_inactive_value_422(self, client, admin_headers, test_db):
        """create 引用已停用维度值 → 422"""
        _seed_dims(test_db)
        test_db.query(AssetClassification).filter_by(code="STYLE_GROWTH").first().is_active = False
        test_db.commit()
        resp = client.post(
            "/api/products",
            json={
                "code": "999007.OF", "market": "CN_OTC", "name": "停用值测试",
                "product_type": "OEF",
                "asset_class_code": "ASSET_STOCK", "region_code": "REGION_CN",
                "style_code": "STYLE_GROWTH", "size_code": "SIZE_LARGE",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_DIMENSION_TAGS"

    def test_update_unchanged_inactive_value_passes(self, client, admin_headers, test_db):
        """存量引用停用值：改其他维度字段（style 未变）不阻断"""
        _seed_dims(test_db)
        create_product(test_db, code="999008.OF", market="CN_OTC", style_code="STYLE_GROWTH")
        test_db.query(AssetClassification).filter_by(code="STYLE_GROWTH").first().is_active = False
        test_db.commit()
        resp = client.put(
            "/api/products/999008.OF/CN_OTC",
            json={"segment_code": "SEG_DIVIDEND"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_update_change_to_inactive_value_422(self, client, admin_headers, test_db):
        """update 改赋停用值（字段实际变化）→ 422"""
        _seed_dims(test_db)
        create_product(test_db, code="999009.OF", market="CN_OTC", style_code="STYLE_BALANCED")
        test_db.query(AssetClassification).filter_by(code="STYLE_GROWTH").first().is_active = False
        test_db.commit()
        resp = client.put(
            "/api/products/999009.OF/CN_OTC",
            json={"style_code": "STYLE_GROWTH"},
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

    def test_items_carry_applicability_and_active(self, client, admin_headers):
        """#135：每项含 applicable_asset_classes 与 is_active；asset_class 维度恒空"""
        resp = client.get("/api/asset-classifications", headers=admin_headers)
        assert resp.status_code == 200
        items = {i["code"]: i for i in resp.json()["items"]}
        assert items["REGION_CN"]["applicable_asset_classes"] == ["ASSET_STOCK", "ASSET_BOND"]
        assert items["SEG_GOLD"]["applicable_asset_classes"] == ["ASSET_COMMODITY"]
        assert items["STYLE_GROWTH"]["applicable_asset_classes"] == ["ASSET_STOCK"]
        assert items["ASSET_STOCK"]["applicable_asset_classes"] == []
        assert items["ASSET_CASH"]["is_active"] is True
        # 原有字段与排序不回归
        assert items["ASSET_STOCK"]["sort_order"] == 1

    def test_dimension_rules_top_level(self, client, admin_headers):
        """#135 矩阵落库：顶层 dimension_rules 与常量一致，无行维度 = forbidden"""
        resp = client.get("/api/asset-classifications", headers=admin_headers)
        assert resp.status_code == 200
        rules = resp.json()["dimension_rules"]
        assert rules["ASSET_STOCK"] == {
            "region": "required", "style": "required",
            "size": "required", "segment": "optional",
        }
        assert rules["ASSET_BOND"] == {"region": "required", "segment": "required"}
        assert rules["ASSET_COMMODITY"] == {"segment": "optional"}
        # ASSET_CASH 无规则行（全 forbidden）
        assert "ASSET_CASH" not in rules


class TestNavLagDaysValidation:
    """issue #235/#240：nav_lag_days 取值校验——>=0；场内基金（CN_EXCHANGE）必须 0。

    #240 跟进 #5：负值校验收进 service 层（去掉 schema ge=0），
    同一业务规则统一 422 形状（detail.error=INVALID_NAV_LAG_DAYS）。

    覆盖：
    - 创建/更新负值 → 422 INVALID_NAV_LAG_DAYS（service 单一实现，统一形状）
    - 场内（CN_EXCHANGE）创建/更新 lag>0 → 422 INVALID_NAV_LAG_DAYS（service 跨字段）
    - 场外 QDII（CN_OTC lag=1）/ 互认（HK_MUTUAL lag=1）正常（回归，仅场内禁止）
    - market 迁移至 CN_EXCHANGE 但残留 lag>0 → 422（禁静默口径翻转）；同 PUT 显式置 0 → 成功
    """

    def test_create_nav_lag_days_negative_422(self, client, admin_headers):
        """>=0：创建传 -1 → 422 INVALID_NAV_LAG_DAYS（#240：service 层统一形状，非 pydantic 列表形状）"""
        resp = client.post(
            "/api/products",
            json={"code": "NL001.OF", "market": "CN_OTC", "name": "负值",
                  "product_type": "OEF", "nav_lag_days": -1},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "INVALID_NAV_LAG_DAYS"
        assert detail["details"]["nav_lag_days"] == -1

    def test_update_nav_lag_days_negative_422(self, client, admin_headers, test_db):
        """>=0：PUT 传 -1 → 422 INVALID_NAV_LAG_DAYS（#240：service 层统一形状，非 pydantic 列表形状）"""
        create_product(test_db, code="NL002.OF", market="CN_OTC")
        resp = client.put(
            "/api/products/NL002.OF/CN_OTC",
            json={"nav_lag_days": -1},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_NAV_LAG_DAYS"

    def test_create_exchange_nav_lag_positive_422(self, client, admin_headers):
        """场内（CN_EXCHANGE）创建 lag=1 → 422 INVALID_NAV_LAG_DAYS（跨字段）"""
        resp = client.post(
            "/api/products",
            json={"code": "NL003.SH", "market": "CN_EXCHANGE", "name": "场内滞后",
                  "product_type": "ETF", "nav_lag_days": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "INVALID_NAV_LAG_DAYS"
        assert detail["details"]["market"] == "CN_EXCHANGE"

    def test_create_exchange_nav_lag_zero_ok(self, client, admin_headers):
        """场内创建 lag=0 → 成功（回归）"""
        resp = client.post(
            "/api/products",
            json={"code": "NL004.SH", "market": "CN_EXCHANGE", "name": "场内当日",
                  "product_type": "ETF", "nav_lag_days": 0},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), resp.json()
        assert resp.json()["nav_lag_days"] == 0

    def test_update_exchange_nav_lag_positive_422(self, client, admin_headers, test_db):
        """场内产品 PUT lag=1 → 422 INVALID_NAV_LAG_DAYS（跨字段）"""
        create_product(test_db, code="NL005.SH", market="CN_EXCHANGE",
                       product_type="ETF", nav_lag_days=0, confirm_days=0)
        resp = client.put(
            "/api/products/NL005.SH/CN_EXCHANGE",
            json={"nav_lag_days": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_NAV_LAG_DAYS"

    def test_update_otc_qdii_lag_one_ok(self, client, admin_headers, test_db):
        """场外 QDII lag=1 正常（回归，仅场内禁止；已由 test_update_nav_lag_days 覆盖 HK）"""
        create_product(test_db, code="NL006.OF", market="CN_OTC", nav_lag_days=1)
        resp = client.put(
            "/api/products/NL006.OF/CN_OTC",
            json={"nav_lag_days": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["nav_lag_days"] == 1

    def test_update_market_to_exchange_with_residual_lag_rejected(self, client, admin_headers, test_db):
        """CN_OTC (lag=1) → CN_EXCHANGE 未清 lag → 422（终态非法，禁静默口径翻转）"""
        create_product(test_db, code="NL007.OF", market="CN_OTC", nav_lag_days=1)
        resp = client.put(
            "/api/products/NL007.OF/CN_OTC",
            json={"market": "CN_EXCHANGE"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_NAV_LAG_DAYS"

    def test_update_market_to_exchange_with_lag_zero_ok(self, client, admin_headers, test_db):
        """CN_OTC (lag=1) → CN_EXCHANGE 且显式置 lag=0 → 成功（confirm_days 重推导 0）"""
        create_product(test_db, code="NL008.OF", market="CN_OTC", nav_lag_days=1)
        resp = client.put(
            "/api/products/NL008.OF/CN_OTC",
            json={"market": "CN_EXCHANGE", "nav_lag_days": 0},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["market"] == "CN_EXCHANGE"
        assert data["nav_lag_days"] == 0
        assert data["confirm_days"] == 0

    def test_update_nav_lag_days_null_422(self, client, admin_headers, test_db):
        """PUT 显式传 null → 422 INVALID_NAV_LAG_DAYS（service 拒绝：NOT NULL 列不允许以 null 清除）"""
        create_product(test_db, code="NL009.OF", market="CN_OTC")
        resp = client.put(
            "/api/products/NL009.OF/CN_OTC",
            json={"nav_lag_days": None},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_NAV_LAG_DAYS"


class TestConfirmDaysValidation:
    """issue #240 跟进 #6：confirm_days 取值校验——>=0；场内（CN_EXCHANGE）必须 0；显式 null 拒绝。

    与 nav_lag_days 同决策（#240 跟进 #5）：校验收在 service 层（validate_confirm_days），
    统一 422 形状（detail.error=INVALID_CONFIRM_DAYS），schema 不加 ge 约束。
    创建路径（#231/#236/#241）：显式传入优先并校验，未传按 calculate_confirm_days 推导。

    覆盖：
    - PUT 负值 / 显式 null → 422 INVALID_CONFIRM_DAYS（此前负值 200 落库、读侧 or 0 静默当日确认）
    - 场内产品 PUT confirm_days>0 → 422（场内当天确认，与推导规则一致）
    - 场外合法值通过（回归）
    - market 迁移至 CN_EXCHANGE 未传 confirm_days → 重推导 0，不误报（回归）
    - market 迁移至 CN_EXCHANGE 且显式传非 0 → 422（终态校验）
    - 创建显式传合法值落库 / 不传按推导 / 显式非法值（负值、null、场内非 0）→ 422
    """

    def test_update_confirm_days_negative_422(self, client, admin_headers, test_db):
        """PUT 传 -1 → 422 INVALID_CONFIRM_DAYS（修复前负值 200 落库）"""
        create_product(test_db, code="CD001.OF", market="CN_OTC")
        resp = client.put(
            "/api/products/CD001.OF/CN_OTC",
            json={"confirm_days": -1},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "INVALID_CONFIRM_DAYS"
        assert detail["details"]["confirm_days"] == -1

    def test_update_confirm_days_null_422(self, client, admin_headers, test_db):
        """PUT 显式传 null → 422 INVALID_CONFIRM_DAYS（列可空但读侧 or 0 静默当日确认，拒绝清除）"""
        create_product(test_db, code="CD002.OF", market="CN_OTC")
        resp = client.put(
            "/api/products/CD002.OF/CN_OTC",
            json={"confirm_days": None},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_CONFIRM_DAYS"

    def test_update_exchange_confirm_days_positive_422(self, client, admin_headers, test_db):
        """场内产品 PUT confirm_days=2 → 422 INVALID_CONFIRM_DAYS（场内当天确认，必须 0）"""
        create_product(test_db, code="CD003.SH", market="CN_EXCHANGE",
                       product_type="ETF", confirm_days=0)
        resp = client.put(
            "/api/products/CD003.SH/CN_EXCHANGE",
            json={"confirm_days": 2},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "INVALID_CONFIRM_DAYS"
        assert detail["details"]["market"] == "CN_EXCHANGE"

    def test_update_otc_confirm_days_positive_ok(self, client, admin_headers, test_db):
        """场外 PUT confirm_days=3 → 成功（回归：场外确认间隔可调）"""
        create_product(test_db, code="CD004.OF", market="CN_OTC")
        resp = client.put(
            "/api/products/CD004.OF/CN_OTC",
            json={"confirm_days": 3},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["confirm_days"] == 3

    def test_update_market_to_exchange_rederives_confirm_days_ok(self, client, admin_headers, test_db):
        """CN_OTC(confirm_days=2) → CN_EXCHANGE 未传 confirm_days → 重推导 0，不误报（终态合法）"""
        create_product(test_db, code="CD005.OF", market="CN_OTC", confirm_days=2)
        resp = client.put(
            "/api/products/CD005.OF/CN_OTC",
            json={"market": "CN_EXCHANGE"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["market"] == "CN_EXCHANGE"
        assert data["confirm_days"] == 0

    def test_update_market_to_exchange_with_explicit_confirm_days_rejected(
        self, client, admin_headers, test_db
    ):
        """CN_OTC → CN_EXCHANGE 且显式传 confirm_days=1 → 422（合并终态：场内必须 0）"""
        create_product(test_db, code="CD006.OF", market="CN_OTC")
        resp = client.put(
            "/api/products/CD006.OF/CN_OTC",
            json={"market": "CN_EXCHANGE", "confirm_days": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_CONFIRM_DAYS"

    def test_create_confirm_days_explicit_persisted(self, client, admin_headers):
        """issue #231/#236/#241：创建显式传合法值 → 落库为该值（显式优先，不再重推导）"""
        resp = client.post(
            "/api/products",
            json={"code": "CD007.OF", "market": "CN_OTC", "name": "创建显式",
                  "product_type": "OEF", "confirm_days": 2},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), resp.json()
        assert resp.json()["confirm_days"] == 2

    def test_create_confirm_days_negative_422(self, client, admin_headers):
        """创建显式传 -1 → 422 INVALID_CONFIRM_DAYS（修复前静默重推导落 1）"""
        resp = client.post(
            "/api/products",
            json={"code": "CD008.OF", "market": "CN_OTC", "name": "创建负值",
                  "product_type": "OEF", "confirm_days": -1},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "INVALID_CONFIRM_DAYS"
        assert detail["details"]["confirm_days"] == -1

    def test_create_confirm_days_null_422(self, client, admin_headers):
        """创建显式传 null → 422 INVALID_CONFIRM_DAYS（null 语义为清除，拒绝）"""
        resp = client.post(
            "/api/products",
            json={"code": "CD009.OF", "market": "CN_OTC", "name": "创建null",
                  "product_type": "OEF", "confirm_days": None},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "INVALID_CONFIRM_DAYS"

    def test_create_exchange_confirm_days_positive_422(self, client, admin_headers):
        """创建场内产品显式传 confirm_days=1 → 422（场内当天确认必须 0）"""
        resp = client.post(
            "/api/products",
            json={"code": "CD010.SH", "market": "CN_EXCHANGE", "name": "创建场内",
                  "product_type": "ETF", "confirm_days": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "INVALID_CONFIRM_DAYS"
        assert detail["details"]["market"] == "CN_EXCHANGE"

    def test_create_confirm_days_omitted_derived(self, client, admin_headers):
        """创建不传 confirm_days → 按 market+is_qdii 推导（缺省推导，与修复前行为一致）"""
        resp = client.post(
            "/api/products",
            json={"code": "CD011.OF", "market": "CN_OTC", "name": "创建缺省",
                  "product_type": "OEF"},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), resp.json()
        # CN_OTC 非 QDII → 推导 1
        assert resp.json()["confirm_days"] == 1

    def test_create_hk_mutual_confirm_days_omitted_derived(self, client, admin_headers):
        """创建互认基金不传 confirm_days → 推导 1（其他市场分支，与 QDII=2 分支互补）"""
        resp = client.post(
            "/api/products",
            json={"code": "CD012.HK", "market": "HK_MUTUAL", "name": "创建互认",
                  "product_type": "OEF"},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), resp.json()
        assert resp.json()["confirm_days"] == 1

