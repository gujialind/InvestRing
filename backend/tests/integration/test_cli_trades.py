# ============================================================================
# 集成测试：CLI ir trade create (test_cli_trades.py)
# ============================================================================
# 覆盖 #53 跟进：CLI trade create 对齐 router
#   - 基金 buy/sell 生成配对 CASH 腿 + 共享 transfer_group
#   - 禁止直接创建裸 CASH 交易
# ============================================================================

import json

import pytest
from datetime import date
from typer.testing import CliRunner

from cli.commands.trades import app as trades_app
from tests.factories import (
    create_portfolio, create_product, create_platform, create_trade,
    ensure_trading_day,
)
from app.models.trade import Trade


runner = CliRunner()


@pytest.fixture
def cli_db(test_db, monkeypatch):
    """让 CLI 的 cli_context 复用测试会话。

    - SessionLocal() 返回 test_db（cli_context 内部运行时 import，可被 patch）
    - commit -> flush：数据落入测试事务但不真正提交，保持测试间隔离
    - close -> no-op：避免 cli_context 关闭测试共享会话
    """
    monkeypatch.setattr(test_db, "close", lambda: None)
    monkeypatch.setattr(test_db, "commit", test_db.flush)
    monkeypatch.setattr("app.database.SessionLocal", lambda: test_db)
    return test_db


def _parse(output: str) -> dict:
    """从 CLI stdout 中解析最后一行 JSON。"""
    lines = [ln for ln in output.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1])


class TestCliCashTradeForbidden:
    """CLI 禁止直接创建裸 CASH 交易"""

    def test_cli_create_cash_trade_rejected(self, cli_db):
        create_portfolio(cli_db, code="CLI_FBD", status="active")
        create_platform(cli_db, code="CLI_FBD_PLAT")
        ensure_trading_day(cli_db, date(2025, 10, 6), is_open=True)

        result = runner.invoke(trades_app, [
            "create",
            "--portfolio-code", "CLI_FBD",
            "--product-code", "CASH",
            "--market", "",
            "--type", "buy",
            "--actual-amount", "10000",
            "--platform-code", "CLI_FBD_PLAT",
            "--trade-date", "2025-10-06",
        ])
        assert result.exit_code == 1, result.output
        payload = _parse(result.output)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "CASH_TRADE_FORBIDDEN"


class TestCliPairedCashLeg:
    """CLI 基金买入生成共享 transfer_group 的配对 CASH 腿"""

    def test_cli_fund_buy_generates_paired_cash_leg(self, cli_db):
        create_portfolio(cli_db, code="CLI_P1", status="active")
        create_product(cli_db, code="ETF_CLI", market="CN_EXCHANGE",
                       product_type="ETF", asset_class_code="STOCK_CN_LARGE",
                       confirm_days=0)
        create_platform(cli_db, code="CLI_PLAT")
        ensure_trading_day(cli_db, date(2025, 10, 6), is_open=True)
        # 提供可用现金
        create_trade(
            cli_db, "CLI_P1", "CASH", "",
            trade_type="buy", amount=50000.0, price=None,
            platform_code="CLI_PLAT", trade_date=date(2025, 10, 3),
            confirm_date=date(2025, 10, 3), status="confirmed",
        )

        result = runner.invoke(trades_app, [
            "create",
            "--portfolio-code", "CLI_P1",
            "--product-code", "ETF_CLI",
            "--market", "CN_EXCHANGE",
            "--type", "buy",
            "--actual-amount", "10000",
            "--price", "1.5",
            "--platform-code", "CLI_PLAT",
            "--trade-date", "2025-10-06",
        ])
        assert result.exit_code == 0, result.output
        payload = _parse(result.output)
        assert payload["ok"] is True
        fund_id = payload["data"]["id"]

        fund_leg = cli_db.query(Trade).filter(Trade.id == fund_id).first()
        assert fund_leg is not None
        assert fund_leg.transfer_group is not None
        assert fund_leg.transfer_group.startswith("rebal_")

        paired = cli_db.query(Trade).filter(
            Trade.transfer_group == fund_leg.transfer_group,
            Trade.id != fund_id,
        ).all()
        assert len(paired) == 1
        assert paired[0].product_code == "CASH"
        assert paired[0].trade_type == "sell"
        assert float(paired[0].amount) == 10000.0
