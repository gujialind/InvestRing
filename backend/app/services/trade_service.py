"""
调仓交易确认服务

将 Trade 确认的核心业务逻辑（净值获取、份额/金额重算、配对 CASH 腿同步）
从路由层提取，供 HTTP API 手动确认与快照重算 auto_confirm 多处复用。
"""
import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.trade import Trade
from app.models.product import Product
from app.models.price_record import PriceRecord
from app.models.portfolio import Portfolio
from app.models.platform import Platform
from app.services.trading_utils import get_next_trading_day, is_trading_day, get_latest_snapshot_date
from app.services.position_service import calculate_available_cash, calculate_available_shares
from app.services.product_service import resolve_product_market
from app.services.exceptions import BusinessError, NotFoundError
from app.utils.quantize import quantize_shares

logger = logging.getLogger(__name__)


def get_nav_for_trade_confirmation(
    db: Session, product_code: str, market: str, trade_date: date
) -> Optional[Decimal]:
    """
    获取调仓交易确认时的净值

    规则：
    - 场外基金统一取 T 日（成交当日）净值，禁止向前查找，不区分 QDII/非 QDII。
      QDII 与非 QDII 的差异仅在确认间隔（T+2 / T+1），已通过创建时设定的
      confirm_date 体现；到确认日净值理应可取，缺失则由调用方拒绝确认。

    Args:
        db: 数据库会话
        product_code: 产品代码
        market: 市场类型
        trade_date: 交易日期（T日）

    Returns:
        净值（Decimal），如果不存在则返回 None（由调用方决定是否拒绝）
    """
    price_record = db.query(PriceRecord).filter(
        PriceRecord.product_code == product_code,
        PriceRecord.market == market,
        PriceRecord.price_date == trade_date
    ).first()

    if price_record and price_record.unit_price:
        return Decimal(str(price_record.unit_price))

    return None


def attach_paired_cash_leg(
    db: Session,
    fund_trade: Trade,
    cash_amount: Decimal,
    confirm_date: Optional[date],
    status: str = "pending",
    cash_platform_code: Optional[str] = None,
) -> Trade:
    """为基金腿生成 transfer_group 并构造/加入配对 CASH 腿。

    cash_amount 采用 router 语义 = 基金腿 actual_amount（买入=支出含费，卖出=收入）。
    cash_platform_code（issue #91）：CASH 腿平台，缺省同基金腿；传入时支持
    跨平台扣款（买）/到账（卖），两腿同 transfer_group 原子翻转。
    供 REST router 与后端 CLI 共用，确保基金买/卖必配 CASH 腿。

    Returns:
        新建的 CASH 腿（已 db.add，未 commit）
    """
    group = f"rebal_{uuid.uuid4().hex[:12]}"
    fund_trade.transfer_group = group
    cash_trade = Trade(
        portfolio_code=fund_trade.portfolio_code,
        platform_code=cash_platform_code or fund_trade.platform_code,
        product_code="CASH",
        market="",
        trade_type="sell" if fund_trade.trade_type == "buy" else "buy",
        shares=None,
        amount=cash_amount,
        price=Decimal("1"),
        fee=Decimal("0"),
        actual_amount=cash_amount,
        trade_date=fund_trade.trade_date,
        confirm_date=confirm_date,
        status=status,
        transfer_group=group,
    )
    db.add(cash_trade)
    return cash_trade


