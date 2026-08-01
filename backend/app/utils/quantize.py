"""
份额/金额精度量化工具

精度体系：份额 2 位小数、金额 2 位小数、净值 4 位小数，
舍入模式均为 ROUND_HALF_UP（四舍五入，第 3 位 >= 5 进位）。场外基金行业惯例
即四舍五入保留 2 位，由此产生的微小误差计入基金财产
（份额 issue #87、金额 issue #94）。

量化职责在「产生点」（写入路径）：
- 份额：申购确认份额（amount / nav）、调仓买入份额（amount / price）、
  卖出/赎回的用户输入份额（先量化到 2 位再做精确校验）、
  份额变动事件的 shares_change / shares_after 计算
- 金额：卖出/赎回确认金额（shares × nav）、买入金额与手续费的用户输入、
  申赎金额、现金分红 cash_change（entitlement_shares × div_cash）、
  forced_adjustment 用户填写 cash_change、manual_market_value 写入、
  现金转移金额

读取/累加/校验路径不量化：2 位小数的份额/金额相加减仍是 2 位小数，
可用份额/可用现金比较保持精确（不引入容差）。
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Union

SHARES_QUANT = Decimal("0.01")
AMOUNT_QUANT = Decimal("0.01")


def quantize_shares(value: Optional[Union[Decimal, float, int, str]]) -> Optional[Decimal]:
    """将份额量化为 2 位小数（ROUND_HALF_UP，四舍五入）。

    负数语义：与正数对称，按绝对值四舍五入、远离零进位
    （如 1.235 → 1.24，-1.235 → -1.24，-1.234 → -1.23）。

    None 原样返回，方便可空字段直接透传。
    """
    if value is None:
        return None
    return Decimal(str(value)).quantize(SHARES_QUANT, rounding=ROUND_HALF_UP)


def quantize_amount(value: Optional[Union[Decimal, float, int, str]]) -> Optional[Decimal]:
    """将金额量化为 2 位小数（ROUND_HALF_UP，四舍五入）。

    金额口径与真实交易平台一致（分），量化误差（< 0.005）计入基金财产。
    负数语义与 quantize_shares 相同：按绝对值四舍五入、远离零进位
    （如 7537.43952 → 7537.44，-1.235 → -1.24）。

    None 原样返回，方便可空字段直接透传。
    """
    if value is None:
        return None
    return Decimal(str(value)).quantize(AMOUNT_QUANT, rounding=ROUND_HALF_UP)
