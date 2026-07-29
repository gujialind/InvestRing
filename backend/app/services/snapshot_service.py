"""
快照生成服务

提供组合快照的生成、重算和校验功能。
三张快照表按固定顺序生成：portfolio_position → portfolio_value_snapshot → investor_holding

注意：catch_up_snapshots / generate_next_snapshot 属编排层函数（issue #84），
采用逐日 checkpoint commit/rollback，是 AGENTS.md §4.1「service 不 commit」
的编排层例外（与 task_runner._generate_snapshots_for_date 语义一致）：
多日回补中已完成的日子须保留，失败日仅回滚当日。
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, delete

from app.models import (
    Portfolio, PortfolioPosition, PortfolioValueSnapshot, InvestorHolding,
    Trade, Subscription, ShareChangeEvent, PriceRecord, Product,
    TradingCalendar, Investor, AssetClassification
)
from app.services.trading_utils import (
    is_trading_day as _trading_utils_is_trading_day,
    get_next_trading_day,
    get_latest_snapshot_date,
)
from app.services.exceptions import BusinessError, NotFoundError
from app.services.subscription_service import unconfirm_single_subscription
from app.models.manual_market_value import ManualMarketValue
from app.utils.quantize import quantize_shares

logger = logging.getLogger(__name__)


def generate_daily_snapshots(
    db: Session,
    portfolio_code: str,
    target_date: date,
    check_continuity: bool = True,
) -> Dict[str, Any]:
    """
    生成指定组合在指定日期的三张快照表
    
    Args:
        db: 数据库会话
        portfolio_code: 组合代码
        target_date: 目标日期
        check_continuity: 是否强制快照连续性校验（重算路径逐日重建时须 bypass）
        
    Returns:
        生成结果
        
    Raises:
        ValueError: 当依赖数据不完整或校验失败时
        BusinessError: SNAPSHOT_NOT_CONTINUOUS——目标日与已有快照不连续

    Note:
        本函数不 commit/rollback（AGENTS.md §4.1，事务边界交调用方），
        仅 flush 保证同一事务内后续读取（如重算次日循环、auto_confirm）可见。
    """
    # 1. 前置校验
    _validate_portfolio(db, portfolio_code)
    _validate_trading_day(db, target_date)
    if check_continuity:
        _validate_snapshot_continuity(db, portfolio_code, target_date)
    
    if failed_checks := [
        v for v in validate_snapshot_dependencies(db, portfolio_code, target_date)
        if v["status"] == "failed"
    ]:
        error_messages = "; ".join([v["message"] for v in failed_checks])
        raise ValueError(f"依赖数据校验失败: {error_messages}")
    
    # 2. 删除已有快照（如果存在）
    _delete_existing_snapshots(db, portfolio_code, target_date)
    
    # 3. 生成持仓快照（issue #71：附带负现金 warnings，不阻断生成）
    positions, warnings = _generate_portfolio_position(db, portfolio_code, target_date)
    
    # 无持仓时跳过快照生成（组合尚无资产，如首次申购确认前）
    if not positions:
        db.flush()
        logger.info(
            f"快照跳过: portfolio={portfolio_code}, date={target_date}, "
            f"原因=无持仓"
        )
        return {
            "success": True,
            "message": "跳过：组合无持仓",
            "portfolio_code": portfolio_code,
            "snapshot_date": target_date,
            "total_value": 0,
            "total_shares": 0,
            "unit_price": 0,
            "warnings": None,
        }
    
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
    
    db.flush()
    
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
        "warnings": warnings or None,
    }


def recalculate_snapshots(
    db: Session,
    portfolio_code: Optional[str],
    start_date: date,
    end_date: date,
) -> Dict[str, Any]:
    """
    重算指定时间区间的快照

    流程（每个交易日 D）：
    1. 校验依赖数据
    2. 删除旧快照（自动级联回退依赖该快照的申购/赎回）
    3. 重新生成快照
    4. 自动确认 apply_date<=D 的 pending 申购/赎回

    注意：若 end_date 之后存在快照，会自动扩展重算区间至最新快照日，
    因为 D 日快照被重算后，依赖它的 D+1 日及以后的快照也必须重新生成。

    Args:
        db: 数据库会话
        portfolio_code: 组合代码（None表示所有活跃组合）
        start_date: 起始日期
        end_date: 结束日期（若之后有快照会自动扩展）

    Returns:
        重算结果

    Note:
        本函数全程不 commit/rollback（issue #58，AGENTS.md §4.1）：
        删旧快照、级联回退、重建、auto_confirm 全部停留在同一事务内，
        由调用方在无 errors 时统一 commit、有 errors 时统一 rollback，
        对外表现为「要么完整成功，要么无变化」。
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
        # 检查 end_date 之后是否存在快照，若有则自动扩展 end_date
        # 因为 D 日快照被重算后，D+1 日快照依赖 D 日数据，也必须重新生成
        latest_snapshot_date = db.query(func.max(PortfolioValueSnapshot.snapshot_date)).filter(
            PortfolioValueSnapshot.portfolio_code == portfolio.code
        ).scalar()
        effective_end_date = end_date
        if latest_snapshot_date and latest_snapshot_date > end_date:
            logger.info(
                f"组合 {portfolio.code}: end_date({end_date}) 后存在快照"
                f"(最新={latest_snapshot_date})，自动扩展重算区间"
            )
            effective_end_date = latest_snapshot_date

        result = {
            "portfolio_code": portfolio.code,
            "processed_dates": [],
            "total_processed": 0,
            "auto_confirmed": [],
            "cascaded_unconfirmed": [],
            "errors": [],
            "warnings": [],
        }

        if effective_end_date > end_date:
            result["end_date_extended_to"] = effective_end_date.isoformat()

        # 整区间预校验（issue #58 增强）：在删除任何快照前一次性校验全部交易日的
        # 静态依赖，NAV 缺失在任何写操作前被拦住，降低回滚压力。
        # 静态/动态检查项的归类统一由 validate_snapshot_dependencies 的
        # static_only 参数定义（单一口径）；循环内逐日全量校验保留。
        precheck_failures = []
        precheck_date = start_date
        while precheck_date <= effective_end_date:
            if _is_trading_day(db, precheck_date):
                static_failed = [
                    v for v in validate_snapshot_dependencies(
                        db, portfolio.code, precheck_date, static_only=True
                    )
                    if v["status"] == "failed"
                ]
                for v in static_failed:
                    precheck_failures.append(
                        f"{precheck_date.isoformat()}: {v['message']}"
                    )
            precheck_date += timedelta(days=1)
        if precheck_failures:
            raise ValueError(
                f"组合 {portfolio.code} 预校验失败，未删除任何快照: "
                + " | ".join(precheck_failures)
            )

        current_date = start_date
        while current_date <= effective_end_date:
            try:
                # 检查是否为交易日
                if not _is_trading_day(db, current_date):
                    current_date += timedelta(days=1)
                    continue

                # 校验依赖数据
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
                    # #35: 单日校验失败即停止，避免后续日基于缺失数据生成错误快照
                    break

                # 删除旧快照并级联回退依赖该快照的申购/赎回
                delete_info = _delete_existing_snapshots(db, portfolio.code, current_date)
                if delete_info["cascaded_subscriptions"]:
                    result["cascaded_unconfirmed"].extend(
                        delete_info["cascaded_subscriptions"]
                    )

                # 先生成快照（作为自动确认的 NAV 依赖）
                # 重算逐日重建，当前日之后的旧快照仍存在，须 bypass 连续性校验
                snapshot_result = generate_daily_snapshots(
                    db, portfolio.code, current_date, check_continuity=False,
                )
                # issue #71：累积每日负现金 warnings（与 errors 聚合风格一致）
                if snapshot_result.get("warnings"):
                    result["warnings"].extend(snapshot_result["warnings"])

                # 自动确认 apply_date<=current_date 的 pending 申购/赎回
                auto_results = auto_confirm_after_snapshot(
                    db, portfolio.code, current_date
                )
                if auto_results:
                    result["auto_confirmed"].extend(auto_results)
                    # 申赎统一 T+1 确认，刚确认的申赎 confirm_date = D+1 > D
                    # 不会被 D 日的 investor_holding 包含，无需局部刷新

                result["processed_dates"].append(current_date.isoformat())
                result["total_processed"] += 1

            except Exception as e:
                # 不在此 rollback：回滚交调用方（errors 非空时统一回滚整个事务）
                result["errors"].append({
                    "date": current_date.isoformat(),
                    "error": str(e)
                })
                logger.error(
                    f"重算失败: portfolio={portfolio.code}, date={current_date}, error={str(e)}"
                )
                # #35: 单日异常即停止，避免后续日基于缺失数据继续
                break

            current_date += timedelta(days=1)

        results.append(result)

    return {
        "success": True,
        "message": f"重算完成，共处理{len(portfolios)}个组合",
        "results": results
    }