def sync_transfer_group(
    db: Session, trade: Trade, target_status: str, confirm_date: Optional[date] = None
):
    """同步 transfer_group 关联的另一腿状态、日期与金额

    - 传播 `trade.trade_date`（组内不变量：同 transfer_group 各腿 trade_date 恒等；
      PUT 改基金腿 trade_date 时据此随动 CASH 腿，其余路径为幂等写入）
    - 传播 `target_status` 与 `confirm_date`（unconfirm 时重算期望确认日）
    - 若源腿为基金腿（product_code != "CASH"），将其 actual_amount 镜像给配对
      CASH 腿（CASH 腿金额恒等于基金腿 actual_amount）。确认时净值型基金
      actual_amount 可能被重算，需同步；金额未变时为幂等写入
    """
    if not trade.transfer_group:
        return
    paired = db.query(Trade).filter(
        Trade.transfer_group == trade.transfer_group,
        Trade.id != trade.id,
    ).all()
    # CASH 腿金额 = 基金腿 actual_amount（买入=支出、卖出=收入）；
    # 仅当源腿为基金腿时向 CASH 腿镜像，避免 CASH→CASH / CASH→基金误写
    mirror_amount = None
    if trade.product_code != "CASH":
        mirror_amount = trade.actual_amount if trade.actual_amount is not None else trade.amount
    # #37 savepoint：配对腿更新失败回滚 savepoint，不影响外层事务
    # 用连接级 SAVEPOINT（db.connection().begin_nested()）而非 session 级
    # db.begin_nested()，避免触发 after_transaction_end 事件与测试隔离监听器冲突
    sp = db.connection().begin_nested()
    try:
        for paired_trade in paired:
            # 先同步 trade_date，保证下方 unconfirm 分支用新日期重算确认日
            paired_trade.trade_date = trade.trade_date
            paired_trade.status = target_status
            if confirm_date is not None:
                paired_trade.confirm_date = confirm_date
            elif target_status == "pending":
                # unconfirm 时需要重新计算期望确认日
                paired_product = db.query(Product).filter(
                    Product.code == paired_trade.product_code,
                    Product.market == paired_trade.market,
                ).first()
                if paired_product:
                    paired_confirm_days = paired_product.confirm_days or 0
                    paired_trade.confirm_date = get_next_trading_day(
                        db, paired_trade.trade_date, days=paired_confirm_days
                    )
            # 同步配对 CASH 腿金额（确认时净值重算后需同步）
            if mirror_amount is not None and paired_trade.product_code == "CASH":
                paired_trade.amount = mirror_amount
                paired_trade.actual_amount = mirror_amount
        db.flush()  # 确保 ORM 变更在 savepoint 内写入 DB
        sp.commit()
    except Exception:
        sp.rollback()
        raise


