# ============================================================================
# 集成测试：CLI 与 REST 经由同一 service 的分层对齐 parity (test_cli_service_parity.py)
# ============================================================================
# 验证 backend/cli 命令改为委托 service 后，与 REST 端点产生一致副作用/错误码：
#   - 现金重估：CLI 与 REST 均写 manual_market_value，且不直接写 portfolio_position（#8）
#   - confirm_days：CLI 与 REST 共用 product_service.calculate_confirm_days 单一实现
#   - 组合关闭：closed_at 落库 + PENDING_TRANSACTIONS_EXIST 拦截
#   - 平台间现金转移：对称状态模型（跨天两腿 pending / 当天两腿 confirmed）
# ============================================================================

import json

import pytest
from datetime import date
from typer.testing import CliRunner

from cli.commands.positions import app as positions_app
from cli.commands.products import app as products_app
from cli.commands.portfolios import app as portfolios_app
from cli.commands.cash_transfers import app as cash_transfers_app
from tests.factories import (
    create_portfolio, create_product, create_platform, create_trade,
    ensure_trading_day,
)
from app.models.manual_market_value import ManualMarketValue
from app.models.portfolio_position import PortfolioPosition
from app.models.product import Product
from app.models.portfolio import Portfolio
from app.models.trade import Trade


runner = CliRunner()

TRADING_DAY = date(2025, 6, 2)  # 周一，落在测试交易日历（2025-2026 工作日开市）内


@pytest.fixture
def cli_db(test_db, monkeypatch):
    """让 CLI 的 cli_context 复用测试会话（与 test_cli_trades.py 同构）。

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


class TestCashPositionParity:
    """现金重估：REST 与 CLI 均写 manual_market_value，均不写 portfolio_position（#8）。"""

    def test_rest_update_cash_writes_manual_market_value(self, client, admin_headers, test_db):
        create_portfolio(test_db, code="PAR_MMV_R", status="active")
        ensure_trading_day(test_db, TRADING_DAY, is_open=True)

        resp = client.post(
            "/api/positions/portfolio/PAR_MMV_R/cash-position",
            json={"amount": 12345.67, "platform_code": "MYCF",
                  "update_date": TRADING_DAY.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["requires_snapshot_regen"] is True

        mmv = test_db.query(ManualMarketValue).filter(
            ManualMarketValue.portfolio_code == "PAR_MMV_R",
            ManualMarketValue.platform_code == "MYCF",
            ManualMarketValue.product_code == "CASH",
            ManualMarketValue.date == TRADING_DAY,
        ).first()
        assert mmv is not None
        assert float(mmv.market_value) == pytest.approx(12345.67)

        # 关键：不得直接写快照表 portfolio_position
        cash_pos = test_db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == "PAR_MMV_R",
            PortfolioPosition.product_code == "CASH",
            PortfolioPosition.snapshot_date == TRADING_DAY,
        ).first()
        assert cash_pos is None

    def test_cli_update_cash_writes_manual_market_value(self, cli_db):
        create_portfolio(cli_db, code="PAR_MMV_C", status="active")
        ensure_trading_day(cli_db, TRADING_DAY, is_open=True)

        result = runner.invoke(positions_app, [
            "update-cash", "PAR_MMV_C",
            "--platform-code", "MYCF",
            "--amount", "12345.67",
            "--update-date", TRADING_DAY.isoformat(),
        ])
        assert result.exit_code == 0, result.output
        payload = _parse(result.output)
        assert payload["ok"] is True
        assert payload["data"]["requires_snapshot_regen"] is True

        mmv = cli_db.query(ManualMarketValue).filter(
            ManualMarketValue.portfolio_code == "PAR_MMV_C",
            ManualMarketValue.platform_code == "MYCF",
            ManualMarketValue.product_code == "CASH",
            ManualMarketValue.date == TRADING_DAY,
        ).first()
        assert mmv is not None
        assert float(mmv.market_value) == pytest.approx(12345.67)

        cash_pos = cli_db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == "PAR_MMV_C",
            PortfolioPosition.product_code == "CASH",
            PortfolioPosition.snapshot_date == TRADING_DAY,
        ).first()
        assert cash_pos is None

    def test_cli_update_cash_non_trading_day_rejected(self, cli_db):
        create_portfolio(cli_db, code="PAR_MMV_N", status="active")
        ensure_trading_day(cli_db, date(2025, 6, 1), is_open=False)  # 周日

        result = runner.invoke(positions_app, [
            "update-cash", "PAR_MMV_N",
            "--platform-code", "MYCF",
            "--amount", "1000",
            "--update-date", "2025-06-01",
        ])
        assert result.exit_code == 1, result.output
        payload = _parse(result.output)
        assert payload["error"]["code"] == "NON_TRADING_DAY"