def catch_up_snapshots(
    db: Session,
    portfolio_code: str,
    to_date: date,
) -> Dict[str, Any]:
    """
    从最新快照日的下一交易日起，逐交易日追平快照至 to_date（含）。

    每日 generate_daily_snapshots + auto_confirm_after_snapshot + commit
    （编排层 checkpoint，AGENTS.md §4.1 例外）；单日失败 rollback 当日并停止，
    已成功的日子保留，结果附 failed_date 与 error。

    Raises:
        NotFoundError: PORTFOLIO_NOT_FOUND——组合不存在
        BusinessError: NO_SNAPSHOT_BASELINE——组合尚无快照基线；
            CALENDAR_NOT_SYNCED——交易日历缺少最新快照日之后的交易日
    """
    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise NotFoundError(
            code="PORTFOLIO_NOT_FOUND", message=f"组合 {portfolio_code} 不存在"
        )

    latest = get_latest_snapshot_date(db, portfolio_code)
    if latest is None:
        raise BusinessError(
            code="NO_SNAPSHOT_BASELINE",
            message="组合尚无快照基线，请先用 snapshot generate 生成首日快照",
        )

    # 幂等：已追平（或 to_date 早于最新快照日）直接返回，零副作用
    if latest >= to_date:
        return {
            "portfolio_code": portfolio_code,
            "to_date": to_date.isoformat(),
            "generated_count": 0,
            "generated_dates": [],
            "latest_snapshot_date": latest.isoformat(),
            "message": "已追平",
        }

    result: Dict[str, Any] = {
        "portfolio_code": portfolio_code,
        "to_date": to_date.isoformat(),
        "generated_count": 0,
        "generated_dates": [],
    }

    current = get_next_trading_day(db, latest, days=1)
    # get_next_trading_day 日历耗尽时回退返回 from_date 本身
    if not current or current <= latest:
        raise BusinessError(
            code="CALENDAR_NOT_SYNCED",
            message=f"交易日历中找不到 {latest} 之后的交易日，请先同步交易日历",
        )

    while current and current <= to_date:
        try:
            generate_daily_snapshots(db, portfolio_code, current)
            auto_confirm_after_snapshot(db, portfolio_code, current)
            # 逐日 checkpoint commit：已完成日立即落库
            db.commit()
            result["generated_dates"].append(current.isoformat())
            result["generated_count"] += 1
        except Exception as e:
            db.rollback()
            result["failed_date"] = current.isoformat()
            result["error"] = str(e)
            logger.error(
                f"追平快照失败: portfolio={portfolio_code}, date={current}, error={str(e)}"
            )
            break
        # 防死循环：日历耗尽时 get_next_trading_day 返回 None 或 current 本身
        nxt = get_next_trading_day(db, current, days=1)
        if not nxt or nxt == current:
            break
        current = nxt

    final_latest = get_latest_snapshot_date(db, portfolio_code)
    result["latest_snapshot_date"] = final_latest.isoformat() if final_latest else None
    if "failed_date" in result:
        result["message"] = (
            f"追平中断于 {result['failed_date']}，已生成 {result['generated_count']} 日快照"
        )
    else:
        result["message"] = f"追平完成，共生成 {result['generated_count']} 日快照"
    return result