def calculate_confirm_preview(
    db: Session,
    trade: Trade,
    product: Optional[Product],
    *,
    confirm_date: Optional[date] = None,
    price: Optional[Decimal] = None,
) -> dict:
    """
    计算交易确认结果（纯计算，不落库），供确认前预览与真实确认共用。

    只做查询与计算：**不修改 trade 对象、不同步配对腿、不 flush/commit**。
    confirm_single_trade 调用本函数取结果后回写，保证「预览 == 真实确认」。

    计算规则（与确认语义完全一致）：
    - 场外净值型基金（OEF/LOF 且 CN_OTC）：取 T 日净值重算 shares/amount，
      缺失抛 MISSING_NAV；传入 price 仅作一致性校验（不一致抛 PRICE_NAV_MISMATCH）
    - 非净值型且传入 price：按传入成交价重算（补录/手动覆盖场景）
    - 否则（场内不传价）：不重算，返回 trade 现有字段原样

    Args:
        db: 数据库会话
        trade: 待确认交易（须为 pending）
        product: 交易对应产品（CASH/未知产品可为 None，跳过净值逻辑）
        confirm_date: 覆盖确认日（补录场景）
        price: 手动价格；场外基金仅用于与 T 日净值一致性校验（不覆盖净值），
            场内基金作为覆盖成交价

    Returns:
        {
            "price"/"shares"/"amount"/"actual_amount": 确认后将写入的数值,
            "fee": trade.fee,
            "confirm_date": 生效确认日（传参覆盖或 trade.confirm_date）,
            "nav_date": OTC 净值型时取净值的 T 日（trade.trade_date），否则 None,
            "is_otc_nav_fund": 是否场外净值型基金,
            "paired_cash_amount": 配对 CASH 腿将同步的金额
                （actual_amount 优先，否则 amount，与 sync_transfer_group 镜像规则一致；
                CASH 腿自身为 None）,
        }
    """
    effective_confirm_date = confirm_date if confirm_date is not None else trade.confirm_date

    # 场外净值型基金（CN_OTC 的 OEF/LOF）确认时必须获取 T 日净值进行计算
    is_otc_nav_fund = (
        bool(product)
        and product.product_type in ["OEF", "LOF"]
        and trade.market == "CN_OTC"
    )

    result_price = trade.price
    result_shares = trade.shares
    result_amount = trade.amount
    result_actual_amount = trade.actual_amount

    if is_otc_nav_fund:
        # 净值型产品：获取T日净值
        nav_price = get_nav_for_trade_confirmation(
            db, trade.product_code, trade.market, trade.trade_date
        )

        # 净值不存在，无法确认交易
        if nav_price is None:
            raise BusinessError(
                "MISSING_NAV",
                f"产品{trade.product_code}在T={trade.trade_date}的净值尚未同步，无法确认交易",
            )

        # 手动价格为可选校验项：传入时必须与 T 日净值一致，否则拒绝确认由用户修正；
        # 场外基金一律以 T 日净值计算，手动价不参与计算、也不覆盖净值
        if price is not None:
            input_price = Decimal(str(price)).quantize(Decimal("0.0001"))
            if input_price != nav_price.quantize(Decimal("0.0001")):
                raise BusinessError(
                    "PRICE_NAV_MISMATCH",
                    f"传入价格({input_price})与T={trade.trade_date}净值({nav_price})不一致，请核对后修改，或不传价格直接取净值",
                )

        final_price = nav_price

        result_price = final_price
        if trade.trade_type == "buy":
            amount = Decimal(str(trade.actual_amount)) - Decimal(str(trade.fee))
            result_shares = quantize_shares(amount / final_price)
            result_amount = amount
        else:
            amount = Decimal(str(trade.shares)) * final_price
            result_actual_amount = amount - Decimal(str(trade.fee))
            result_amount = amount
    elif price is not None:
        # 场内基金/其他非净值型：仅在传入价格时按传入成交价重算（补录/手动覆盖场景）
        result_price = Decimal(str(price))
        if trade.trade_type == "buy":
            amount = Decimal(str(trade.actual_amount)) - Decimal(str(trade.fee))
            result_shares = quantize_shares(amount / Decimal(str(price)))
            result_amount = amount
        else:
            amount = Decimal(str(trade.shares)) * Decimal(str(price))
            result_actual_amount = amount - Decimal(str(trade.fee))
            result_amount = amount
    # else：场内不传价 → 不重算，返回 trade 现有字段原样

    # 配对 CASH 腿镜像金额（与 sync_transfer_group 规则一致，仅基金腿有意义）
    paired_cash_amount = None
    if trade.product_code != "CASH":
        paired_cash_amount = (
            result_actual_amount if result_actual_amount is not None else result_amount
        )

    return {
        "price": result_price,
        "shares": result_shares,
        "amount": result_amount,
        "actual_amount": result_actual_amount,
        "fee": trade.fee,
        "confirm_date": effective_confirm_date,
        "nav_date": trade.trade_date if is_otc_nav_fund else None,
        "is_otc_nav_fund": is_otc_nav_fund,
        "paired_cash_amount": paired_cash_amount,
    }