class TestProductConfirmDaysParity:
    """confirm_days 单一实现：CN_EXCHANGE=0 / CN_OTC 非 QDII=1 / CN_OTC QDII=2。"""

    def test_cli_cn_otc_non_qdii_confirm_days_1(self, cli_db):
        result = runner.invoke(products_app, [
            "create", "--code", "PAR_OTC.OF", "--market", "CN_OTC",
            "--name", "场外非QDII", "--product-type", "OEF",
            "--asset-class-code", "STOCK_CN_LARGE",
        ])
        assert result.exit_code == 0, result.output
        payload = _parse(result.output)
        assert payload["data"]["confirm_days"] == 1

    def test_cli_cn_exchange_confirm_days_0(self, cli_db):
        result = runner.invoke(products_app, [
            "create", "--code", "PAR_EXC.SH", "--market", "CN_EXCHANGE",
            "--name", "场内", "--product-type", "ETF",
            "--asset-class-code", "STOCK_CN_LARGE",
        ])
        assert result.exit_code == 0, result.output
        payload = _parse(result.output)
        assert payload["data"]["confirm_days"] == 0

    def test_cli_cn_otc_qdii_confirm_days_2(self, cli_db):
        result = runner.invoke(products_app, [
            "create", "--code", "PAR_QDII.OF", "--market", "CN_OTC",
            "--name", "场外QDII", "--product-type", "OEF",
            "--asset-class-code", "STOCK_CN_LARGE", "--is-qdii",
        ])
        assert result.exit_code == 0, result.output
        payload = _parse(result.output)
        assert payload["data"]["confirm_days"] == 2

    def test_rest_cn_otc_non_qdii_confirm_days_1(self, client, admin_headers, test_db):
        resp = client.post(
            "/api/products",
            json={"code": "PAR_OTC_R.OF", "market": "CN_OTC", "name": "场外非QDII",
                  "product_type": "OEF", "asset_class_code": "STOCK_CN_LARGE",
                  "is_qdii": False},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201), resp.text
        assert resp.json()["confirm_days"] == 1


class TestPortfolioCloseParity:
    """组合关闭：closed_at 落库；存在 pending 交易时拒绝。"""

    def test_cli_close_sets_closed_at(self, cli_db):
        create_portfolio(cli_db, code="PAR_CLOSE_OK", status="active")
        result = runner.invoke(portfolios_app, ["close", "PAR_CLOSE_OK", "--yes"])
        assert result.exit_code == 0, result.output
        payload = _parse(result.output)
        assert payload["data"]["status"] == "closed"
        assert payload["data"]["closed_at"] is not None

        port = cli_db.query(Portfolio).filter(Portfolio.code == "PAR_CLOSE_OK").first()
        assert port.status == "closed"
        assert port.closed_at is not None

    def test_cli_close_rejects_pending_trades(self, cli_db):
        create_portfolio(cli_db, code="PAR_CLOSE_PEND", status="active")
        create_trade(
            cli_db, "PAR_CLOSE_PEND", "CASH", "",
            trade_type="buy", amount=1000.0, price=None,
            platform_code="MYCF", trade_date=TRADING_DAY, status="pending",
        )
        result = runner.invoke(portfolios_app, ["close", "PAR_CLOSE_PEND", "--yes"])
        assert result.exit_code == 1, result.output
        payload = _parse(result.output)
        assert payload["error"]["code"] == "PENDING_TRANSACTIONS_EXIST"


