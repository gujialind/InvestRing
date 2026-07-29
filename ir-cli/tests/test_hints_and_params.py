"""
错误就近提示与参数风格统一测试（issue #86/#81）

覆盖：
- get_hint 按 details 动态插值（MARKET_AMBIGUOUS/PRODUCT_NOT_FOUND/INSUFFICIENT_SHARES）
- 无动态规则时 fallback 静态表；未知错误码返回 None
- output.error 缺省 hints 时按 code+details 自动生成
- available-cash/available-shares 双通道参数：--portfolio-code option 优先、
  位置参数弃用告警走 stderr（stdout 仍为纯 JSON）、两者皆缺报 VALIDATION_ERROR

运行方式（ir-cli/.venv 无 pytest，用仓库根 .venv）：
    PYTHONPATH=ir-cli .venv/bin/python -m pytest ir-cli/tests/ -q
"""
import json

import pytest
from typer.testing import CliRunner

from ir_cli.client import APIClient
from ir_cli.hints import ERROR_HINTS, get_hint
from ir_cli.main import app
from ir_cli.output import error


class TestGetHint:
    """get_hint 动态插值与静态 fallback"""

    def test_market_ambiguous_interpolates_available_markets(self):
        hint = get_hint("MARKET_AMBIGUOUS", {"product_code": "161005", "available_markets": ["CN_OTC", "CN_SH"]})
        assert "--market" in hint
        assert "CN_OTC, CN_SH" in hint

    def test_market_ambiguous_without_details_falls_back_static(self):
        assert get_hint("MARKET_AMBIGUOUS") == ERROR_HINTS["MARKET_AMBIGUOUS"]
        assert get_hint("MARKET_AMBIGUOUS", {"http_status": 409}) == ERROR_HINTS["MARKET_AMBIGUOUS"]

    def test_product_not_found_with_available_markets(self):
        hint = get_hint("PRODUCT_NOT_FOUND", {"product_code": "161005.OF", "available_markets": ["CN_SZ"]})
        assert "161005.OF" in hint
        assert "CN_SZ" in hint

    def test_product_not_found_without_markets_falls_back_static(self):
        hint = get_hint("PRODUCT_NOT_FOUND", {"product_code": "999999.OF"})
        assert hint == ERROR_HINTS["PRODUCT_NOT_FOUND"]
        assert "ir product list" in hint

    def test_not_found_with_available_markets(self):
        hint = get_hint("NOT_FOUND", {"product_code": "161005.OF", "available_markets": ["CN_SH", "CN_SZ"]})
        assert "CN_SH, CN_SZ" in hint

    def test_not_found_without_markets_falls_back_static(self):
        assert get_hint("NOT_FOUND", {"http_status": 404}) == ERROR_HINTS["NOT_FOUND"]

    def test_insufficient_shares_interpolates_available_shares(self):
        hint = get_hint("INSUFFICIENT_SHARES", {"available_shares": 1234.56})
        assert "1234.56" in hint

    def test_insufficient_shares_without_details_falls_back_static(self):
        assert get_hint("INSUFFICIENT_SHARES") == ERROR_HINTS["INSUFFICIENT_SHARES"]

    def test_unknown_code_returns_none(self):
        assert get_hint("SOME_UNKNOWN_CODE") is None
        assert get_hint("SOME_UNKNOWN_CODE", {"available_markets": ["CN_SH"]}) is None

    def test_static_table_new_entries_present(self):
        for code in ("NOT_FOUND", "PRODUCT_NOT_FOUND", "MARKET_AMBIGUOUS",
                     "CONFIRM_REQUIRED", "NO_SNAPSHOT_BASELINE", "CALENDAR_NOT_SYNCED"):
            assert ERROR_HINTS.get(code), f"静态表缺少 {code}"

    def test_static_entries_recommend_new_commands(self):
        assert "catch-up" in ERROR_HINTS["SNAPSHOT_NOT_CONTINUOUS"]
        assert "catch-up" in ERROR_HINTS["NAV_NOT_AVAILABLE"]
        assert "calendar-sync" in ERROR_HINTS["CALENDAR_NOT_SYNCED"]
        assert "--dry-run" in ERROR_HINTS["CONFIRM_REQUIRED"]
        assert "--portfolio-code" in ERROR_HINTS["INSUFFICIENT_CASH"]
        assert "--portfolio-code" in ERROR_HINTS["INSUFFICIENT_SHARES"]