def confirm_single_trade(
    db: Session,
    trade: Trade,
    product: Optional[Product],
    *,
    confirm_date: Optional[date] = None,
    price: Optional[Decimal] = None,
    skip_cash_check: bool = False,
    sync_nav: bool = False,
) -> Trade:
    """
    确认单笔调仓交易的核心逻辑，供手动确认与 auto_confirm 共用。

    - 计算统一委托 calculate_confirm_preview（确认与预览共用同一实现），
      本函数负责将结果回写 trade 并置 confirmed
    - confirm_date 已在创建时设定；若传入参数则覆盖（补录场景）
    - 场外基金（OEF/LOF 且 CN_OTC）确认时统一获取 T 日（成交当日）净值并重算 shares/amount，
      不区分 QDII/非 QDII，一律以净值计算；缺失 T 日净值时抛 MISSING_NAV 拒绝确认
    - sync_nav=True（issue #90，显式选择）：命中 MISSING_NAV 时自动回填该标的历史净值
      后重试一次；同步后仍缺失则照常抛 MISSING_NAV
    - 场外基金若传入 price 仅作一致性校验：须与 T 日净值相等，否则抛 PRICE_NAV_MISMATCH，
      手动价不覆盖净值（不传则直接取净值）
    - 场内基金不取净值，使用创建时录入的成交价（成交价录入时必填，见 trades.py 创建校验）
    - 基金买入确认时按生效确认日口径校验可用现金（加回自身在途 CASH 腿防双重计数），
      不足抛 INSUFFICIENT_CASH；skip_cash_check=True 跳过（auto_confirm 重算历史场景）
    - 置 status=confirmed 并原子同步配对 CASH 腿

    Args:
        db: 数据库会话
        trade: 待确认交易（须为 pending）
        product: 交易对应产品（CASH/未知产品可为 None，跳过净值逻辑）
        confirm_date: 覆盖确认日（补录场景）
        price: 手动价格；场外基金仅用于与 T 日净值一致性校验（不覆盖净值），
            场内基金作为覆盖成交价
        skip_cash_check: 跳过买入确认时的可用现金校验（auto_confirm 专用）
        sync_nav: MISSING_NAV 时自动回填净值并重试一次（显式选择，会访问外部数据源）

    Returns:
        确认后的 trade 对象（未 commit，事务由调用方控制）
    """
    try:
        preview = calculate_confirm_preview(
            db, trade, product, confirm_date=confirm_date, price=price
        )
    except BusinessError as e:
        if not (sync_nav and e.code == "MISSING_NAV"):
            raise
        # issue #90：显式请求时自动回填该标的历史净值后重试一次
        from app.services.market_data_service import sync_price_data

        try:
            sync_price_data(db, trade.product_code, trade.market, None, date.today())
        except Exception as sync_err:
            raise BusinessError(
                "MISSING_NAV",
                f"{e.message}；自动同步净值失败: {sync_err}",
            )
        preview = calculate_confirm_preview(
            db, trade, product, confirm_date=confirm_date, price=price
        )

    # 基金买入确认时校验可用现金（#70/#78：按生效确认日时点口径）
    if (
        not skip_cash_check
        and trade.trade_type == "buy"
        and trade.product_code != "CASH"
    ):
        effective_confirm_date = (
            confirm_date if confirm_date is not None else trade.confirm_date
        )
        # #91：扣款平台 = 配对 CASH sell 腿的平台（跨平台扣款时与基金腿不同），
        # 无配对腿时回退基金腿平台
        cash_check_platform = trade.platform_code
        own_legs = []
        if trade.transfer_group:
            own_legs = db.query(Trade).filter(
                Trade.transfer_group == trade.transfer_group,
                Trade.product_code == "CASH",
                Trade.trade_type == "sell",
                Trade.status == "pending",
            ).all()
            if own_legs:
                cash_check_platform = own_legs[0].platform_code
        available = calculate_available_cash(
            db, trade.portfolio_code, cash_check_platform,
            as_of_date=effective_confirm_date,
        )
        # 加回自身在途 CASH sell 腿：该腿已作为 pending sell 计提预留，
        # 若不加回会与 paired_cash_amount 双重计数导致误拒
        own_leg_amount = Decimal("0")
        for leg in own_legs:
            own_leg_amount += Decimal(str(leg.amount or 0))
        available_excl_own = available + own_leg_amount
        paired = preview["paired_cash_amount"]
        if paired is not None:
            paired_d = Decimal(str(paired))
            if paired_d > available_excl_own:
                raise BusinessError(
                    "INSUFFICIENT_CASH",
                    f"平台 {cash_check_platform} 可用现金不足"
                    f"（需 {paired_d}，可用 {available_excl_own}）",
                    details={
                        "deficit": str(paired_d - available_excl_own),
                        "required": str(paired_d),
                        "available": str(available_excl_own),
                    },
                )

    # confirm_date 已在创建时设定；若传入参数则覆盖（补录场景）
    if confirm_date is not None:
        trade.confirm_date = confirm_date

    # 仅在重算分支回写数值字段（场内不传价时保持 trade 现有字段不动）
    if preview["is_otc_nav_fund"] or price is not None:
        trade.price = preview["price"]
        trade.shares = preview["shares"]
        trade.amount = preview["amount"]
        trade.actual_amount = preview["actual_amount"]

    trade.status = "confirmed"
    # 同步 transfer_group 配对腿（如基金调仓的配对 CASH 腿）
    sync_transfer_group(db, trade, "confirmed", trade.confirm_date)

    logger.info(
        f"交易确认: trade_id={trade.id}, type={trade.trade_type}, "
        f"product={trade.product_code}, confirm_date={trade.confirm_date}"
    )

    return trade


