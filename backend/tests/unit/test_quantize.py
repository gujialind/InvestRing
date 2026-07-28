# ============================================================================
# 单元测试：份额精度量化工具 (test_quantize.py)
# ============================================================================
# 覆盖 app/utils/quantize.py::quantize_shares：
# - ROUND_DOWN 行为（第 3 位直接舍去，不四舍五入）
# - None 透传
# - Decimal / float / int / str 输入兼容
# ============================================================================

import pytest
from decimal import Decimal

from app.utils.quantize import SHARES_QUANT, quantize_shares


class TestQuantizeShares:
    """quantize_shares 基本行为"""

    def test_round_down_truncates_third_decimal(self):
        """第 3 位直接舍去，不四舍五入"""
        assert quantize_shares(Decimal("6837.2967")) == Decimal("6837.29")
        assert quantize_shares(Decimal("6837.299")) == Decimal("6837.29")
        # 即使第 3 位 >= 5 也不进位
        assert quantize_shares(Decimal("6837.295")) == Decimal("6837.29")
        assert quantize_shares(Decimal("0.019")) == Decimal("0.01")

    def test_already_two_decimals_unchanged(self):
        """已是 2 位小数的值保持不变"""
        assert quantize_shares(Decimal("6837.30")) == Decimal("6837.30")
        assert quantize_shares(Decimal("6837.29")) == Decimal("6837.29")
        assert quantize_shares(Decimal("0")) == Decimal("0.00")

    def test_result_exponent_is_two_decimals(self):
        """结果统一量化到 0.01（exponent = -2）"""
        assert quantize_shares(Decimal("100")).as_tuple().exponent == -2
        assert quantize_shares(Decimal("6837.2967")).as_tuple().exponent == -2

    def test_none_passthrough(self):
        """None 原样返回，方便可空字段透传"""
        assert quantize_shares(None) is None

    def test_float_input(self):
        """float 输入经 str 转换后量化，无二进制浮点误差"""
        assert quantize_shares(6837.2967) == Decimal("6837.29")
        assert quantize_shares(6837.29) == Decimal("6837.29")

    def test_str_input(self):
        """str 输入直接量化"""
        assert quantize_shares("6837.2967") == Decimal("6837.29")
        assert quantize_shares("6837.30") == Decimal("6837.30")

    def test_int_input(self):
        """int 输入量化为 2 位小数"""
        assert quantize_shares(6837) == Decimal("6837.00")

    def test_division_result_round_down(self):
        """申购确认典型场景：amount / nav 除不尽时向下舍去"""
        # 10000 / 1.4623 = 6838.5426...，ROUND_DOWN → 6838.54
        shares = quantize_shares(Decimal("10000") / Decimal("1.4623"))
        assert shares == Decimal("6838.54")

    def test_shares_quant_constant(self):
        """SHARES_QUANT 为 0.01（2 位小数口径）"""
        assert SHARES_QUANT == Decimal("0.01")
