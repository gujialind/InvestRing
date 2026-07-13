"""
run_nav_sync 重写测试（P5.4）

验证：
- target_date = yesterday(T)（D3）
- 增量起点 = MAX(date)+1
- 快照不被 failed_products 门控
- 无 ShareChangeEvent 写入（D1 跳过分红检测）
- auto_confirm_after_snapshot 被调用
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from app.models.sync_job import SyncJob
from app.models.nav_sync_detail import NavSyncDetail
from app.models.price_record import PriceRecord
from app.models.product import Product
from app.models.share_change_event import ShareChangeEvent
from app.services.task_runner import run_nav_sync, _generate_snapshots_for_date


class TestTargetDateYesterday:
    """target_date = yesterday(T)（D3）"""

    @patch("app.services.market_data_service.sync_product_prices")
    def test_end_date_is_yesterday(self, mock_sync, test_db):
        """sync_product_prices 传入的 end_date 应为昨天"""
        mock_sync.return_value = {"success": True, "synced_count": 0, "source": "tushare"}

        result = run_nav_sync(test_db, log_id=None)

        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
        assert result["target_date"] == yesterday

        call_args = mock_sync.call_args_list[0]
        passed_end_date = call_args.kwargs.get("end_date")
        assert passed_end_date == datetime.now().date() - timedelta(days=1)


class TestIncrementalStart:
    """增量起点 = MAX(date)+1"""

    @patch("app.services.market_data_service.sync_product_prices")
    @patch("app.services.task_runner._generate_snapshots_for_date")
    def test_start_date_from_max_date_plus_one(self, mock_snap, mock_sync, test_db):
        """有历史数据时，start_date = MAX(date)+1"""
        yesterday = datetime.now().date() - timedelta(days=1)
        day_before = yesterday - timedelta(days=1)

        record = PriceRecord(
            product_code="510300.SH", market="CN_EXCHANGE",
            date=day_before, unit_price=3.5, source="tushare",
        )
        test_db.add(record)
        test_db.commit()

        mock_sync.return_value = {"success": True, "synced_count": 1, "source": "tushare"}

        run_nav_sync(test_db, log_id=None)

        call_args = mock_sync.call_args_list[0]
        passed_start_date = call_args.kwargs.get("start_date")
        assert passed_start_date == day_before + timedelta(days=1)


class TestNoShareChangeEvent:
    """无 ShareChangeEvent 写入（D1 跳过分红检测）"""

    @patch("app.services.market_data_service.sync_product_prices")
    @patch("app.services.task_runner._generate_snapshots_for_date")
    def test_no_share_change_event_written(self, mock_snap, mock_sync, test_db):
        """run_nav_sync 不写 ShareChangeEvent"""
        count_before = test_db.query(ShareChangeEvent).count()

        mock_sync.return_value = {"success": True, "synced_count": 0, "source": "tushare"}
        run_nav_sync(test_db, log_id=None)

        count_after = test_db.query(ShareChangeEvent).count()
        assert count_after == count_before


class TestSnapshotNotGatedByFailures:
    """快照不被 failed_products 门控"""

    @patch("app.services.market_data_service.sync_product_prices")
    @patch("app.services.task_runner._generate_snapshots_for_date")
    def test_snapshot_attempted_even_with_failures(self, mock_snap, mock_sync, test_db):
        """有产品失败也调用 _generate_snapshots_for_date"""
        mock_sync.return_value = {"success": False, "synced_count": 0, "message": "API 错误", "source": "tushare"}

        run_nav_sync(test_db, log_id=None)

        mock_snap.assert_called_once()


class TestAutoConfirmCalled:
    """auto_confirm_after_snapshot 被调用"""

    @patch("app.services.snapshot_service.auto_confirm_after_snapshot")
    @patch("app.services.snapshot_service.generate_daily_snapshots")
    def test_auto_confirm_called_on_trading_day(self, mock_gen, mock_auto, test_db):
        """快照生成后调 auto_confirm_after_snapshot"""
        from app.models.trading_calendar import TradingCalendar
        from app.models.portfolio import Portfolio

        yesterday = datetime.now().date() - timedelta(days=1)
        cal = test_db.query(TradingCalendar).filter(TradingCalendar.date == yesterday).first()
        if not cal:
            cal = TradingCalendar(date=yesterday, is_open=True, exchange="SSE")
            test_db.add(cal)
        else:
            cal.is_open = True
        test_db.commit()

        port = Portfolio(code="AUTO_CONFIRM_PORT", name="测试", status="active")
        test_db.add(port)
        test_db.commit()

        _generate_snapshots_for_date(test_db, yesterday)

        mock_gen.assert_called()
        mock_auto.assert_called()