def create_trade(
    db: Session,
    *,
    portfolio_code: str,
    product_code: str,
    market: Optional[str],
    trade_type: str,
    trade_date: date,
    amount: Optional[Decimal] = None,
    actual_amount: Optional[Decimal] = None,
    fee: Optional[Decimal] = None,
    price: Optional[Decimal] = None,
    shares: Optional[Decimal] = None,
    platform_code: Optional[str] = None,
    notes: Optional[str] = None,
    allow_duplicate: bool = False,
    cash_platform_code: Optional[str] = None,
) -> Trade:
    """创建买入/卖出交易（含全部校验与配对 CASH 腿），供 REST 与 CLI 共用。

    买入现金口径统一：cash_out = actual_amount 优先，否则 amount
    （前端传 amount、CLI 传 actual_amount，两者行为一致）。
    自然键防重（#82）：同组合/产品/市场/平台/方向/交易日且金额（买）或份额（卖）
    相同的 pending/confirmed 交易视为重复，抛 DUPLICATE_TRADE；
    allow_duplicate=True 强制放行，cancelled 记录不算重复。
    cash_platform_code（issue #91）：现金腿平台，买=扣款平台、卖=到账平台，
    缺省同基金腿；买入可用现金按扣款平台校验。
    不 commit，事务由调用方控制。返回基金腿 Trade。
    """
    if not is_trading_day(db, trade_date):
        raise BusinessError("NON_TRADING_DAY", "非交易日，请等待交易日再提交")

    portfolio = db.query(Portfolio).filter(Portfolio.code == portfolio_code).first()
    if not portfolio:
        raise NotFoundError("NOT_FOUND", "组合不存在")
    if portfolio.status != "active":
        raise BusinessError("PORTFOLIO_NOT_ACTIVE", "组合未激活")

    # 交易日必须晚于最新快照日
    latest_snapshot_date = get_latest_snapshot_date(db, portfolio_code)
    if latest_snapshot_date and trade_date <= latest_snapshot_date:
        raise BusinessError(
            "DATE_BEFORE_SNAPSHOT",
            f"交易日必须晚于最新快照日（{latest_snapshot_date}）",
        )

    # #83：market 省略时按产品唯一市场自动补全；LOF 一码多市场抛 MARKET_AMBIGUOUS
    product_code, market = resolve_product_market(db, product_code, market)

    product = db.query(Product).filter(
        Product.code == product_code, Product.market == market
    ).first()
    if not product:
        # details 携带 product_code 与同 code 其他市场，供 CLI hints 消费
        details = {"product_code": product_code, "market": market}
        other_markets = sorted(
            row[0] or ""
            for row in db.query(Product.market).filter(Product.code == product_code).all()
        )
        if other_markets:
            details["available_markets"] = other_markets
        raise NotFoundError(
            "NOT_FOUND", f"产品 {product_code}({market}) 不存在", details=details
        )

    # 禁止直接创建裸 CASH 交易：现金变动只能来自申赎/调仓配对/现金转移
    if product_code == "CASH":
        raise BusinessError(
            "CASH_TRADE_FORBIDDEN",
            "不支持直接创建 CASH 交易，请使用现金转移或申购赎回入口",
        )

    # #91：现金腿平台规范化——与基金腿同平台时等价于不传；传入时校验存在
    if cash_platform_code == platform_code:
        cash_platform_code = None
    if cash_platform_code and not db.query(Platform).filter(
        Platform.code == cash_platform_code
    ).first():
        raise NotFoundError(
            "PLATFORM_NOT_FOUND", f"现金平台 {cash_platform_code} 不存在"
        )

    # 场内交易必须提供有效价格（实时撚合价，不能用收盘价替代）
    if product.market == "CN_EXCHANGE" and (price is None or Decimal(str(price)) <= 0):
        raise BusinessError(
            "MISSING_OR_INVALID_PRICE",
            "场内交易必须提供有效的正数交易价格（--price）",
        )

    confirm_days = product.confirm_days or 0
    expected_confirm_date = get_next_trading_day(db, trade_date, days=confirm_days)
    fee_d = Decimal(str(fee)) if fee else Decimal("0")
    price_d = Decimal(str(price)) if price else None

    if trade_type == "buy":
        # 买入现金口径：actual_amount 优先，否则 amount
        cash_out = actual_amount if actual_amount is not None else amount
        if cash_out is None or Decimal(str(cash_out)) <= 0:
            raise BusinessError("INVALID_AMOUNT", "买入金额必须大于0")
        cash_out_d = Decimal(str(cash_out))
        # #91：可用现金按扣款平台校验（缺省同基金腿平台）
        cash_check_platform = cash_platform_code or platform_code
        available_cash = calculate_available_cash(
            db, portfolio_code, cash_check_platform, as_of_date=trade_date
        )
        if cash_out_d > available_cash:
            msg = "买入金额超过可用现金"
            if cash_check_platform:
                msg = f"平台 {cash_check_platform} 的可用现金不足"
            raise BusinessError("INSUFFICIENT_CASH", msg)
        net_amount = cash_out_d - fee_d
        shares_d = quantize_shares(net_amount / price_d) if price_d else Decimal("0")
        actual_amount_final = cash_out_d
        new_trade = Trade(
            portfolio_code=portfolio_code, product_code=product_code, market=market,
            platform_code=platform_code, trade_type="buy",
            shares=shares_d, amount=net_amount, price=price_d, fee=fee_d,
            actual_amount=actual_amount_final, trade_date=trade_date,
            confirm_date=expected_confirm_date, status="pending", notes=notes,
        )
    elif trade_type == "sell":
        if shares is None or Decimal(str(shares)) <= 0:
            raise BusinessError("INVALID_SHARES", "卖出份额必须大于0")
        # 用户输入份额先量化到 2 位（四舍五入），再做精确比较
        shares_d = quantize_shares(Decimal(str(shares)))
        if shares_d <= 0:
            raise BusinessError("INVALID_SHARES", "卖出份额必须大于0")
        available_shares = calculate_available_shares(
            db, portfolio_code, product_code, market, as_of_date=trade_date
        )
        if shares_d > available_shares:
            raise BusinessError("INSUFFICIENT_SHARES", "卖出份额超过可用份额")
        actual_amount_final = Decimal(str(actual_amount)) if actual_amount else Decimal("0")
        net_amount = actual_amount_final + fee_d
        new_trade = Trade(
            portfolio_code=portfolio_code, product_code=product_code, market=market,
            platform_code=platform_code, trade_type="sell",
            shares=shares_d, amount=net_amount, price=price_d, fee=fee_d,
            actual_amount=actual_amount_final, trade_date=trade_date,
            confirm_date=expected_confirm_date, status="pending", notes=notes,
        )
    else:
        raise BusinessError("INVALID_TYPE", "类型必须为 buy 或 sell")

    # 自然键防重（#82）：命中 pending/confirmed 同参数交易且未显式放行时拒绝
    if not allow_duplicate:
        candidates = db.query(Trade).filter(
            Trade.portfolio_code == portfolio_code,
            Trade.product_code == product_code,
            Trade.market == market,
            Trade.platform_code == platform_code,
            Trade.trade_type == trade_type,
            Trade.trade_date == trade_date,
            Trade.status.in_(["pending", "confirmed"]),
        ).all()
        existing = None
        for c in candidates:
            if trade_type == "buy":
                # 买入比对现金支出（actual_amount = cash_out，与落库值同口径）
                if c.actual_amount is not None and Decimal(str(c.actual_amount)) == cash_out_d:
                    existing = c
                    break
            else:
                # 卖出比对量化后份额（与落库值同口径）
                if c.shares is not None and Decimal(str(c.shares)) == shares_d:
                    existing = c
                    break
        if existing:
            raise BusinessError(
                "DUPLICATE_TRADE",
                f"存在相同参数的交易（id={existing.id}），如确为重复操作请检查，"
                f"如需强制创建请传 allow_duplicate",
                details={"existing_trade_id": existing.id},
            )

    # 基金腿必配 CASH 腿（显式记录现金变动；#91 支持跨平台现金腿）
    db.add(new_trade)
    attach_paired_cash_leg(
        db, new_trade, actual_amount_final, expected_confirm_date,
        cash_platform_code=cash_platform_code,
    )
    return new_trade


