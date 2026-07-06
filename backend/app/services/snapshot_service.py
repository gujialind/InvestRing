"""
快照生成服务

提供组合快照的生成、重算和校验功能。
三张快照表按固定顺序生成：portfolio_position → portfolio_value_snapshot → investor_holding
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models import (
    Portfolio, PortfolioPosition, PortfolioValueSnapshot, InvestorHolding,
    Trade, Subscription, ShareChangeEvent, PriceRecord, Product,
    TradingCalendar, Investor, AssetClassification
)

logger = logging.getLogger(__name__)


def generate_daily_snapshots(
    db: Session,
    portfolio_code: str,
    target_date: date
) -> Dict[str, Any]:
    """
    生成指定组合在指定日期的三张快照表
    
    Args:
        db: 数据库会话
        portfolio_code: 组合代码
        target_date: 目标日期
        
    Returns:
        生成结果
        
    Raises:
        ValueError: 当依赖数据不完整或校验失败时
    """
    # 1. 前置校验
    _validate_portfolio(db, portfolio_code)
    _validate_trading_day(db, target_date)
    
    validations = validate_snapshot_dependencies(db, portfolio_code, target_date)
    failed_checks = [v for v in validations if v["status"] == "failed"]
    if failed_checks:
        error_messages = "; ".join([v["message"] for v in failed_checks])
        raise ValueError(f"依赖数据校验失败: {error_messages}")
    
    try:
        # 2. 删除已有快照（如果存在）
        _delete_existing_snapshots(db, portfolio_code, target_date)
        
        # 3. 生成持仓快照
        positions = _generate_portfolio_position(db, portfolio_code, target_date)
        db.add_all(positions)
        
        # 4. 生成市值快照
        value_snapshot = _generate_portfolio_value_snapshot(
            db, portfolio_code, target_date, positions
        )
        db.add(value_snapshot)
        
        # 5. 生成投资人快照
        holdings = _generate_investor_holding(
            db, portfolio_code, target_date, value_snapshot
        )
        db.add_all(holdings)
        
        db.commit()
        
        logger.info(
            f"快照生成成功: portfolio={portfolio_code}, date={target_date}, "
            f"positions={len(positions)}, investors={len(holdings)}"
        )
        
        return {
            "success": True,
            "message": "快照生成成功",
            "portfolio_code": portfolio_code,
            "snapshot_date": target_date,
            "total_value": float(value_snapshot.total_value),
            "total_shares": float(value_snapshot.total_shares),
            "unit_price": float(value_snapshot.unit_price),
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"快照生成失败: portfolio={portfolio_code}, date={target_date}, error={str(e)}")
        raise


def recalculate_snapshots(
    db: Session,
    portfolio_code: Optional[str],
    start_date: date,
    end_date: date,
    force: bool = False
) -> Dict[str, Any]:
    """
    重算指定时间区间的快照
    
    Args:
        db: 数据库会话
        portfolio_code: 组合代码（None表示所有活跃组合）
        start_date: 起始日期
        end_date: 结束日期
        force: 是否强制重算（跳过校验）
        
    Returns:
        重算结果
    """
    # 获取需要处理的组合列表
    if portfolio_code:
        portfolios = [db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()]
        if not portfolios[0]:
            raise ValueError(f"组合 {portfolio_code} 不存在")
    else:
        portfolios = db.query(Portfolio).filter(Portfolio.status == "active").all()
    
    results = []
    
    for portfolio in portfolios:
        result = {
            "portfolio_code": portfolio.code,
            "processed_dates": [],
            "total_processed": 0,
            "errors": []
        }
        
        current_date = start_date
        while current_date <= end_date:
            try:
                # 检查是否为交易日
                if not _is_trading_day(db, current_date):
                    current_date += timedelta(days=1)
                    continue
                
                # 校验依赖数据（除非force模式）
                if not force:
                    validations = validate_snapshot_dependencies(
                        db, portfolio.code, current_date
                    )
                    failed = [v for v in validations if v["status"] == "failed"]
                    if failed:
                        error_msg = "; ".join([v["message"] for v in failed])
                        result["errors"].append({
                            "date": current_date.isoformat(),
                            "error": f"校验失败: {error_msg}"
                        })
                        current_date += timedelta(days=1)
                        continue
                
                # 删除旧快照并生成新快照
                _delete_existing_snapshots(db, portfolio.code, current_date)
                snapshot_result = generate_daily_snapshots(
                    db, portfolio.code, current_date
                )
                
                result["processed_dates"].append(current_date.isoformat())
                result["total_processed"] += 1
                
            except Exception as e:
                db.rollback()
                result["errors"].append({
                    "date": current_date.isoformat(),
                    "error": str(e)
                })
                logger.error(
                    f"重算失败: portfolio={portfolio.code}, date={current_date}, error={str(e)}"
                )
            
            current_date += timedelta(days=1)
        
        results.append(result)
    
    return {
        "success": True,
        "message": f"重算完成，共处理{len(portfolios)}个组合",
        "results": results
    }


def validate_snapshot_dependencies(
    db: Session,
    portfolio_code: str,
    target_date: date
) -> List[Dict[str, Any]]:
    """
    校验生成快照所需的依赖数据
    
    Args:
        db: 数据库会话
        portfolio_code: 组合代码
        target_date: 目标日期
        
    Returns:
        校验结果列表
    """
    checks = []
    
    # 1. 检查交易日
    checks.append(_check_trading_day(db, target_date))
    
    # 2. 检查pending交易
    checks.append(_check_pending_transactions(db, portfolio_code, target_date))
    
    # 3. 检查净值数据完整性
    checks.append(_check_price_data_completeness(db, portfolio_code, target_date))
    
    # 4. 检查分红事件状态
    checks.append(_check_share_change_events(db, portfolio_code, target_date))
    
    return checks


# ==================== 内部辅助函数 ====================

def _validate_portfolio(db: Session, portfolio_code: str):
    """校验组合是否存在且为active状态"""
    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise ValueError(f"组合 {portfolio_code} 不存在")
    if portfolio.status != "active":
        raise ValueError(f"组合 {portfolio_code} 未激活，当前状态: {portfolio.status}")


def _validate_trading_day(db: Session, target_date: date):
    """校验目标日期是否为交易日"""
    if not _is_trading_day(db, target_date):
        raise ValueError(f"{target_date} 不是交易日，无法生成快照")


def _is_trading_day(db: Session, target_date: date) -> bool:
    """检查指定日期是否为交易日"""
    cal = db.query(TradingCalendar).filter(
        TradingCalendar.date == target_date
    ).first()
    if not cal:
        return False
    return cal.is_open


def _delete_existing_snapshots(db: Session, portfolio_code: str, target_date: date):
    """删除指定日期的三张快照表记录"""
    db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_code == portfolio_code,
        PortfolioPosition.snapshot_date == target_date
    ).delete()
    
    db.query(PortfolioValueSnapshot).filter(
        PortfolioValueSnapshot.portfolio_code == portfolio_code,
        PortfolioValueSnapshot.snapshot_date == target_date
    ).delete()
    
    db.query(InvestorHolding).filter(
        InvestorHolding.portfolio_code == portfolio_code,
        InvestorHolding.snapshot_date == target_date
    ).delete()


def _generate_portfolio_position(
    db: Session,
    portfolio_code: str,
    target_date: date
) -> List[PortfolioPosition]:
    """
    生成持仓快照
    
    逻辑：
    1. 获取前一日快照作为基准
    2. 应用期间内所有已确认交易
    3. 获取目标日价格计算市值
    4. 计算冻结字段
    """
    # 获取前一日最新快照日期
    prev_snapshot = db.query(func.max(PortfolioPosition.snapshot_date)).filter(
        PortfolioPosition.portfolio_code == portfolio_code,
        PortfolioPosition.snapshot_date < target_date
    ).scalar()
    
    # 初始化持仓字典（从前一日快照）
    positions = {}
    if prev_snapshot:
        prev_positions = db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == portfolio_code,
            PortfolioPosition.snapshot_date == prev_snapshot
        ).all()
        
        for pos in prev_positions:
            key = (pos.product_code, pos.market)
            # 如果 asset_type 为空，从产品表推导
            pos_asset_type = pos.asset_type
            if not pos_asset_type:
                if pos.product_code == "CASH":
                    pos_asset_type = "cash"
                else:
                    product = db.query(Product).filter(
                        Product.code == pos.product_code,
                        Product.market == pos.market
                    ).first()
                    if product and product.asset_class_code:
                        ac = db.query(AssetClassification).filter(
                            AssetClassification.code == product.asset_class_code
                        ).first()
                        if ac:
                            pos_asset_type = ac.asset_type
            positions[key] = {
                "shares": Decimal(str(pos.shares or 0)),
                "amount": Decimal(str(pos.amount or 0)) if pos.amount is not None else None,
                "cost_price": Decimal(str(pos.cost_price or 0)) if pos.cost_price else None,
                "asset_type": pos_asset_type,
            }
    
    # 应用期间内的已确认交易（从prev_snapshot次日到target_date）
    start_apply_date = prev_snapshot + timedelta(days=1) if prev_snapshot else target_date
    
    # 处理买入交易
    buy_trades = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.trade_type == "buy",
        Trade.status == "confirmed",
        Trade.confirm_date >= start_apply_date,
        Trade.confirm_date <= target_date
    ).all()
    
    for trade in buy_trades:
        key = (trade.product_code, trade.market)
        if key not in positions:
            product = db.query(Product).filter(
                Product.code == trade.product_code,
                Product.market == trade.market
            ).first()
            positions[key] = {
                "shares": Decimal("0"),
                "amount": None,
                "cost_price": None,
                "asset_type": _get_product_asset_type(db, product) if product else "stock",
            }
        
        new_shares = Decimal(str(trade.shares or 0))
        new_price = Decimal(str(trade.price or 0))
        old_shares = positions[key]["shares"]
        old_cost = positions[key]["cost_price"] or Decimal("0")
        
        # 加权平均成本价
        if old_shares > 0:
            positions[key]["cost_price"] = (old_shares * old_cost + new_shares * new_price) / (old_shares + new_shares)
        else:
            positions[key]["cost_price"] = new_price
        
        positions[key]["shares"] += new_shares
    
    # 处理卖出交易
    sell_trades = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.trade_type == "sell",
        Trade.status == "confirmed",
        Trade.confirm_date >= start_apply_date,
        Trade.confirm_date <= target_date
    ).all()
    
    for trade in sell_trades:
        key = (trade.product_code, trade.market)
        if key in positions:
            positions[key]["shares"] -= Decimal(str(trade.shares or 0))
    
    # 处理申购/赎回对组合现金的影响
    # 申购确认增加现金，赎回确认减少现金
    cash_key = ("CASH", "")
    
    # 获取前一日现金余额
    prev_cash_amount = Decimal("0")
    if prev_snapshot:
        prev_cash_pos = db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_code == portfolio_code,
            PortfolioPosition.snapshot_date == prev_snapshot,
            PortfolioPosition.product_code == "CASH"
        ).first()
        if prev_cash_pos and prev_cash_pos.amount is not None:
            prev_cash_amount = Decimal(str(prev_cash_pos.amount))
    
    # 如果没有前一日快照，检查是否有初始现金持仓
    if not prev_snapshot and cash_key not in positions:
        positions[cash_key] = {
            "shares": None,
            "amount": Decimal("0"),
            "cost_price": None,
            "asset_type": "cash",
        }
    elif cash_key not in positions:
        positions[cash_key] = {
            "shares": None,
            "amount": prev_cash_amount,
            "cost_price": None,
            "asset_type": "cash",
        }
    
    # 处理申购确认（增加现金）
    confirmed_subs = db.query(Subscription).filter(
        Subscription.portfolio_code == portfolio_code,
        Subscription.sub_type == "subscribe",
        Subscription.status == "confirmed",
        Subscription.confirm_date >= start_apply_date,
        Subscription.confirm_date <= target_date
    ).all()
    
    for sub in confirmed_subs:
        positions[cash_key]["amount"] = (positions[cash_key]["amount"] or Decimal("0")) + Decimal(str(sub.amount or 0))
    
    # 处理赎回确认（减少现金）
    confirmed_redeems = db.query(Subscription).filter(
        Subscription.portfolio_code == portfolio_code,
        Subscription.sub_type == "redeem",
        Subscription.status == "confirmed",
        Subscription.confirm_date >= start_apply_date,
        Subscription.confirm_date <= target_date
    ).all()
    
    for sub in confirmed_redeems:
        positions[cash_key]["amount"] = (positions[cash_key]["amount"] or Decimal("0")) - Decimal(str(sub.amount or 0))
    
    # 处理买入交易（减少现金）
    for trade in buy_trades:
        trade_amount = Decimal(str(trade.amount or 0))
        if trade_amount > 0:
            positions[cash_key]["amount"] = (positions[cash_key]["amount"] or Decimal("0")) - trade_amount
    
    # 处理卖出交易（增加现金）
    for trade in sell_trades:
        trade_amount = Decimal(str(trade.amount or 0))
        if trade_amount > 0:
            positions[cash_key]["amount"] = (positions[cash_key]["amount"] or Decimal("0")) + trade_amount
    
    # 构建最终的持仓快照对象
    result_positions = []
    for (product_code, market), pos_data in positions.items():
        # 跳过零持仓（现金允许为0但不跳过，保留现金持仓记录）
        is_cash = pos_data.get("asset_type") == "cash"
        if not is_cash:
            if pos_data["shares"] is not None and pos_data["shares"] <= 0 and pos_data.get("amount", Decimal("0")) <= 0:
                continue  # 跳过零持仓
        
        # 获取产品价格
        product = db.query(Product).filter(
            Product.code == product_code,
            Product.market == market
        ).first()
        
        unit_price = None
        market_value = None
        
        if pos_data["asset_type"] == "cash":
            # 现金资产
            market_value = pos_data["amount"]
        elif product:
            # 根据产品类型获取净值
            if product.is_qdii:
                # QDII：取前一交易日净值
                prev_date = _prev_trading_day(db, target_date, 1)
                price_record = db.query(PriceRecord).filter(
                    PriceRecord.product_code == product_code,
                    PriceRecord.market == market,
                    PriceRecord.date <= prev_date
                ).order_by(PriceRecord.date.desc()).first()
            else:
                # 普通基金：取当日净值
                price_record = db.query(PriceRecord).filter(
                    PriceRecord.product_code == product_code,
                    PriceRecord.market == market,
                    PriceRecord.date <= target_date
                ).order_by(PriceRecord.date.desc()).first()
            
            if price_record:
                unit_price = Decimal(str(price_record.unit_price))
                market_value = pos_data["shares"] * unit_price
        
        # 计算冻结份额（pending卖出）
        frozen_shares = _calculate_frozen_shares(db, portfolio_code, product_code, market, target_date)
        
        position = PortfolioPosition(
            portfolio_code=portfolio_code,
            product_code=product_code,
            market=market,
            shares=float(pos_data["shares"]) if pos_data["shares"] and not is_cash else None,
            amount=float(pos_data["amount"]) if is_cash and pos_data["amount"] is not None else None,
            frozen_shares=float(frozen_shares) if frozen_shares > 0 else 0,
            frozen_amount=0,  # 简化：暂不计算冻结金额
            cost_price=float(pos_data["cost_price"]) if pos_data["cost_price"] else None,
            unit_price=float(unit_price) if unit_price else None,
            market_value=float(market_value) if market_value else None,
            asset_type=pos_data["asset_type"],
            snapshot_date=target_date
        )
        result_positions.append(position)
    
    return result_positions


def _generate_portfolio_value_snapshot(
    db: Session,
    portfolio_code: str,
    target_date: date,
    positions: List[PortfolioPosition]
) -> PortfolioValueSnapshot:
    """
    生成组合市值快照
    
    逻辑：
    1. 计算总市值 = Σ(持仓市值) + 现金余额
    2. 获取总份额
    3. 计算净值 = total_value / total_shares
    """
    # 计算总市值
    total_value = Decimal("0")
    for pos in positions:
        if pos.market_value is not None:
            total_value += Decimal(str(pos.market_value))
        elif pos.amount is not None:
            total_value += Decimal(str(pos.amount))
    
    # 获取总份额（从投资人快照汇总，或使用前一日的值）
    prev_holding = db.query(func.sum(InvestorHolding.shares)).filter(
        InvestorHolding.portfolio_code == portfolio_code,
        InvestorHolding.snapshot_date < target_date
    ).scalar()
    
    total_shares = Decimal(str(prev_holding or 0))
    
    # 如果无历史份额，使用市值作为初始份额（首次申购场景）
    if total_shares == 0:
        total_shares = total_value if total_value > 0 else Decimal("1")
    
    # 计算净值
    if total_shares > 0:
        unit_price = total_value / total_shares
    else:
        unit_price = Decimal("1.0000")
    
    # 计算冻结份额（pending赎回）
    frozen_shares = _calculate_portfolio_frozen_shares(db, portfolio_code, target_date)
    
    snapshot = PortfolioValueSnapshot(
        portfolio_code=portfolio_code,
        snapshot_date=target_date,
        total_value=float(total_value),
        total_shares=float(total_shares),
        unit_price=float(unit_price.quantize(Decimal("0.0001"))),
        frozen_shares=float(frozen_shares) if frozen_shares > 0 else 0,
    )
    
    return snapshot


def _generate_investor_holding(
    db: Session,
    portfolio_code: str,
    target_date: date,
    value_snapshot: PortfolioValueSnapshot
) -> List[InvestorHolding]:
    """
    生成投资人份额快照
    
    逻辑：
    1. 获取前一日各投资人份额
    2. 应用期间内的申购/赎回确认
    3. 计算冻结份额
    """
    # 获取前一日最新快照日期
    prev_snapshot_date = db.query(func.max(InvestorHolding.snapshot_date)).filter(
        InvestorHolding.portfolio_code == portfolio_code,
        InvestorHolding.snapshot_date < target_date
    ).scalar()
    
    # 获取所有投资人
    investors = db.query(Investor).all()
    
    result_holdings = []
    
    for investor in investors:
        # 获取前一日份额
        prev_shares = Decimal("0")
        prev_cost = Decimal("0")
        
        if prev_snapshot_date:
            prev_holding = db.query(InvestorHolding).filter(
                InvestorHolding.portfolio_code == portfolio_code,
                InvestorHolding.investor_code == investor.code,
                InvestorHolding.snapshot_date == prev_snapshot_date
            ).first()
            
            if prev_holding:
                prev_shares = Decimal(str(prev_holding.shares or 0))
                prev_cost = Decimal(str(prev_holding.cost_per_share or 0))
        
        # 应用期间内的申购/赎回
        start_apply_date = prev_snapshot_date + timedelta(days=1) if prev_snapshot_date else target_date
        
        # 申购
        subscribes = db.query(Subscription).filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.investor_code == investor.code,
            Subscription.sub_type == "subscribe",
            Subscription.status == "confirmed",
            Subscription.confirm_date >= start_apply_date,
            Subscription.confirm_date <= target_date
        ).all()
        
        for sub in subscribes:
            new_shares = Decimal(str(sub.shares or 0))
            new_price = Decimal(str(sub.unit_price or 0))
            
            # 加权平均成本
            if prev_shares > 0:
                prev_cost = (prev_shares * prev_cost + new_shares * new_price) / (prev_shares + new_shares)
            else:
                prev_cost = new_price
            
            prev_shares += new_shares
        
        # 赎回
        redeems = db.query(Subscription).filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.investor_code == investor.code,
            Subscription.sub_type == "redeem",
            Subscription.status == "confirmed",
            Subscription.confirm_date >= start_apply_date,
            Subscription.confirm_date <= target_date
        ).all()
        
        for sub in redeems:
            redeem_shares = Decimal(str(sub.shares or 0))
            prev_shares -= redeem_shares
        
        # 只保留有份额的投资人
        if prev_shares <= 0:
            continue
        
        # 计算冻结份额（pending赎回）
        frozen_shares = _calculate_investor_frozen_shares(
            db, portfolio_code, investor.code, target_date
        )
        
        holding = InvestorHolding(
            portfolio_code=portfolio_code,
            investor_code=investor.code,
            snapshot_date=target_date,
            shares=float(prev_shares),
            frozen_shares=float(frozen_shares) if frozen_shares > 0 else 0,
            cost_per_share=float(prev_cost.quantize(Decimal("0.0001"))) if prev_cost > 0 else 0,
        )
        result_holdings.append(holding)
    
    return result_holdings


# ==================== 校验函数 ====================

def _check_trading_day(db: Session, target_date: date) -> Dict[str, Any]:
    """检查目标日期是否为交易日"""
    cal = db.query(TradingCalendar).filter(
        TradingCalendar.date == target_date
    ).first()
    
    if not cal or not cal.is_open:
        return {
            "check_type": "trading_day",
            "status": "failed",
            "message": f"{target_date} 不是交易日，无法生成快照"
        }
    return {"check_type": "trading_day", "status": "passed", "message": "交易日校验通过"}


def _check_pending_transactions(
    db: Session,
    portfolio_code: str,
    target_date: date
) -> Dict[str, Any]:
    """检查是否存在pending交易"""
    pending_trades = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.trade_date <= target_date,
        Trade.status == "pending"
    ).count()
    
    pending_subs = db.query(Subscription).filter(
        Subscription.portfolio_code == portfolio_code,
        Subscription.apply_date <= target_date,
        Subscription.status == "pending"
    ).count()
    
    if pending_trades > 0 or pending_subs > 0:
        return {
            "check_type": "pending_transactions",
            "status": "failed",
            "message": f"存在{pending_trades}笔待确认交易和{pending_subs}笔待确认申赎，请先确认这些交易"
        }
    return {"check_type": "pending_transactions", "status": "passed", "message": "无待确认交易"}


def _check_price_data_completeness(
    db: Session,
    portfolio_code: str,
    target_date: date
) -> Dict[str, Any]:
    """检查净值数据完整性"""
    # 获取该组合的最新持仓产品
    latest_position_date = db.query(func.max(PortfolioPosition.snapshot_date)).filter(
        PortfolioPosition.portfolio_code == portfolio_code
    ).scalar()
    
    if not latest_position_date:
        return {"check_type": "price_data", "status": "warning", "message": "无历史持仓数据"}
    
    products_to_check = db.query(
        PortfolioPosition.product_code,
        PortfolioPosition.market
    ).filter(
        PortfolioPosition.portfolio_code == portfolio_code,
        PortfolioPosition.snapshot_date == latest_position_date
    ).distinct().all()
    
    missing_prices = []
    qdii_missing = []
    
    for product_code, market in products_to_check:
        if product_code == "CASH":
            continue
        
        product = db.query(Product).filter(
            Product.code == product_code,
            Product.market == market
        ).first()
        
        if not product:
            continue
        
        if product.is_qdii:
            # QDII基金：检查T-1日净值
            prev_date = _prev_trading_day(db, target_date, 1)
            price = db.query(PriceRecord).filter(
                PriceRecord.product_code == product_code,
                PriceRecord.market == market,
                PriceRecord.date == prev_date
            ).first()
            
            if not price:
                qdii_missing.append(f"{product_code}({market}) [T-1={prev_date}]")
        else:
            # 普通基金：检查target_date当日净值
            price = db.query(PriceRecord).filter(
                PriceRecord.product_code == product_code,
                PriceRecord.market == market,
                PriceRecord.date <= target_date
            ).order_by(PriceRecord.date.desc()).first()
            
            if not price:
                missing_prices.append(f"{product_code}({market})")
    
    all_missing = []
    if missing_prices:
        all_missing.append(f"普通基金缺少当日净值: {', '.join(missing_prices)}")
    if qdii_missing:
        all_missing.append(f"QDII基金缺少T-1日净值: {', '.join(qdii_missing)}")
    
    if all_missing:
        return {
            "check_type": "price_data",
            "status": "failed",
            "message": "; ".join(all_missing)
        }
    return {"check_type": "price_data", "status": "passed", "message": "净值数据完整"}


def _check_share_change_events(
    db: Session,
    portfolio_code: str,
    target_date: date
) -> Dict[str, Any]:
    """检查分红事件状态"""
    pending_events = db.query(ShareChangeEvent).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.entitlement_date <= target_date,
        ShareChangeEvent.status == "pending"
    ).count()
    
    if pending_events > 0:
        return {
            "check_type": "share_change_events",
            "status": "warning",
            "message": f"存在{pending_events}笔未确认的份额变动事件，可能影响快照准确性"
        }
    return {"check_type": "share_change_events", "status": "passed", "message": "无未确认的份额变动事件"}


def _get_product_asset_type(db: Session, product: Product) -> str:
    """从产品表获取资产类型"""
    if product.asset_class_code:
        ac = db.query(AssetClassification).filter(
            AssetClassification.code == product.asset_class_code
        ).first()
        if ac:
            return ac.asset_type
    return "stock"  # 默认返回股票类型


# ==================== 冻结字段计算函数 ====================

def _calculate_frozen_shares(
    db: Session,
    portfolio_code: str,
    product_code: str,
    market: Optional[str],
    target_date: date
) -> Decimal:
    """计算基金在指定日期的冻结份额（pending卖出）"""
    query = db.query(func.sum(Trade.shares)).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.product_code == product_code,
        Trade.trade_type == "sell",
        Trade.status == "pending",
        Trade.trade_date <= target_date
    )
    
    if market:
        query = query.filter(Trade.market == market)
    
    result = query.scalar()
    return Decimal(str(result or 0))


def _calculate_portfolio_frozen_shares(
    db: Session,
    portfolio_code: str,
    target_date: date
) -> Decimal:
    """计算组合在指定日期的冻结份额（pending赎回总和）"""
    result = db.query(func.sum(Subscription.shares)).filter(
        Subscription.portfolio_code == portfolio_code,
        Subscription.sub_type == "redeem",
        Subscription.status == "pending",
        Subscription.apply_date <= target_date
    ).scalar()
    
    return Decimal(str(result or 0))


def _calculate_investor_frozen_shares(
    db: Session,
    portfolio_code: str,
    investor_code: str,
    target_date: date
) -> Decimal:
    """计算投资人在指定日期的冻结份额（pending赎回）"""
    result = db.query(func.sum(Subscription.shares)).filter(
        Subscription.portfolio_code == portfolio_code,
        Subscription.investor_code == investor_code,
        Subscription.sub_type == "redeem",
        Subscription.status == "pending",
        Subscription.apply_date <= target_date
    ).scalar()
    
    return Decimal(str(result or 0))


# ==================== 工具函数 ====================

def _prev_trading_day(db: Session, target_date: date, offset: int = 1) -> date:
    """获取目标日期之前第offset个交易日"""
    trading_days = db.query(TradingCalendar.date).filter(
        TradingCalendar.date < target_date,
        TradingCalendar.is_open == True
    ).order_by(TradingCalendar.date.desc()).limit(offset).all()
    
    if len(trading_days) < offset:
        # 如果找不到足够的交易日，返回target_date - offset天
        return target_date - timedelta(days=offset)
    
    return trading_days[-1][0]