def generate_next_snapshot(
    db: Session,
    portfolio_code: str,
) -> Dict[str, Any]:
    """
    生成最新快照日的下一个交易日快照（单日顺延）。

    生成 + auto_confirm 后即 commit（编排层 checkpoint，AGENTS.md §4.1 例外）。

    Raises:
        NotFoundError: PORTFOLIO_NOT_FOUND——组合不存在
        BusinessError: NO_SNAPSHOT_BASELINE——组合尚无快照基线；
            CALENDAR_NOT_SYNCED——交易日历缺少最新快照日之后的交易日
    """
    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise NotFoundError(
            code="PORTFOLIO_NOT_FOUND", message=f"组合 {portfolio_code} 不存在"
        )

    latest = get_latest_snapshot_date(db, portfolio_code)
    if latest is None:
        raise BusinessError(
            code="NO_SNAPSHOT_BASELINE",
            message="组合尚无快照基线，请先用 snapshot generate 生成首日快照",
        )

    next_day = get_next_trading_day(db, latest, days=1)
    if not next_day or next_day <= latest:
        raise BusinessError(
            code="CALENDAR_NOT_SYNCED",
            message=f"交易日历中找不到 {latest} 之后的交易日，请先同步交易日历",
        )

    gen_result = generate_daily_snapshots(db, portfolio_code, next_day)
    auto_confirm_after_snapshot(db, portfolio_code, next_day)
    db.commit()

    return {
        "success": True,
        "message": gen_result["message"],
        "portfolio_code": portfolio_code,
        "generated_date": next_day.isoformat(),
        "total_value": gen_result["total_value"],
        "total_shares": gen_result["total_shares"],
        "unit_price": gen_result["unit_price"],
        "warnings": gen_result.get("warnings"),
    }


def validate_snapshot_dependencies(
    db: Session,
    portfolio_code: str,
    target_date: date,
    static_only: bool = False
) -> List[Dict[str, Any]]:
    """
    校验生成快照所需的依赖数据
    
    Args:
        db: 数据库会话
        portfolio_code: 组合代码
        target_date: 目标日期
        static_only: 仅执行静态检查项（交易日、净值完整性），用于 recalculate
            的整区间预校验（issue #58）。pending 申赎/事件会被重算循环内的
            auto_confirm 逐日消化，属于重算的正常输入，纳入预校验会误杀
            合法重算，故归为动态项排除。检查项的静态/动态归类以本函数为
            单一事实来源，新增检查项时须在此处显式归类。
        
    Returns:
        校验结果列表
    """
    checks = []
    
    # 1. 检查交易日（静态）
    checks.append(_check_trading_day(db, target_date))
    
    # 2. 检查pending交易（动态：会被重算循环内 auto_confirm 消化）
    if not static_only:
        checks.append(_check_pending_transactions(db, portfolio_code, target_date))
    
    # 3. 检查净值数据完整性（静态）
    checks.append(_check_price_data_completeness(db, portfolio_code, target_date))
    
    # 4. 检查分红事件状态（动态：会被重算循环内 auto_confirm 消化）
    if not static_only:
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
    """检查指定日期是否为交易日（委托给 trading_utils）"""
    return _trading_utils_is_trading_day(db, target_date)


def _validate_snapshot_continuity(db: Session, portfolio_code: str, target_date: date):
    """
    校验快照连续性（AGENTS.md §2.1）：
    - 无快照时（首次生成）不限制；
    - target_date == 最新快照日：允许（重建最新一日，无空洞、无下游依赖）；
    - target_date == 最新快照日的下一个交易日：允许（正常顺延）；
    - 其他情况（跳过交易日、或重建其后仍有快照的中间日）拒绝。
    """
    latest = db.query(func.max(PortfolioValueSnapshot.snapshot_date)).filter(
        PortfolioValueSnapshot.portfolio_code == portfolio_code
    ).scalar()
    if latest is None or target_date == latest:
        return
    expected = get_next_trading_day(db, latest, days=1)
    if target_date == expected:
        return
    if target_date < latest:
        message = (
            f"{target_date} 早于最新快照日 {latest}，不允许单独重建中间快照，"
            f"请使用重算接口（recalculate）"
        )
    else:
        message = (
            f"快照必须按交易日连续生成：最新快照日为 {latest}，"
            f"下一个应生成 {expected}，不允许跳过生成 {target_date}"
        )
    raise BusinessError(code="SNAPSHOT_NOT_CONTINUOUS", message=message)