class TestCashTransferSymmetricParity:
    """平台间现金转移对称状态：跨天两腿 pending / 当天两腿 confirmed。"""

    def _seed_cash(self, db, portfolio_code, platform_code, amount=50000.0):
        create_portfolio(db, code=portfolio_code, status="active")
        create_platform(db, code=platform_code)
        create_trade(
            db, portfolio_code, "CASH", "",
            trade_type="buy", amount=amount, price=None,
            platform_code=platform_code, trade_date=date(2025, 6, 2),
            confirm_date=date(2025, 6, 2), status="confirmed",
        )

    def test_cli_cross_day_both_legs_pending(self, cli_db):
        self._seed_cash(cli_db, "PAR_XFER_X", "MYCF")
        create_platform(cli_db, code="HBZQ")
        ensure_trading_day(cli_db, TRADING_DAY, is_open=True)
        ensure_trading_day(cli_db, date(2025, 6, 3), is_open=True)

        result = runner.invoke(cash_transfers_app, [
            "create", "--portfolio-code", "PAR_XFER_X",
            "--from", "MYCF", "--to", "HBZQ",
            "--amount", "10000", "--date", TRADING_DAY.isoformat(),
            "--cross-day",
        ])
        assert result.exit_code == 0, result.output
        data = _parse(result.output)["data"]
        assert data["cross_day"] is True
        assert data["sell_status"] == "pending"
        assert data["buy_status"] == "pending"

        legs = cli_db.query(Trade).filter(
            Trade.transfer_group == data["transfer_group"]
        ).all()
        assert len(legs) == 2
        for leg in legs:
            assert leg.status == "pending"
            assert leg.confirm_date is not None
            assert leg.confirm_date > leg.trade_date  # 对称：确认日推到次交易日

    def test_cli_same_day_both_legs_confirmed(self, cli_db):
        self._seed_cash(cli_db, "PAR_XFER_S", "MYCF")
        create_platform(cli_db, code="HBZQ")
        ensure_trading_day(cli_db, TRADING_DAY, is_open=True)

        result = runner.invoke(cash_transfers_app, [
            "create", "--portfolio-code", "PAR_XFER_S",
            "--from", "MYCF", "--to", "HBZQ",
            "--amount", "10000", "--date", TRADING_DAY.isoformat(),
        ])
        assert result.exit_code == 0, result.output
        data = _parse(result.output)["data"]
        assert data["cross_day"] is False
        assert data["sell_status"] == "confirmed"
        assert data["buy_status"] == "confirmed"

        legs = cli_db.query(Trade).filter(
            Trade.transfer_group == data["transfer_group"]
        ).all()
        assert len(legs) == 2
        for leg in legs:
            assert leg.status == "confirmed"
            assert leg.confirm_date == TRADING_DAY

    def test_cli_same_platform_rejected(self, cli_db):
        self._seed_cash(cli_db, "PAR_XFER_SP", "MYCF")
        ensure_trading_day(cli_db, TRADING_DAY, is_open=True)

        result = runner.invoke(cash_transfers_app, [
            "create", "--portfolio-code", "PAR_XFER_SP",
            "--from", "MYCF", "--to", "MYCF",
            "--amount", "10000", "--date", TRADING_DAY.isoformat(),
        ])
        assert result.exit_code == 1, result.output
        payload = _parse(result.output)
        assert payload["error"]["code"] == "SAME_PLATFORM"
