# ============================================================================
# 单元测试：产品市场解析 resolve_product_market (issue #83)
# ============================================================================
# 三分支覆盖：
# - market 非空原样返回（透传，不查库）
# - 省略且唯一市场：自动补全
# - 省略且多市场（LOF 一码多市场）：MARKET_AMBIGUOUS(422)
# - 省略且不存在：PRODUCT_NOT_FOUND(404)
# ============================================================================

import pytest

from app.services.product_service import resolve_product_market
from app.services.exceptions import BusinessError, NotFoundError
from tests.factories import create_product


class TestResolveProductMarket:
    def test_explicit_market_passthrough(self, test_db):
        """market 非空时原样返回，不做存在性校验"""
        assert resolve_product_market(test_db, "ANY_CODE", "CN_OTC") == (
            "ANY_CODE", "CN_OTC",
        )

    def test_unique_market_autofill(self, test_db):
        """唯一市场自动补全"""
        create_product(test_db, code="RSLV01.OF", market="CN_OTC")
        assert resolve_product_market(test_db, "RSLV01.OF") == (
            "RSLV01.OF", "CN_OTC",
        )

    def test_product_not_found(self, test_db):
        """code 不存在抛 PRODUCT_NOT_FOUND(404)，details 携带 product_code"""
        with pytest.raises(NotFoundError) as exc_info:
            resolve_product_market(test_db, "NO_SUCH_CODE")
        err = exc_info.value
        assert err.code == "PRODUCT_NOT_FOUND"
        assert err.http_status == 404
        assert err.details == {"product_code": "NO_SUCH_CODE"}

    def test_multi_market_ambiguous(self, test_db):
        """LOF 一码多市场抛 MARKET_AMBIGUOUS(422)，available_markets 排序返回"""
        create_product(test_db, code="RSLV_LOF", market="CN_OTC", product_type="LOF")
        create_product(test_db, code="RSLV_LOF", market="CN_EXCHANGE", product_type="LOF")
        with pytest.raises(BusinessError) as exc_info:
            resolve_product_market(test_db, "RSLV_LOF")
        err = exc_info.value
        assert err.code == "MARKET_AMBIGUOUS"
        assert err.http_status == 422
        assert err.details == {
            "product_code": "RSLV_LOF",
            "available_markets": ["CN_EXCHANGE", "CN_OTC"],
        }
