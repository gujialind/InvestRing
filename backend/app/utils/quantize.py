"""
份额精度量化工具

份额统一 2 位小数（净值 4 位小数、投资人确认份额 2 位小数），
舍入模式为 ROUND_HALF_UP（四舍五入，第 3 位 >= 5 进位）。场外基金行业惯例
即四舍五入保留 2 位，由此产生的微小误差计入基金财产（issue #87）。

量化职责在「份额产生点」（写入路径）：
- 申购确认份额（amount / nav）、调仓买入份额（amount / price）
- 卖出/赎回的用户输入份额（先量化到 2 位再做精确校验）
- 份额变动事件的 shares_change / shares_after 计算

读取/累加/校验路径不量化：2 位小数的份额相加减仍是 2 位小数，
可用份额比较保持精确（不引入容差）。
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Union

SHARES_QUANT = Decimal("0.01")


def quantize_shares(value: Optional[Union[Decimal, float, int, str]]) -> Optional[Decimal]:
    """将份额量化为 2 位小数（ROUND_HALF_UP，四舍五入）。

    负数语义：与正数对称，按绝对值四舍五入、远离零进位
    （如 1.235 → 1.24，-1.235 → -1.24，-1.234 → -1.23）。

    None 原样返回，方便可空字段直接透传。
    """
    if value is None:
        return None
    return Decimal(str(value)).quantize(SHARES_QUANT, rounding=ROUND_HALF_UP)
