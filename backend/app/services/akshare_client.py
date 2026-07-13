"""AkShare 客户端 — 与 tushare_client.py 平级。

⚠️ 本文件为 stub：函数签名已定义，但具体 akshare 接口调用和字段映射需 PoC 后补全。
akshare 未安装时，调用会抛 AkshareAPIError，不影响 tushare 主路径。
"""
import time
import logging
from typing import List, Dict, Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class AkshareAPIError(Exception):
    """AkShare API 调用错误"""
    pass


def _rate_limit_sleep():
    time.sleep(get_settings().akshare_rate_interval)


def _retry(func, error_label: str):
    settings = get_settings()
    max_retries = settings.akshare_max_retries
    delay = 1
    for attempt in range(max_retries):
        _rate_limit_sleep()
        try:
            return func()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise AkshareAPIError(f"{error_label}: {e}")


def get_fund_nav_otc(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    场外基金净值（CN_OTC）。
    symbol: 基金代码（如 '000051' 或 '000051.OF'，取 . 前部分）
    返回统一结构: {trade_date: 'YYYYMMDD', unit_nav, accum_nav}
    """
    try:
        import akshare as ak
    except ImportError:
        raise AkshareAPIError("akshare 未安装，请 pip install akshare")

    code = symbol.split(".")[0]

    def _fetch():
        # TODO(PoC): 实测 fund_open_fund_info_em 返回的 DataFrame 列名后补全映射
        # 预期: ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        # 需映射列名 -> {trade_date: YYYYMMDD, unit_nav, accum_nav}
        raise AkshareAPIError("get_fund_nav_otc 尚未实现（需 PoC 确认 akshare 字段名）")

    return _retry(_fetch, "获取场外基金净值失败")


def get_fund_daily_exchange(
    etf_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    场内 ETF 日线（CN_EXCHANGE）。
    返回统一结构: {trade_date: 'YYYYMMDD', close, pre_close, pct_change}
    """
    try:
        import akshare as ak
    except ImportError:
        raise AkshareAPIError("akshare 未安装，请 pip install akshare")

    def _fetch():
        # TODO(PoC): 实测 fund_etf_hist_em 返回的 DataFrame 列名后补全映射
        # 预期: ak.fund_etf_hist_em(symbol=etf_code, period="daily", adjust="")
        # 需映射列名 -> {trade_date: YYYYMMDD, close, pre_close, pct_change}
        raise AkshareAPIError("get_fund_daily_exchange 尚未实现（需 PoC 确认 akshare 字段名）")

    return _retry(_fetch, "获取场内 ETF 日线失败")


def get_fund_hk_mutual(
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    香港互认基金净值（HK_MUTUAL）。
    code: 内地销售代码（如 '1001767344'），格式需实测确认。
    返回统一结构: {trade_date: 'YYYYMMDD', unit_price, accumulated_nav}
    """
    try:
        import akshare as ak
    except ImportError:
        raise AkshareAPIError("akshare 未安装，请 pip install akshare")

    def _fetch():
        # TODO(PoC): 确认 akshare 香港基金历史净值明细接口函数名和参数
        # 天天基金网香港基金接口，code 格式可能是 10 位内地代码或另有映射
        # 需实测确认后补全
        raise AkshareAPIError("get_fund_hk_mutual 尚未实现（需 PoC 确认 akshare 香港基金接口和 code 格式）")

    return _retry(_fetch, "获取香港互认基金净值失败")
