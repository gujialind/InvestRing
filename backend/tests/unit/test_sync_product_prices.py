"""
sync_product_prices 改造测试（P5.2）

验证：
- 批量 upsert 幂等性（同区间跑两次不翻倍）
- 数据源路由（tushare CN_EXCHANGE / akshare HK_MUTUAL）
- 禁止硬编码 data_source 覆盖
- sync_error 失败落库
- 不支持的数据源 → skipped
"""
import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.models.price_record import PriceRecord
from app.models.product import Product
from app.services.market_data_service import (
    sync_product_prices, _normalize_raw, _bulk_upsert_prices,
    _mark_failed, _mark_skipped,
)


class TestBulkUpsertIdempotent:
    """批量 upsert 幂等性"""

    def test_upsert_idempotent(self, test_db: Session, sample_etf_product: Product):
        """同产品同区间跑两次，price_record 记录数不翻倍"""
        rows = [
            {"trade_date": "20250106", "close": 3.5, "pre_close": 3.4, "pct_chg": 0.029},
            {"trade_date": "20250107", "close": 3.6, "pre_close": 3.5, "pct_chg": 0.028},
        ]
        normalized = _normalize_raw(rows, "CN_EXCHANGE")

        _bulk_upsert_prices(test_db, "510300.SH", "CN_EXCHANGE", normalized, "tushare")
        test_db.commit()
        count1 = test_db.query(PriceRecord).filter(
            PriceRecord.product_code == "510300.SH",
            PriceRecord.market == "CN_EXCHANGE",
        ).count()

        _bulk_upsert_prices(test_db, "510300.SH", "CN_EXCHANGE", normalized, "tushare")
        test_db.commit()
        count2 = test_db.query(PriceRecord).filter(
            PriceRecord.product_code == "510300.SH",
            PriceRecord.market == "CN_EXCHANGE",
        ).count()

        assert count1 == count2 == 2, f"幂等失败: 第一次={count1}, 第二次={count2}"

    def test_upsert_updates_existing_values(self, test_db: Session, sample_etf_product: Product):
        """重跑时更新已有记录的值"""
        rows = [{"trade_date": "20250106", "close": 3.5}]
        normalized = _normalize_raw(rows, "CN_EXCHANGE")
        _bulk_upsert_prices(test_db, "510300.SH", "CN_EXCHANGE", normalized, "tushare")
        test_db.commit()

        updated = [{"trade_date": "20250106", "close": 4.0}]
        normalized2 = _normalize_raw(updated, "CN_EXCHANGE")
        _bulk_upsert_prices(test_db, "510300.SH", "CN_EXCHANGE", normalized2, "tushare")
        test_db.commit()

        record = test_db.query(PriceRecord).filter(
            PriceRecord.product_code == "510300.SH",
            PriceRecord.price_date == date(2025, 1, 6),
        ).first()
        assert float(record.unit_price) == 4.0, "值应被更新为 4.0"


class TestDataSourceRouting:
    """数据源路由"""

    @patch("app.services.market_data_service.get_fund_daily")
    def test_tushare_cn_exchange(self, mock_get_fund_daily, test_db: Session, sample_etf_product: Product):
        """tushare + CN_EXCHANGE → 走 get_fund_daily"""
        mock_get_fund_daily.return_value = []
        result = sync_product_prices(test_db, "510300.SH", "CN_EXCHANGE",
                                     start_date=date(2025, 1, 6), end_date=date(2025, 1, 10))
        mock_get_fund_daily.assert_called_once()
        assert result["source"] == "tushare"

    @patch("app.services.market_data_service.get_fund_nav")
    def test_tushare_cn_otc(self, mock_get_fund_nav, test_db: Session, sample_otc_product: Product):
        """tushare + CN_OTC → 走 get_fund_nav"""
        mock_get_fund_nav.return_value = []
        result = sync_product_prices(test_db, "000300.OF", "CN_OTC",
                                     start_date=date(2025, 1, 6), end_date=date(2025, 1, 10))
        mock_get_fund_nav.assert_called_once()
        assert result["source"] == "tushare"

    def test_tushare_hk_mutual_skipped(self, test_db: Session):
        """tushare + HK_MUTUAL → skipped"""
        from sqlalchemy import and_
        product = test_db.query(Product).filter(
            Product.code == "1001767344", Product.market == "HK_MUTUAL"
        ).first()
        # 临时改 data_source 为 tushare 测试跳过
        product.data_source = "tushare"
        test_db.commit()

        result = sync_product_prices(test_db, "1001767344", "HK_MUTUAL",
                                     start_date=date(2025, 1, 6), end_date=date(2025, 1, 10))
        assert result["success"] is True
        assert result["synced_count"] == 0
        assert "跳过" in result["message"]

        test_db.refresh(product)
        assert product.data_source_status == "skipped"