def cancel_trade(db: Session, trade: Trade) -> Trade:
    """取消交易（仅 pending + 非场内），并同步配对 CASH 腿。不 commit。"""
    if trade.status != "pending":
        raise BusinessError("INVALID_STATUS", "仅 pending 状态可取消")
    if trade.market == "CN_EXCHANGE":
        raise BusinessError(
            "CANNOT_CANCEL_EXCHANGE",
            "场内交易不可取消，请使用 PUT 修改字段或 DELETE 删除后重新创建",
        )
    trade.status = "cancelled"
    sync_transfer_group(db, trade, "cancelled")
    return trade


def unconfirm_trade(db: Session, trade: Trade) -> Trade:
    """取消确认（confirmed -> pending）：快照保护 + 重算 confirm_date + 同步配对腿。不 commit。"""
    from app.models.portfolio_value_snapshot import PortfolioValueSnapshot
    from sqlalchemy import func as _func

    if trade.status != "confirmed":
        raise BusinessError("INVALID_STATUS", "仅 confirmed 状态可取消确认")

    # 快照保护：确认日及之后已有快照则拒绝
    if trade.confirm_date:
        snapshots_after = (
            db.query(_func.count(PortfolioValueSnapshot.id))
            .filter(
                PortfolioValueSnapshot.portfolio_code == trade.portfolio_code,
                PortfolioValueSnapshot.snapshot_date >= trade.confirm_date,
            )
            .scalar()
        )
        if snapshots_after and snapshots_after > 0:
            raise BusinessError(
                "SNAPSHOT_DEPENDENCY",
                f"该交易已被快照纳入（{trade.confirm_date} 及之后有 {snapshots_after} 张快照），"
                f"请先删除 {trade.confirm_date} 及之后的快照",
            )

    trade.status = "pending"
    # 重新计算期望确认日（创建时设定 confirm_date，unconfirm 后需恢复）
    if trade.product_code and trade.market:
        product = db.query(Product).filter(
            Product.code == trade.product_code, Product.market == trade.market
        ).first()
        if product:
            trade.confirm_date = get_next_trading_day(
                db, trade.trade_date, days=product.confirm_days or 0
            )
    sync_transfer_group(db, trade, "pending")
    return trade
