# ============================================================================
# 集成测试：快照生成净值严格匹配 (test_snapshot_nav_strict.py)
# ============================================================================
# issue #96：快照生成净值必须严格与快照日一致——普通基金严格取 target_date
# 当日净值、QDII 严格取 T-1（前一交易日）净值；取不到即拒绝生成（MISSING_NAV），
# 禁止静默回退到更早净值。
#
# 覆盖验收断言：
# 1. 缺 target_date 当日净值 → generate 422 MISSING_NAV，指出缺失产品与日期
# 2. 补齐净值后生成成功，持仓 unit_price == 当日净值
# 3. QDII：T-1 缺失拒绝（不回退 T-2）；T-1 存在严格用 T-1（不用当日净值）
# 4. 净值齐全的正常交易日生成不回归
# 5. 被拒绝后不产生快照（目标日无快照行、最新快照日不变）
# 附：recalculate 预校验同样严格（删除任何快照前拦截）；生成点硬性兜底
#    （新确认持仓不在前日快照中、闸门覆盖不到时，_generate_portfolio_position
#    直接抛 MISSING_NAV）。
# ============================================================================

from datetime import date
from decimal import Decimal

import pytest

from app.models import PortfolioPosition, PortfolioValueSnapshot
from app.services.exceptions import BusinessError
from app.services.snapshot_service import generate_daily_snapshots
from tests.factories import (
    create_portfolio,
    create_position_snapshot,
    create_value_snapshot,
    create_investor_holding,
    create_product,
    create_price_record,
    create_trade,
)

# conftest 交易日历：工作日均为交易日
D0 = date(2025, 6, 6)         # 周五（最新快照日）
NEXT_DAY = date(2025, 6, 9)   # 周一（下一交易日 = 生成目标日）
T_MINUS_2 = date(2025, 6, 5)  # 周四（相对 NEXT_DAY 的 T-2）


def _setup_fund_snapshot(db, portfolio_code: str, product_code: str, market: str,
                         snapshot_date: date, shares: float = 100.0):
    """制造指定日的完整三表快照：基金持仓 shares 份（unit_price=1.0）"""
    create_position_snapshot(
        db, portfolio_code, product_code, market,
        snapshot_date=snapshot_date, shares=shares, unit_price=1.0,
        cost_price=1.0, market_value=shares, platform_code="MYCF",
    )
    create_value_snapshot(
        db, portfolio_code, snapshot_date,
        total_value=shares, total_shares=shares, unit_price=1.0,
    )
    create_investor_holding(db, portfolio_code, "VIEWER", snapshot_date, shares=shares)


def _setup_cash_snapshot(db, portfolio_code: str, snapshot_date: date, amount: float = 10000.0):
    """制造指定日的完整三表快照（仅 CASH 持仓，无需行情数据）"""
    create_position_snapshot(
        db, portfolio_code, "CASH", "",
        snapshot_date=snapshot_date, cash_amount=amount, unit_price=None,
        cost_price=None, market_value=amount, platform_code="MYCF",
    )
    create_value_snapshot(
        db, portfolio_code, snapshot_date,
        total_value=amount, total_shares=amount, unit_price=1.0,
    )
    create_investor_holding(db, portfolio_code, "VIEWER", snapshot_date, shares=amount)


def _snapshot_ids(db, portfolio_code: str):
    return sorted(
        row[0] for row in db.query(PortfolioValueSnapshot.id).filter(
            PortfolioValueSnapshot.portfolio_code == portfolio_code
        ).all()
    )