def _cascade_unconfirm_subscriptions(
    db: Session, portfolio_code: str, snapshot_date: date
) -> List[Dict[str, Any]]:
    """
    级联回退依赖指定日期快照的申购/赎回。

    查找所有 status='confirmed' 且 apply_date == snapshot_date 的记录，
    因为它们使用了该快照的 NAV 进行确认，快照被删后必须回退。
    同时删除关联的 CASH trade（transfer_group = "sub_{id}"）。

    Returns:
        被回退的记录信息列表
    """
    confirmed_subs = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.apply_date == snapshot_date,
            Subscription.status == "confirmed",
        )
        .all()
    )

    unconfirmed_list = []
    for sub in confirmed_subs:
        sub_id = sub.id
        sub_type = sub.sub_type
        try:
            unconfirm_single_subscription(db, sub, check_snapshot=False, auto_flush=False)
            unconfirmed_list.append({
                "id": sub_id,
                "sub_type": sub_type,
                "confirm_date": snapshot_date.isoformat(),
                "action": "unconfirmed",
            })
            logger.info(
                f"级联取消确认: subscription_id={sub_id}, "
                f"portfolio={portfolio_code}, snapshot_date={snapshot_date}"
            )
        except Exception as e:
            logger.warning(
                f"级联取消确认失败: subscription_id={sub_id}, error={str(e)}"
            )

    return unconfirmed_list


def _cascade_unconfirm_share_change_events(
    db: Session, portfolio_code: str, snapshot_date: date
) -> List[Dict[str, Any]]:
    """
    级联回退依赖指定日期持仓快照的 confirmed 事件。
    仅回退 entitlement_date == snapshot_date 的事件——其确认数据
    （entitlement_shares）来自被删除的 entitlement_date 持仓快照，故需回退。
    ex_date == snapshot_date 但 entitlement_date < snapshot_date 的事件，
    其依赖的持仓快照未删除，数据仍有效，保持 confirmed（重新生成快照时被重新应用）。
    只处理父/独立记录（parent_event_id IS NULL），子记录被物理删除。
    """
    events = db.query(ShareChangeEvent).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.status == "confirmed",
        ShareChangeEvent.parent_event_id.is_(None),  # 只处理父/独立记录
        ShareChangeEvent.entitlement_date == snapshot_date,  # 只回退持仓快照被删的
    ).all()

    result = []
    for event in events:
        # 父记录：先物理删除所有子记录（确保 regen 重确认不重复拆分）
        db.query(ShareChangeEvent).filter(
            ShareChangeEvent.parent_event_id == event.id
        ).delete(synchronize_session=False)

        # 然后回退父记录本身
        event.status = "pending"
        event.confirmed_at = None
        event.entitlement_shares = None
        event.shares_before = None
        event.shares_change = None
        event.shares_after = None
        event.cash_change = None
        result.append({"id": event.id, "action": "unconfirmed"})
        logger.info(
            f"级联取消确认事件: event_id={event.id}, "
            f"portfolio={portfolio_code}, snapshot_date={snapshot_date}"
        )

    return result


def _delete_existing_snapshots(
    db: Session, portfolio_code: str, target_date: date
) -> Dict[str, Any]:
    """
    删除指定日期的三张快照表记录。

    删除前先级联回退依赖该快照的已确认申购/赎回。
    """
    # 先级联回退依赖该快照的申购（含 CASH trade）
    cascaded = _cascade_unconfirm_subscriptions(db, portfolio_code, target_date)
    # 级联回退依赖该快照的事件
    cascaded_events = _cascade_unconfirm_share_change_events(db, portfolio_code, target_date)
    # #40 改进4：级联回退详情日志
    logger.info(
        f"级联回退: portfolio={portfolio_code}, date={target_date}, "
        f"subscriptions={len(cascaded)}, events={len(cascaded_events)}"
    )

    # #40 改进2：用 db.execute(delete()) 绕过 instance-level before_delete listener
    # （bulk SQL delete 不触发 mapper event，明确表达内部快照删除意图）
    pp_deleted = db.execute(
        delete(PortfolioPosition).where(
            PortfolioPosition.portfolio_code == portfolio_code,
            PortfolioPosition.snapshot_date == target_date,
        )
    ).rowcount
    
    nav_deleted = db.execute(
        delete(PortfolioValueSnapshot).where(
            PortfolioValueSnapshot.portfolio_code == portfolio_code,
            PortfolioValueSnapshot.snapshot_date == target_date,
        )
    ).rowcount

    ih_deleted = db.execute(
        delete(InvestorHolding).where(
            InvestorHolding.portfolio_code == portfolio_code,
            InvestorHolding.snapshot_date == target_date,
        )
    ).rowcount

    return {
        "cascaded_subscriptions": cascaded,
        "cascaded_events": cascaded_events,
        "deleted": {
            "portfolio_position": pp_deleted,
            "portfolio_value_snapshot": nav_deleted,
            "investor_holding": ih_deleted,
        },
    }


