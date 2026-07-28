"""调仓交易管理命令组"""
import sys
import typer
from typing import Optional
from ir_cli.client import APIClient
from ir_cli.output import error, success
from ir_cli.utils import SUMMARY_FIELDS, build_body, project_fields, resolve_body, run_list

app = typer.Typer(no_args_is_help=True)

# --quiet 时写操作仅输出的关键字段
QUIET_FIELDS = "id,status,confirm_date"
# 确认后提醒：快照未生成前不计入持仓
SNAPSHOT_HINT = "确认后需生成确认日快照才计入持仓: ir snapshot generate --portfolio-code <code> --target-date <confirm_date>"


@app.command("list")
def list_trades(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码"),
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页大小"),
    all_pages: bool = typer.Option(False, "--all", help="自动翻页获取全部记录"),
    fields: Optional[str] = typer.Option(None, "--fields", help="仅输出指定字段(逗号分隔)"),
    full: bool = typer.Option(False, "--full", help="输出全字段（默认仅摘要字段）"),
):
    """获取交易列表（默认输出摘要字段，--full 全字段）"""
    client = APIClient.from_config()
    params = build_body(portfolio_code=portfolio_code)
    run_list(
        client, "/api/trades", params,
        page=page, page_size=page_size, all_pages=all_pages,
        fields=fields, default_fields=SUMMARY_FIELDS["trade"], full=full,
    )


@app.command("create")
def create(
    portfolio_code: Optional[str] = typer.Option(None, "--portfolio-code", help="组合代码(必填)"),
    product_code: Optional[str] = typer.Option(None, "--product-code", help="产品代码(必填)"),
    trade_type: Optional[str] = typer.Option(None, "--type", help="类型(buy/sell)(必填)"),
    trade_date: Optional[str] = typer.Option(None, "--trade-date", help="交易日期(YYYY-MM-DD)(必填)"),
    actual_amount: Optional[float] = typer.Option(None, "--actual-amount", help="实际金额"),
    fee: float = typer.Option(0, "--fee", help="手续费"),
    platform_code: Optional[str] = typer.Option(None, "--platform-code", help="平台代码"),
    market: Optional[str] = typer.Option(None, "--market", help="市场类型"),
    price: Optional[float] = typer.Option(None, "--price", help="价格"),
    shares: Optional[float] = typer.Option(None, "--shares", help="份额"),
    amount: Optional[float] = typer.Option(None, "--amount", help="金额"),
    notes: Optional[str] = typer.Option(None, "--notes", help="备注"),
    json_body: Optional[str] = typer.Option(None, "--json", help="完整 JSON 请求体，优先于逐项参数"),
    auto_confirm: bool = typer.Option(False, "--confirm", help="创建成功后立即确认（快捷组合）"),
    quiet: bool = typer.Option(False, "--quiet", help="仅输出 id/status/confirm_date"),
):
    """创建交易（--confirm 可链式创建+确认）"""
    client = APIClient.from_config()
    body = resolve_body(
        json_body,
        required=("portfolio_code", "product_code", "trade_type", "trade_date"),
        portfolio_code=portfolio_code,
        product_code=product_code,
        trade_type=trade_type,
        trade_date=trade_date,
        actual_amount=actual_amount,
        fee=fee,
        platform_code=platform_code,
        market=market,
        price=price,
        shares=shares,
        amount=amount,
        notes=notes,
    )
    result = client.post("/api/trades", json_data=body)
    created = result["data"]
    if auto_confirm and isinstance(created, dict) and created.get("id"):
        # 确认失败时 stdout 为确认阶段的错误 JSON，stderr 保留已创建的 id 便于后续处理
        print(f"[info] 交易已创建 id={created['id']}，正在确认...", file=sys.stderr)
        result = client.post(f"/api/trades/{created['id']}/confirm")
    data = result["data"]
    hints = None
    if isinstance(data, dict):
        if data.get("status") == "pending":
            hints = [f"ir trade confirm {data.get('id')}"]
        elif data.get("status") == "confirmed":
            hints = [SNAPSHOT_HINT]
    success(data=project_fields(data, QUIET_FIELDS) if quiet else data, hints=hints)


@app.command("get")
def get(id: int = typer.Argument(..., help="交易ID")):
    """获取交易详情"""
    client = APIClient.from_config()
    result = client.get(f"/api/trades/{id}")
    success(data=result["data"])