class TestSnapshotNavStrict:
    """#96 普通基金/QDII 净值严格匹配"""

    def test_missing_target_date_nav_rejected(self, client, admin_headers, test_db):
        """缺 target_date 当日净值 → 422 MISSING_NAV，指出产品与日期，不产生快照（验收 1、5）"""
        port = create_portfolio(test_db, code="NAV_S1", status="active")
        create_product(test_db, code="STRICTA.OF", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        _setup_fund_snapshot(test_db, port.code, "STRICTA.OF", "CN_OTC", D0)
        # 仅 D0 有净值，NEXT_DAY 无净值（旧逻辑会静默回退用 D0 净值）
        create_price_record(test_db, "STRICTA.OF", "CN_OTC", D0, 1.0)

        resp = client.post(
            "/api/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": NEXT_DAY.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "MISSING_NAV"
        assert "STRICTA.OF" in detail["message"]
        assert "2025-06-09" in detail["message"]

        # 目标日无快照行，最新快照日仍为 D0（不产生缺口/半截快照）
        assert test_db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == port.code,
            PortfolioValueSnapshot.snapshot_date == NEXT_DAY,
        ).first() is None
        latest = test_db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == port.code,
        ).order_by(PortfolioValueSnapshot.snapshot_date.desc()).first()
        assert latest.snapshot_date == D0

    def test_generate_uses_target_date_nav_after_sync(self, client, admin_headers, test_db):
        """补齐当日净值后生成成功，unit_price == target_date 当日净值（验收 2、4）"""
        port = create_portfolio(test_db, code="NAV_S2", status="active")
        create_product(test_db, code="STRICTB.OF", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        _setup_fund_snapshot(test_db, port.code, "STRICTB.OF", "CN_OTC", D0)
        create_price_record(test_db, "STRICTB.OF", "CN_OTC", NEXT_DAY, 1.5)

        resp = client.post(
            "/api/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": NEXT_DAY.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Response: {resp.status_code} {resp.json()}"
        assert resp.json()["success"] is True

        pos = test_db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == port.code,
            PortfolioPosition.product_code == "STRICTB.OF",
            PortfolioPosition.snapshot_date == NEXT_DAY,
        ).first()
        assert pos is not None
        assert Decimal(str(pos.unit_price)) == Decimal("1.5")
        assert Decimal(str(pos.market_value)) == Decimal("150.0")

    def test_qdii_missing_t1_nav_rejected_no_fallback(self, client, admin_headers, test_db):
        """QDII：T-1 缺失即拒绝，不回退 T-2 净值（验收 3 前半）"""
        port = create_portfolio(test_db, code="NAV_S3", status="active")
        create_product(test_db, code="QDIIA.OF", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK",
                       confirm_days=2, is_qdii=True)
        _setup_fund_snapshot(test_db, port.code, "QDIIA.OF", "CN_OTC", D0)
        # 仅 T-2（06-05）有净值，T-1（06-06）缺失
        create_price_record(test_db, "QDIIA.OF", "CN_OTC", T_MINUS_2, 1.8)

        resp = client.post(
            "/api/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": NEXT_DAY.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "MISSING_NAV"
        assert "QDIIA.OF" in detail["message"]
        assert "2025-06-06" in detail["message"]  # 指出所需 T-1 日期

        assert test_db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == port.code,
            PortfolioValueSnapshot.snapshot_date == NEXT_DAY,
        ).first() is None

    def test_qdii_strict_t1_nav_used(self, client, admin_headers, test_db):
        """QDII：T-1 存在时严格用 T-1，不用 target_date 当日净值（验收 3 后半）"""
        port = create_portfolio(test_db, code="NAV_S4", status="active")
        create_product(test_db, code="QDIIB.OF", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK",
                       confirm_days=2, is_qdii=True)
        _setup_fund_snapshot(test_db, port.code, "QDIIB.OF", "CN_OTC", D0)
        # NEXT_DAY 的 T-1 = D0（06-06）；两日净值不同值以区分取价日
        create_price_record(test_db, "QDIIB.OF", "CN_OTC", D0, 2.0)
        create_price_record(test_db, "QDIIB.OF", "CN_OTC", NEXT_DAY, 3.0)

        resp = client.post(
            "/api/snapshots/generate",
            json={"portfolio_code": port.code, "target_date": NEXT_DAY.isoformat()},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Response: {resp.status_code} {resp.json()}"

        pos = test_db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == port.code,
            PortfolioPosition.product_code == "QDIIB.OF",
            PortfolioPosition.snapshot_date == NEXT_DAY,
        ).first()
        assert pos is not None
        assert Decimal(str(pos.unit_price)) == Decimal("2.0")
        assert Decimal(str(pos.market_value)) == Decimal("200.0")

    def test_recalculate_precheck_rejects_missing_nav(self, client, admin_headers, test_db):
        """重算预校验同样严格：区间内含缺净值交易日 → 422 VALIDATION_FAILED，不删任何快照"""
        port = create_portfolio(test_db, code="NAV_S5", status="active")
        create_product(test_db, code="STRICTC.OF", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        _setup_fund_snapshot(test_db, port.code, "STRICTC.OF", "CN_OTC", D0)
        # D0 净值齐全（D0 预校验通过），NEXT_DAY 缺失（旧逻辑 <= 会放行）
        create_price_record(test_db, "STRICTC.OF", "CN_OTC", D0, 1.0)
        ids_before = _snapshot_ids(test_db, port.code)

        resp = client.post(
            "/api/snapshots/recalculate",
            json={
                "portfolio_code": port.code,
                "start_date": D0.isoformat(),
                "end_date": NEXT_DAY.isoformat(),
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "VALIDATION_FAILED"
        assert "预校验失败" in detail["message"]
        assert "STRICTC.OF" in detail["message"]
        assert "2025-06-09" in detail["message"]

        # 未删除任何快照（原行 id 不变）
        assert _snapshot_ids(test_db, port.code) == ids_before

    def test_new_position_missing_nav_rejected_at_generation(self, test_db):
        """生成点硬性兜底：窗口内新确认买入的基金（不在前日快照、闸门覆盖不到）
        缺 target_date 净值时，_generate_portfolio_position 直接抛 MISSING_NAV"""
        port = create_portfolio(test_db, code="NAV_S6", status="active")
        create_product(test_db, code="STRICTD.OF", market="CN_OTC",
                       product_type="OEF", asset_class_code="ASSET_STOCK")
        _setup_cash_snapshot(test_db, port.code, D0)
        # 窗口内确认的基金买入：confirm_date=NEXT_DAY，持仓首次出现于目标日
        create_trade(
            test_db, port.code, "STRICTD.OF", "CN_OTC",
            trade_type="buy", shares=100.0, amount=150.0, price=1.5,
            trade_date=D0, confirm_date=NEXT_DAY, status="confirmed",
        )

        with pytest.raises(BusinessError) as exc:
            generate_daily_snapshots(test_db, port.code, NEXT_DAY)
        assert exc.value.code == "MISSING_NAV"
        assert "STRICTD.OF" in exc.value.message
        assert "2025-06-09" in exc.value.message