def _generate_portfolio_position(
    db: Session,
    portfolio_code: str,
    target_date: date
) -> Tuple[List[PortfolioPosition], List[Dict[str, Any]]]:
    """
    生成持仓快照
    
    逻辑：
    1. 获取前一日快照作为基准
    2. 应用期间内所有已确认交易
    3. 获取目标日价格计算市值
    4. 计算冻结字段

    Returns:
        (positions, warnings) 元组。warnings 为负现金告警列表（issue #71）：
        CASH 条目 cash_amount < 0 时记录 negative_cash 告警但不阻断生成
        （历史快照可能已有负现金，阻断会使重算不可用）。
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
            if pos.product_code == "CASH":
                key = ("CASH", "", pos.platform_code)
                positions[key] = {
                    "shares": None,
                    "cash_amount": Decimal(str(pos.cash_amount or 0)),
                    "cost_price": None,
                    "asset_type": "cash",
                }
                continue
            key = (pos.product_code, pos.market, pos.platform_code)
            pos_asset_type = pos.asset_type
            if not pos_asset_type:
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
                "cash_amount": Decimal(str(pos.cash_amount or 0)) if pos.cash_amount is not None else None,
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
        if trade.product_code == "CASH":
            cash_key = ("CASH", "", trade.platform_code)
            if cash_key not in positions:
                positions[cash_key] = {"shares": None, "cash_amount": Decimal("0"), "cost_price": None, "asset_type": "cash"}
            positions[cash_key]["cash_amount"] += Decimal(str(trade.amount or 0))
            continue
        key = (trade.product_code, trade.market, trade.platform_code)
        if key not in positions:
            product = db.query(Product).filter(
                Product.code == trade.product_code,
                Product.market == trade.market
            ).first()
            positions[key] = {
                "shares": Decimal("0"),
                "cash_amount": None,
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
        if trade.product_code == "CASH":
            cash_key = ("CASH", "", trade.platform_code)
            if cash_key not in positions:
                positions[cash_key] = {"shares": None, "cash_amount": Decimal("0"), "cost_price": None, "asset_type": "cash"}
            positions[cash_key]["cash_amount"] -= Decimal(str(trade.amount or 0))
            continue
        key = (trade.product_code, trade.market, trade.platform_code)
        if key in positions:
            positions[key]["shares"] -= Decimal(str(trade.shares or 0))

    # 应用份额变动事件（窗口内 confirmed）
    # 只读取 platform_code IS NOT NULL 的子记录/平台级记录，跳过基金级父记录
    # 按 entitlement_date 升序处理
    # 窗口约束：ex_date >= start_apply_date 避免重复累加已经在前一日快照中反映的事件
    confirmed_events = db.query(ShareChangeEvent).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.status == "confirmed",
        ShareChangeEvent.ex_date >= start_apply_date,
        ShareChangeEvent.ex_date <= target_date,
        ShareChangeEvent.platform_code.isnot(None),  # 跳过基金级父记录
    ).order_by(ShareChangeEvent.entitlement_date.asc()).all()

    for event in confirmed_events:
        if event.event_type in ("cash_dividend", "forced_adjustment"):
            if event.cash_change:
                cash_key = ("CASH", "", event.platform_code)
                if cash_key not in positions:
                    positions[cash_key] = {"shares": None, "cash_amount": Decimal("0"), "cost_price": None, "asset_type": "cash"}
                positions[cash_key]["cash_amount"] += Decimal(str(event.cash_change))
            continue

        # 按平台精确匹配持仓
        fund_key = (event.product_code, event.market, event.platform_code)

        if fund_key not in positions:
            # 持仓不存在，创建
            product = db.query(Product).filter(
                Product.code == event.product_code,
                Product.market == event.market
            ).first()
            positions[fund_key] = {
                "shares": Decimal("0"),
                "cash_amount": None,
                "cost_price": None,
                "asset_type": _get_product_asset_type(db, product) if product else "stock",
            }

        old_shares = Decimal(str(positions[fund_key]["shares"] or 0))

        # 使用确认时预计算的 shares_change（不重算）
        if event.shares_change is not None:
            positions[fund_key]["shares"] = old_shares + Decimal(str(event.shares_change))

    # CASH 持仓：应用 manual_market_value 绝对覆盖（日期精确匹配）
    for key, pos_data in list(positions.items()):
        if pos_data.get("asset_type") == "cash":
            _, _, plat_code = key
            manual = db.query(ManualMarketValue).filter(
                ManualMarketValue.portfolio_code == portfolio_code,
                ManualMarketValue.platform_code == plat_code,
                ManualMarketValue.product_code == "CASH",
                ManualMarketValue.value_date == target_date,
            ).first()
            if manual:
                pos_data["cash_amount"] = Decimal(str(manual.market_value))

    # 构建最终的持仓快照对象
    result_positions = []
    for (product_code, market, platform_code), pos_data in positions.items():
        # 跳过零持仓（现金允许为0但不跳过，保留现金持仓记录）
        is_cash = pos_data.get("asset_type") == "cash"
        if not is_cash:
            if pos_data["shares"] is not None and pos_data["shares"] <= 0 and (pos_data.get("cash_amount") or Decimal("0")) <= 0:
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
            market_value = pos_data["cash_amount"]
        elif product:
            # 根据产品类型获取净值
            if product.is_qdii:
                # QDII：取前一交易日净值
                prev_date = _prev_trading_day(db, target_date, 1)
                price_record = db.query(PriceRecord).filter(
                    PriceRecord.product_code == product_code,
                    PriceRecord.market == market,
                    PriceRecord.price_date <= prev_date
                ).order_by(PriceRecord.price_date.desc()).first()
            else:
                # 普通基金：取当日净值
                price_record = db.query(PriceRecord).filter(
                    PriceRecord.product_code == product_code,
                    PriceRecord.market == market,
                    PriceRecord.price_date <= target_date
                ).order_by(PriceRecord.price_date.desc()).first()
            
            if price_record:
                unit_price = Decimal(str(price_record.unit_price))
                market_value = pos_data["shares"] * unit_price
        
        # 计算冻结份额（pending卖出）
        frozen_shares = _calculate_frozen_shares(db, portfolio_code, product_code, market, target_date)
        # 计算冻结金额（pending CASH sells，仅 CASH 持仓行；#40 改进1）
        frozen_amount = (
            _calculate_frozen_amount(db, portfolio_code, platform_code, target_date)
            if is_cash else Decimal("0")
        )
        
        position = PortfolioPosition(
            portfolio_code=portfolio_code,
            platform_code=platform_code,
            product_code=product_code,
            market=market,
            shares=float(pos_data["shares"]) if pos_data["shares"] and not is_cash else None,
            cash_amount=float(pos_data["cash_amount"]) if is_cash and pos_data["cash_amount"] is not None else None,
            frozen_shares=float(frozen_shares) if frozen_shares > 0 else 0,
            frozen_amount=float(frozen_amount) if frozen_amount > 0 else 0,
            cost_price=float(pos_data["cost_price"]) if pos_data["cost_price"] else None,
            unit_price=float(unit_price) if unit_price else None,
            market_value=float(market_value) if market_value is not None else None,
            asset_type=pos_data["asset_type"],
            snapshot_date=target_date
        )
        result_positions.append(position)
    
    # issue #71：检测负现金 CASH 条目，产出 warning（不阻断生成）
    warnings: List[Dict[str, Any]] = []
    for pos in result_positions:
        if (
            pos.product_code == "CASH"
            and pos.cash_amount is not None
            and Decimal(str(pos.cash_amount)) < 0
        ):
            warnings.append({
                "type": "negative_cash",
                "platform_code": pos.platform_code,
                "cash_amount": float(pos.cash_amount),
                "snapshot_date": target_date.isoformat(),
            })
            logger.warning(
                f"负现金告警: portfolio={portfolio_code}, platform={pos.platform_code}, "
                f"date={target_date}, cash_amount={pos.cash_amount}"
            )

    return result_positions, warnings


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
        elif pos.cash_amount is not None:
            total_value += Decimal(str(pos.cash_amount))
    
    # 获取总份额：前序快照 + 窗口内申赎变动（与 _generate_portfolio_position 增量法一致）
    prev_pvs_date = db.query(func.max(PortfolioValueSnapshot.snapshot_date)).filter(
        PortfolioValueSnapshot.portfolio_code == portfolio_code,
        PortfolioValueSnapshot.snapshot_date < target_date
    ).scalar()

    prev_pvs = None
    if prev_pvs_date:
        prev_pvs = db.query(PortfolioValueSnapshot).filter(
            PortfolioValueSnapshot.portfolio_code == portfolio_code,
            PortfolioValueSnapshot.snapshot_date == prev_pvs_date
        ).first()
        total_shares = Decimal(str(prev_pvs.total_shares or 0))

        # 窗口内申购确认份额（前序快照次日 ~ 目标日）
        confirm_start = prev_pvs_date + timedelta(days=1)
        subscribe_shares = db.query(func.sum(Subscription.shares)).filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.sub_type == "subscribe",
            Subscription.status == "confirmed",
            Subscription.confirm_date >= confirm_start,
            Subscription.confirm_date <= target_date
        ).scalar()
        redeem_shares = db.query(func.sum(Subscription.shares)).filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.sub_type == "redeem",
            Subscription.status == "confirmed",
            Subscription.confirm_date >= confirm_start,
            Subscription.confirm_date <= target_date
        ).scalar()

        total_shares += Decimal(str(subscribe_shares or 0)) - Decimal(str(redeem_shares or 0))
    else:
        # 首次快照：无前序快照，使用市值作为初始份额（NAV=1.0，份额=金额）
        # 份额产生点：量化到 2 位，与首次申购确认份额（amount/1.0 量化）口径一致
        # 极小值边界：若 total_value 在 (0, 0.01) 区间，量化后 total_shares=0.00，
        # 后续走 total_shares<=0 分支 unit_price 固定 1.0000 作为兜底，属预期设计
        total_shares = quantize_shares(total_value) if total_value > 0 else Decimal("1")
    
    # 计算净值
    if total_shares > 0:
        unit_price = total_value / total_shares
    else:
        unit_price = Decimal("1.0000")
    
    # 计算冻结份额（pending赎回）
    frozen_shares = _calculate_portfolio_frozen_shares(db, portfolio_code, target_date)
    
    # 计算净值涨跌幅（#40 改进1，复用已查到的 prev_pvs）
    if prev_pvs and prev_pvs.unit_price and prev_pvs.unit_price > 0:
        unit_price_change_pct = (unit_price - Decimal(str(prev_pvs.unit_price))) / Decimal(str(prev_pvs.unit_price))
    else:
        unit_price_change_pct = Decimal("0")
    
    snapshot = PortfolioValueSnapshot(
        portfolio_code=portfolio_code,
        snapshot_date=target_date,
        total_value=float(total_value),
        total_shares=float(total_shares),
        unit_price=float(unit_price.quantize(Decimal("0.0001"))),
        unit_price_change_pct=float(unit_price_change_pct.quantize(Decimal("0.0001"))) if unit_price_change_pct else 0,
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
        
        # 派生字段（#40 改进1）
        market_value = prev_shares * Decimal(str(value_snapshot.unit_price))
        total_cost = prev_shares * prev_cost
        profit = market_value - total_cost
        
        holding = InvestorHolding(
            portfolio_code=portfolio_code,
            investor_code=investor.code,
            snapshot_date=target_date,
            shares=float(prev_shares),
            frozen_shares=float(frozen_shares) if frozen_shares > 0 else 0,
            cost_per_share=float(prev_cost.quantize(Decimal("0.0001"))) if prev_cost > 0 else 0,
            market_value=float(market_value),
            total_cost=float(total_cost),
            profit=float(profit),
        )
        result_holdings.append(holding)
    
    return result_holdings


def auto_confirm_after_snapshot(
    db: Session,
    portfolio_code: str,
    snapshot_date: date
) -> List[Dict[str, Any]]:
    """
    快照生成后自动确认 apply_date<=snapshot_date 的 pending 申购/赎回。

    包含 apply_date < snapshot_date 的记录（可能因级联回退而重新变为 pending）。
    按 apply_date 升序确认，确保 is_first 判断正确。
    此时 snapshot_date 的快照已存在，NAV 可获取。
    单笔失败不影响整批，失败记录到结果中。

    Args:
        db: 数据库会话
        portfolio_code: 组合代码
        snapshot_date: 快照日期

    Returns:
        确认结果列表
    """
    from app.services.subscription_service import (
        confirm_single_subscription,
        NavNotAvailableError,
        InvalidStatusError,
    )

    pending_subs = (
        db.query(Subscription)
        .filter(
            Subscription.portfolio_code == portfolio_code,
            Subscription.apply_date <= snapshot_date,
            Subscription.status == "pending",
        )
        .order_by(Subscription.apply_date.asc())
        .all()
    )

    results = []
    for sub in pending_subs:
        sub_id = sub.id
        sub_type = sub.sub_type
        try:
            confirm_single_subscription(db, sub, auto_flush=True)
            results.append({
                "id": sub_id,
                "sub_type": sub_type,
                "apply_date": snapshot_date.isoformat(),
                "action": "auto_confirmed",
                "status": "success",
            })
            logger.info(
                f"自动确认: subscription_id={sub_id}, "
                f"portfolio={portfolio_code}, apply_date={snapshot_date}"
            )
        except (NavNotAvailableError, InvalidStatusError) as e:
            results.append({
                "id": sub_id,
                "sub_type": sub_type,
                "apply_date": snapshot_date.isoformat(),
                "action": "auto_confirm_failed",
                "error": str(e),
            })
            logger.warning(
                f"自动确认失败: subscription_id={sub_id}, error={str(e)}"
            )
        except Exception as e:
            results.append({
                "id": sub_id,
                "sub_type": sub_type,
                "apply_date": snapshot_date.isoformat(),
                "action": "auto_confirm_failed",
                "error": str(e),
            })
            logger.error(
                f"自动确认异常: subscription_id={sub_id}, error={str(e)}"
            )

    # #33: auto_confirm(D) 确认 confirm_date == next_trading_day(D) 的交易/事件，
    # 配合逐日循环生成快照，使 confirm_date==C 的交易在快照 C 中体现。
    from app.services.trade_service import confirm_single_trade
    next_confirm_date = get_next_trading_day(db, snapshot_date, days=1)

    # Trade 自动确认（confirm_date == next_trading_day(D) 的 pending trades）
    # 排除 transfer_group 非空的 CASH trade：
    #   - 跨天转移两腿：由下方 cross_day_transfers 分支处理
    #   - 基金调仓配对 CASH 腿：由原子翻转跟随基金腿
    pending_trades = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.status == "pending",
        Trade.confirm_date == next_confirm_date,
        Trade.transfer_group.is_(None) | (Trade.product_code != "CASH"),
    ).all()

    for trade in pending_trades:
        try:
            product = db.query(Product).filter(
                Product.code == trade.product_code,
                Product.market == trade.market,
            ).first()
            # 走公共确认逻辑：净值型产品按 T 日净值重算 shares/amount，
            # 并原子同步 transfer_group 配对腿（#29）；重算历史时现金基线
            # 尚未逐日重建，跳过买入确认的可用现金校验（#78）
            confirm_single_trade(db, trade, product, skip_cash_check=True)
            results.append({
                "id": trade.id,
                "type": "trade",
                "action": "auto_confirmed",
                "status": "success",
            })
            logger.info(f"自动确认 Trade: trade_id={trade.id}, portfolio={portfolio_code}")
        except Exception as e:
            results.append({
                "id": trade.id,
                "type": "trade",
                "action": "auto_confirm_failed",
                "error": str(e),
            })
            logger.warning(f"Trade auto-confirm failed: trade_id={trade.id}, {e}")

    # 跨天转移 auto_confirm（两腿均 pending，需同时确认）
    # 仅当 confirm_date == next_trading_day(D)（与其它交易同一时序）时处理
    cross_day_pending = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.status == "pending",
        Trade.product_code == "CASH",
        Trade.transfer_group.isnot(None),
        Trade.confirm_date == next_confirm_date,
    ).all()
    processed_groups = set()
    for trade in cross_day_pending:
        if trade.transfer_group in processed_groups:
            continue
        processed_groups.add(trade.transfer_group)
        try:
            # TRANSFER_NOT_READY 守卫
            if trade.confirm_date and trade.confirm_date > date.today():
                logger.info(f"跨天转移 {trade.transfer_group} 未到确认日，跳过")
                continue
            # 同时确认两腿
            paired_trades = db.query(Trade).filter(
                Trade.transfer_group == trade.transfer_group,
                Trade.status == "pending",
            ).all()
            for pt in paired_trades:
                pt.status = "confirmed"
            results.append({
                "transfer_group": trade.transfer_group,
                "type": "cross_day_transfer",
                "action": "auto_confirmed",
                "status": "success",
            })
            logger.info(f"自动确认跨天转移: transfer_group={trade.transfer_group}")
        except Exception as e:
            results.append({
                "transfer_group": trade.transfer_group,
                "type": "cross_day_transfer",
                "action": "auto_confirm_failed",
                "error": str(e),
            })
            logger.warning(f"Cross-day transfer auto-confirm failed: {trade.transfer_group}, {e}")

    # Event 自动确认（ex_date == next_trading_day(D) 的 pending events）
    # 只处理父/独立记录（跳过子记录，子记录由父记录确认时自动生成）
    pending_events = db.query(ShareChangeEvent).filter(
        ShareChangeEvent.portfolio_code == portfolio_code,
        ShareChangeEvent.status == "pending",
        ShareChangeEvent.ex_date == next_confirm_date,
        ShareChangeEvent.parent_event_id.is_(None),  # 只处理父/独立记录
    ).all()

    for event in pending_events:
        try:
            if event.platform_code is None:
                # 基金级事件：自动拆分为各平台子记录
                from app.services.share_change_event_service import _confirm_fund_level_event
                _confirm_fund_level_event(db, event)
            else:
                # 平台级事件：按 platform_code 过滤读取 entitlement_shares
                ent_position = db.query(PortfolioPosition).filter(
                    PortfolioPosition.portfolio_code == event.portfolio_code,
                    PortfolioPosition.product_code == event.product_code,
                    PortfolioPosition.platform_code == event.platform_code,
                    PortfolioPosition.snapshot_date == event.entitlement_date,
                ).first()
                entitlement_shares = Decimal(str(ent_position.shares or 0)) if ent_position else Decimal("0")

                event.entitlement_shares = entitlement_shares
                event.shares_before = entitlement_shares

                from app.services.share_change_event_service import _compute_event_fields
                _compute_event_fields(event)
                event.status = "confirmed"
                event.confirmed_at = datetime.now()
            results.append({
                "id": event.id,
                "type": "event",
                "action": "auto_confirmed",
                "status": "success",
            })
            logger.info(f"自动确认 Event: event_id={event.id}, portfolio={portfolio_code}")
        except Exception as e:
            results.append({
                "id": event.id,
                "type": "event",
                "action": "auto_confirm_failed",
                "error": str(e),
            })
            logger.warning(f"Event auto-confirm failed: event_id={event.id}, {e}")

    return results


# ==================== 校验函数 ====================

def _check_trading_day(db: Session, target_date: date) -> Dict[str, Any]:
    """检查目标日期是否为交易日"""
    cal = db.query(TradingCalendar).filter(
        TradingCalendar.calendar_date == target_date
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
    """检查是否存在pending交易

    confirm_date 为 NULL 时 SQL 比较恒不命中，故兜底按 trade_date/apply_date 判断，
    防止异常数据（如历史遗留的 NULL confirm_date）逃过校验静默生成脏快照。
    """
    pending_trades = db.query(Trade).filter(
        Trade.portfolio_code == portfolio_code,
        or_(
            Trade.confirm_date <= target_date,
            and_(Trade.confirm_date.is_(None), Trade.trade_date <= target_date),
        ),
        Trade.status == "pending"
    ).count()
    
    pending_subs = db.query(Subscription).filter(
        Subscription.portfolio_code == portfolio_code,
        or_(
            Subscription.confirm_date <= target_date,
            and_(Subscription.confirm_date.is_(None), Subscription.apply_date <= target_date),
        ),
        Subscription.status == "pending"
    ).count()
    
    if pending_trades > 0 or pending_subs > 0:
        details = []
        if pending_trades > 0:
            details.append(f"{pending_trades}笔confirm_date<={target_date}的待确认交易")
        if pending_subs > 0:
            details.append(f"{pending_subs}笔confirm_date<={target_date}的待确认申赎")
        return {
            "check_type": "pending_transactions",
            "status": "failed",
            "message": f"存在{', '.join(details)}，请先确认这些交易"
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
                PriceRecord.price_date == prev_date
            ).first()
            
            if not price:
                qdii_missing.append(f"{product_code}({market}) [T-1={prev_date}]")
        else:
            # 普通基金：检查target_date当日净值
            price = db.query(PriceRecord).filter(
                PriceRecord.product_code == product_code,
                PriceRecord.market == market,
                PriceRecord.price_date <= target_date
            ).order_by(PriceRecord.price_date.desc()).first()
            
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
        ShareChangeEvent.ex_date <= target_date,
        ShareChangeEvent.status == "pending"
    ).count()
    
    if pending_events > 0:
        return {
            "check_type": "share_change_events",
            "status": "failed",
            "message": f"存在{pending_events}笔未确认的份额变动事件（ex_date <= {target_date}），请先确认或取消后再生成快照"
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


def _calculate_frozen_amount(
    db: Session,
    portfolio_code: str,
    platform_code: Optional[str],
    target_date: date
) -> Decimal:
    """计算 CASH 持仓在指定日期的冻结金额（pending CASH sells，#40 改进1）。

    pending CASH sell 表示已承诺待执行的现金支出，需在 frozen_amount 中预留。
    按平台维度过滤，与 portfolio_position 的 CASH 分平台存储一致。
    """
    query = db.query(func.sum(Trade.amount)).filter(
        Trade.portfolio_code == portfolio_code,
        Trade.product_code == "CASH",
        Trade.trade_type == "sell",
        Trade.status == "pending",
        Trade.trade_date <= target_date,
    )
    if platform_code:
        query = query.filter(Trade.platform_code == platform_code)
    result = query.scalar()
    return Decimal(str(result or 0))


# ==================== 工具函数 ====================

def _prev_trading_day(db: Session, target_date: date, offset: int = 1) -> date:
    """获取目标日期之前第offset个交易日"""
    trading_days = db.query(TradingCalendar.calendar_date).filter(
        TradingCalendar.calendar_date < target_date,
        TradingCalendar.is_open == True
    ).order_by(TradingCalendar.calendar_date.desc()).limit(offset).all()
    
    if len(trading_days) < offset:
        # 如果找不到足够的交易日，返回target_date - offset天
        return target_date - timedelta(days=offset)
    
    return trading_days[-1][0]