@app.command("preview")
def preview(
    id: int = typer.Argument(..., help="交易ID"),
    confirm_date: Optional[str] = typer.Option(None, "--confirm-date", help="确认日期(YYYY-MM-DD)"),
    price: Optional[float] = typer.Option(None, "--price", help="确认价格"),
    quiet: bool = typer.Option(False, "--quiet", help="仅输出 preview/paired_cash_amount"),
):
    """确认前预览：返回真实确认将写入的净值/份额/金额，不落库。

    需要后端支持 GET /api/trades/{id}/preview（issue #65 后的版本）。
    仅 pending 状态可预览；场外基金 T 日净值缺失时返回 MISSING_NAV。
    """
    client = APIClient.from_config()
    params = {}
    if confirm_date is not None:
        params["confirm_date"] = confirm_date
    if price is not None:
        params["price"] = price
    result = client.get(f"/api/trades/{id}/preview", params=params)
    data = result["data"]
    hints = [
        "预览为时点快照，实际以确认时为准",
        f"核对无误后执行: ir trade confirm {id}",
    ]
    # data 为嵌套结构 {trade, preview, paired_cash_amount}，--quiet 时裁掉冗长的 trade 全字段
    success(
        data=project_fields(data, "preview,paired_cash_amount") if quiet else data,
        hints=hints,
    )


@app.command("confirm")
def confirm(
    id: int = typer.Argument(..., help="交易ID"),
    confirm_date: Optional[str] = typer.Option(None, "--confirm-date", help="确认日期(YYYY-MM-DD)"),
    price: Optional[float] = typer.Option(None, "--price", help="确认价格"),
    quiet: bool = typer.Option(False, "--quiet", help="仅输出 id/status/confirm_date"),
):
    """确认交易"""
    client = APIClient.from_config()
    params = {}
    if confirm_date is not None:
        params["confirm_date"] = confirm_date
    if price is not None:
        params["price"] = price
    result = client.post(f"/api/trades/{id}/confirm", params=params)
    data = result["data"]
    success(data=project_fields(data, QUIET_FIELDS) if quiet else data, hints=[SNAPSHOT_HINT])


@app.command("cancel")
def cancel(
    id: int = typer.Argument(..., help="交易ID"),
    quiet: bool = typer.Option(False, "--quiet", help="仅输出 id/status/confirm_date"),
):
    """取消交易。

    约束：仅场外（CN_OTC）pending 状态交易可取消；场内交易当天确认，不可取消。
    配对 CASH 腿会自动同步为 cancelled。
    """
    client = APIClient.from_config()
    result = client.post(f"/api/trades/{id}/cancel")
    data = result["data"]
    success(data=project_fields(data, QUIET_FIELDS) if quiet else data)


@app.command("unconfirm")
def unconfirm(
    id: int = typer.Argument(..., help="交易ID"),
    quiet: bool = typer.Option(False, "--quiet", help="仅输出 id/status/confirm_date"),
):
    """取消确认交易。

    约束：仅 confirmed 状态可取消确认；若 confirm_date 及之后已有快照，
    返回 SNAPSHOT_DEPENDENCY，需先删除对应快照。配对 CASH 腿会自动同步回 pending。
    """
    client = APIClient.from_config()
    result = client.post(f"/api/trades/{id}/unconfirm")
    data = result["data"]
    success(data=project_fields(data, QUIET_FIELDS) if quiet else data)


@app.command("update")
def update(
    id: int = typer.Argument(..., help="交易ID"),
    shares: Optional[float] = typer.Option(None, "--shares", help="份额"),
    amount: Optional[float] = typer.Option(None, "--amount", help="金额"),
    price: Optional[float] = typer.Option(None, "--price", help="价格"),
    fee: Optional[float] = typer.Option(None, "--fee", help="手续费"),
    actual_amount: Optional[float] = typer.Option(None, "--actual-amount", help="实际金额"),
    trade_date: Optional[str] = typer.Option(None, "--trade-date", help="交易日期(YYYY-MM-DD)"),
    notes: Optional[str] = typer.Option(None, "--notes", help="备注"),
    json_body: Optional[str] = typer.Option(None, "--json", help="完整 JSON 请求体，优先于逐项参数"),
):
    """更新交易（仅 pending 状态可改，confirmed 需先 unconfirm）。

    改动 trade_date/status 会自动同步配对 CASH 腿；confirm_date 不开放直改，
    改 trade_date 时后端自动联动重算，补录覆盖请用 confirm --confirm-date。
    """
    client = APIClient.from_config()
    body = resolve_body(
        json_body,
        shares=shares,
        amount=amount,
        price=price,
        fee=fee,
        actual_amount=actual_amount,
        trade_date=trade_date,
        notes=notes,
    )
    if not body:
        error("VALIDATION_ERROR", "未提供任何更新字段")
    result = client.put(f"/api/trades/{id}", json_data=body)
    success(data=result["data"])


@app.command("delete")
def delete(id: int = typer.Argument(..., help="交易ID")):
    """删除交易（仅 pending 状态可删，confirmed 需先 unconfirm）。

    删除主腿会级联删除同一 transfer_group 的配对 CASH 腿。
    """
    client = APIClient.from_config()
    result = client.delete(f"/api/trades/{id}")
    success(data=result["data"])
