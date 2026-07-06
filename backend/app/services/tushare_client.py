import os
import time
from datetime import date
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
import tushare as ts

_ENV_LOADED = False


def _ensure_env_loaded():
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_paths = [
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(".env"),
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=str(env_path))
            _ENV_LOADED = True
            return
    _ENV_LOADED = True


def _get_tushare_pro():
    """获取 Tushare Pro 实例，带 Token 校验"""
    _ensure_env_loaded()
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise TushareNotConfiguredError("Tushare token 未配置，请在 .env 文件中设置 TUSHARE_TOKEN")
    return ts.pro_api(token)


class TushareNotConfiguredError(Exception):
    """Tushare 未配置错误"""
    pass


class TushareAPIError(Exception):
    """Tushare API 调用错误"""
    pass


def get_trade_calendar(year: int, exchange: str = "SSE") -> List[Dict[str, Any]]:
    """
    获取指定年份的交易日历

    Args:
        year: 年份，如 2026
        exchange: 交易所代码，SSE(上交所) 或 SZSE(深交所)，默认 SSE

    Returns:
        交易日历列表，每项包含 date(YYYY-MM-DD) 和 is_open(bool)
        例如: [{"date": "2026-01-05", "is_open": True}, ...]

    Raises:
        TushareNotConfiguredError: Tushare token 未配置
        TushareAPIError: API 调用失败
    """
    pro = _get_tushare_pro()

    start_date = f"{year}0101"
    end_date = f"{year}1231"

    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            df = pro.trade_cal(
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
                fields="cal_date,is_open"
            )
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            raise TushareAPIError(f"获取交易日历失败: {str(e)}")

    if df is None or df.empty:
        return []

    result = []
    for _, row in df.iterrows():
        cal_date = str(row["cal_date"])
        # 将 YYYYMMDD 转换为 YYYY-MM-DD
        formatted_date = f"{cal_date[:4]}-{cal_date[4:6]}-{cal_date[6:]}"
        is_open = bool(row["is_open"] == 1)
        result.append({
            "date": formatted_date,
            "is_open": is_open,
        })

    return result


def get_trade_calendar_years(years: List[int], exchange: str = "SSE") -> List[Dict[str, Any]]:
    """
    批量获取多个年份的交易日历

    Args:
        years: 年份列表
        exchange: 交易所代码

    Returns:
        合并后的交易日历列表
    """
    all_dates = []
    for year in years:
        dates = get_trade_calendar(year, exchange)
        all_dates.extend(dates)
    return all_dates


def get_fund_daily(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    获取场内基金日线行情（收盘价）

    Args:
        ts_code: 基金代码（如 510300.SH）
        start_date: 开始日期（YYYYMMDD），不传则返回从有数据以来的全部记录
        end_date: 结束日期（YYYYMMDD），不传则到最新日期

    Returns:
        行情数据列表，包含 trade_date, close, pre_close, pct_chg 等
    """
    pro = _get_tushare_pro()

    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            kwargs = {"ts_code": ts_code}
            if start_date:
                kwargs["start_date"] = start_date
            if end_date:
                kwargs["end_date"] = end_date
            df = pro.fund_daily(**kwargs)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            raise TushareAPIError(f"获取基金日线行情失败: {str(e)}")

    if df is None or df.empty:
        return []

    result = []
    for _, row in df.iterrows():
        result.append({
            "trade_date": str(row["trade_date"]),
            "close": float(row["close"]) if row.get("close") else None,
            "pre_close": float(row["pre_close"]) if row.get("pre_close") else None,
            "pct_chg": float(row["pct_chg"]) if row.get("pct_chg") else None,
        })

    return result


def get_fund_nav(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    获取场外基金净值数据

    Args:
        ts_code: 基金代码（如 000001.OF）
        start_date: 开始日期（YYYYMMDD），不传则返回从有数据以来的全部记录
        end_date: 结束日期（YYYYMMDD），不传则到最新日期

    Returns:
        净值数据列表，包含 trade_date, unit_nav, accum_nav 等
    """
    pro = _get_tushare_pro()

    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            kwargs = {"ts_code": ts_code}
            if start_date:
                kwargs["start_date"] = start_date
            if end_date:
                kwargs["end_date"] = end_date
            df = pro.fund_nav(**kwargs)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            raise TushareAPIError(f"获取基金净值失败: {str(e)}")

    if df is None or df.empty:
        return []

    result = []
    for _, row in df.iterrows():
        result.append({
            "trade_date": str(row["nav_date"]) if row.get("nav_date") else None,
            "unit_nav": float(row["unit_nav"]) if row.get("unit_nav") else None,
            "accum_nav": float(row["accum_nav"]) if row.get("accum_nav") else None,
        })

    return result