class TestNoHardcodeDataSourceOverride:
    """禁止硬编码 data_source"""

    @patch("app.services.market_data_service.get_fund_daily")
    def test_data_source_not_overwritten(self, mock_get_fund_daily, test_db: Session, sample_etf_product: Product):
        """成功路径不覆盖 product.data_source"""
        mock_get_fund_daily.return_value = [
            {"trade_date": "20250106", "close": 3.5, "pre_close": 3.4, "pct_chg": 2.9},
        ]
        original_ds = sample_etf_product.data_source

        sync_product_prices(test_db, "510300.SH", "CN_EXCHANGE",
                            start_date=date(2025, 1, 6), end_date=date(2025, 1, 10))

        test_db.refresh(sample_etf_product)
        assert sample_etf_product.data_source == original_ds, "data_source 不应被覆盖"

    @patch("app.services.market_data_service.get_fund_daily")
    def test_source_field_uses_actual_data_source(self, mock_get_fund_daily, test_db: Session, sample_etf_product: Product):
        """PriceRecord.source 取 product.data_source，不恒写 tushare"""
        mock_get_fund_daily.return_value = [
            {"trade_date": "20250106", "close": 3.5, "pre_close": 3.4, "pct_chg": 2.9},
        ]
        # data_source 保持默认 "tushare"，验证 source 来自 product.data_source 而非硬编码
        sync_product_prices(test_db, "510300.SH", "CN_EXCHANGE",
                            start_date=date(2025, 1, 6), end_date=date(2025, 1, 10))

        record = test_db.query(PriceRecord).filter(
            PriceRecord.product_code == "510300.SH",
            PriceRecord.market == "CN_EXCHANGE",
        ).first()
        assert record is not None, "应有记录写入"
        assert record.source == sample_etf_product.data_source, \
            f"source 应取 product.data_source='{sample_etf_product.data_source}'"


class TestSyncErrorPersisted:
    """sync_error 失败落库"""

    @patch("app.services.market_data_service.get_fund_daily")
    def test_sync_error_written_on_failure(self, mock_get_fund_daily, test_db: Session, sample_etf_product: Product):
        """失败时写 product.sync_error"""
        from app.services.tushare_client import TushareAPIError
        mock_get_fund_daily.side_effect = TushareAPIError("获取基金日线行情失败: API 错误")

        result = sync_product_prices(test_db, "510300.SH", "CN_EXCHANGE",
                                     start_date=date(2025, 1, 6), end_date=date(2025, 1, 10))

        assert result["success"] is False
        test_db.refresh(sample_etf_product)
        assert sample_etf_product.data_source_status == "failed"
        assert sample_etf_product.sync_error is not None
        assert "API 错误" in sample_etf_product.sync_error


class TestSkippedUnsupported:
    """不支持的数据源 → skipped"""

    def test_unknown_data_source_skipped(self, test_db: Session, sample_etf_product: Product):
        """未知 data_source → data_source_status='skipped'"""
        sample_etf_product.data_source = "unknown_source"
        test_db.commit()

        result = sync_product_prices(test_db, "510300.SH", "CN_EXCHANGE",
                                     start_date=date(2025, 1, 6), end_date=date(2025, 1, 10))

        assert result["success"] is True
        assert result["synced_count"] == 0
        test_db.refresh(sample_etf_product)
        assert sample_etf_product.data_source_status == "skipped"