class TestErrorOutputDynamicHints:
    """output.error 缺省 hints 时按 code+details 自动生成"""

    def test_error_emits_interpolated_hint(self, capsys):
        with pytest.raises(SystemExit) as ei:
            error("MARKET_AMBIGUOUS", "产品 161005 存在多个市场",
                  details={"product_code": "161005", "available_markets": ["CN_OTC", "CN_SH"]})
        assert ei.value.code == 1
        doc = json.loads(capsys.readouterr().out)
        assert doc["ok"] is False
        assert any("CN_OTC, CN_SH" in h for h in doc["error"]["hints"])

    def test_explicit_hints_take_precedence(self, capsys):
        with pytest.raises(SystemExit):
            error("MARKET_AMBIGUOUS", "msg",
                  details={"available_markets": ["CN_SH"]}, hints=["自定义提示"])
        doc = json.loads(capsys.readouterr().out)
        assert doc["error"]["hints"] == ["自定义提示"]


class _StubClient:
    """记录请求路径并返回固定响应的假客户端"""

    def __init__(self):
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        return {"data": {"available_cash": 100.0}}


@pytest.fixture
def stub_client(monkeypatch):
    stub = _StubClient()
    monkeypatch.setattr(APIClient, "from_config", classmethod(lambda cls, require_auth=True: stub))
    return stub


def _runner() -> CliRunner:
    try:
        # click <8.2 默认混流，需显式分离 stderr；click >=8.2 无此参数且默认分离
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


class TestAvailableCashDualChannel:
    """available-cash 双通道参数（issue #81）"""

    def test_option_style(self, stub_client):
        result = _runner().invoke(app, ["position", "available-cash", "--portfolio-code", "PORT001"])
        assert result.exit_code == 0
        doc = json.loads(result.stdout)
        assert doc["ok"] is True
        assert stub_client.calls[0][0] == "/api/positions/portfolio/PORT001/available-cash"
        assert "弃用" not in result.stderr

    def test_positional_style_warns_on_stderr(self, stub_client):
        result = _runner().invoke(app, ["position", "available-cash", "PORT001"])
        assert result.exit_code == 0
        # stdout 保持纯 JSON，弃用告警只出现在 stderr
        doc = json.loads(result.stdout)
        assert doc["ok"] is True
        assert "弃用" in result.stderr
        assert "--portfolio-code" in result.stderr
        assert stub_client.calls[0][0] == "/api/positions/portfolio/PORT001/available-cash"

    def test_option_takes_precedence_over_positional(self, stub_client):
        result = _runner().invoke(
            app, ["position", "available-cash", "OLD001", "--portfolio-code", "NEW001"]
        )
        assert result.exit_code == 0
        assert stub_client.calls[0][0] == "/api/positions/portfolio/NEW001/available-cash"

    def test_missing_both_reports_validation_error(self, stub_client):
        result = _runner().invoke(app, ["position", "available-cash"])
        assert result.exit_code == 1
        doc = json.loads(result.stdout)
        assert doc["error"]["code"] == "VALIDATION_ERROR"
        assert "--portfolio-code" in doc["error"]["message"]
        assert stub_client.calls == []


class TestAvailableSharesDualChannel:
    """available-shares 双通道参数（issue #81）"""

    def test_option_style(self, stub_client):
        result = _runner().invoke(app, [
            "position", "available-shares",
            "--portfolio-code", "PORT001", "--product-code", "022959.OF",
        ])
        assert result.exit_code == 0
        assert stub_client.calls[0][0] == (
            "/api/positions/portfolio/PORT001/product/022959.OF/available-shares"
        )

    def test_positional_style_warns_on_stderr(self, stub_client):
        result = _runner().invoke(app, ["position", "available-shares", "PORT001", "022959.OF"])
        assert result.exit_code == 0
        assert "弃用" in result.stderr
        assert stub_client.calls[0][0] == (
            "/api/positions/portfolio/PORT001/product/022959.OF/available-shares"
        )

    def test_missing_product_code_reports_validation_error(self, stub_client):
        result = _runner().invoke(app, ["position", "available-shares", "--portfolio-code", "PORT001"])
        assert result.exit_code == 1
        doc = json.loads(result.stdout)
        assert doc["error"]["code"] == "VALIDATION_ERROR"
        assert "--product-code" in doc["error"]["message"]
