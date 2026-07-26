"""
CLI 自描述结构生成

通过 click 反射把整个命令树（命令/参数/枚举/错误码/输出协议）导出为紧凑 JSON，
供 AI agent 通过一次 `ir schema` 调用掌握全部指令，替代逐个 --help 探索。

注意：typer 高版本内嵌自带 click（typer._click），不能用 isinstance(cmd, click.Group)
判断，统一用鸭子类型（commands 属性 / param_type_name）。
"""
from typing import Any, Optional

from ir_cli.hints import ERROR_HINTS
from ir_cli.utils import ENUMS

# 输出协议与通用约定（与 output.py / client.py / utils.py 保持一致）
PROTOCOL = {
    "output": '成功 {"ok":true,"data":...,"meta"?:...,"hints"?:[...]}; 失败 {"ok":false,"error":{"code","message","details"?,"hints"?}}',
    "exit_codes": {
        "0": "成功",
        "1": "业务错误（可换参数重试）",
        "2": "认证错误（需 ir auth login）",
        "3": "连接/超时错误（可原样重试或检查服务）",
    },
}

CONVENTIONS = {
    "--json": "create/update 类命令可传完整 JSON 请求体，优先于逐项参数",
    "--fields": "list 类命令按逗号分隔字段名裁剪输出",
    "--all": "list 类命令自动翻页获取全部记录",
    "--full": "list 类命令输出全字段（默认仅摘要字段）",
    "--quiet": "trade/sub 写操作仅输出 {id,status,confirm_date}",
    "env": ["IR_BASE_URL", "IR_TOKEN", "IR_CONNECT_TIMEOUT", "IR_HTTP_TIMEOUT", "IR_RETRY", "IR_DEBUG"],
}

# 端到端业务配方：多步命令序列 + 关键前置条件，补充 error_hints 无法覆盖的流程知识
WORKFLOWS = {
    "操作前侦察": {
        "steps": ["ir portfolio context <code>"],
        "notes": "一次返回组合详情/最新快照日/可用现金/pending 申赎交易；任何写操作前先执行",
    },
    "申购入金": {
        "steps": [
            "ir sub create --portfolio-code X --investor-code I --type subscribe --amount N --apply-date D --platform-code P",
            "ir sub confirm <id>",
            "ir snapshot generate --portfolio-code X --target-date <confirm_date>",
        ],
        "notes": "apply_date 须为交易日且晚于最新快照日；首次申购净值固定 1.0000 并自动激活组合；确认自动生成配对 CASH trade",
    },
    "赎回出金": {
        "steps": [
            "ir sub create --portfolio-code X --investor-code I --type redeem --shares N --apply-date D --platform-code P",
            "ir sub confirm <id>",
            "ir snapshot generate --portfolio-code X --target-date <confirm_date>",
        ],
        "notes": "赎回输入份额（金额=份额×申请日净值）；投资人可用份额由服务端实时校验，超额报 INSUFFICIENT_SHARES",
    },
    "调仓买入/卖出": {
        "steps": [
            "ir position available-cash <code>（买入前）/ ir position available-shares <code> <product>（卖出前）",
            "ir trade create --portfolio-code X --product-code F --type buy|sell --trade-date D --actual-amount N [--price P 场内必填]",
            "ir trade confirm <id>（到 confirm_date 当日执行，场外需 T 日净值已同步）",
            "ir snapshot generate --portfolio-code X --target-date <confirm_date>",
        ],
        "notes": "创建时自动生成配对 CASH 腿；pending 卖出不增加可用现金，先卖后买须两步；场内 confirm_days=0、场外非 QDII T+1、QDII T+2",
    },
    "补录历史交易": {
        "steps": [
            "ir snapshot delete-bulk <code> <最早影响日> --yes（若历史日已有快照）",
            "ir trade create --trade-date <历史日> ... 或 ir sub create ...",
            "ir trade confirm <id> --confirm-date <实际确认日>",
            "ir snapshot recalculate --start-date <删除起始日> --end-date <今日> --portfolio-code <code>",
        ],
        "notes": "快照只能从尾部删除（连续原则）；recalculate 逐交易日重建并自动重确认当日记录",
    },
    "快照回退重算": {
        "steps": [
            "ir snapshot status <code>（确认当前快照范围）",
            "ir snapshot delete-bulk <code> <from_date> --yes",
            "修改/补录相关记录",
            "ir snapshot recalculate --start-date <from_date> --end-date <最新交易日> --portfolio-code <code>",
        ],
        "notes": "删除自动级联回退：当日确认的申购/事件退回 pending；不可只删中间某日快照",
    },
    "跨平台现金转移": {
        "steps": [
            "ir cash-transfer create --portfolio-code X --from P1 --to P2 --amount N --date D [--cross-day]",
            "ir cash-transfer confirm <transfer_group> --portfolio-code X（仅跨天：到账日执行）",
            "ir snapshot generate ...",
        ],
        "notes": "当天到账两腿立即 confirmed；跨天两腿均 pending，在途期间不计入任何平台可用现金",
    },
    "份额变动事件": {
        "steps": [
            "ir share-event create --event-type <type> --entitlement-date D1 --ex-date D2 ...",
            "确保 entitlement_date 当日快照已存在",
            "ir share-event confirm <id>",
            "ir snapshot generate --target-date <ex_date>",
        ],
        "notes": "ex_date > entitlement_date 且均为交易日；基金级事件（拆分/合并/送股）不传 platform_code，平台级（分红等）必传",
    },
}


def _param_entry(param: Any) -> Optional[dict]:
    """单个参数 → 紧凑 dict；--help 等内置参数返回 None"""
    if param.name in ("help",):
        return None
    if param.param_type_name == "option":
        # 取最长的选项名（如 --portfolio-code）
        opt = max(param.opts, key=len)
        entry = {"opt": opt, "type": param.type.name.upper()}
        if getattr(param, "is_flag", False):
            entry["type"] = "FLAG"
        if param.required:
            entry["required"] = True
        default = param.default
        # 用身份判断避免 0 == False 被误过滤（如 --fee 默认 0）
        if default is not None and default is not False and not callable(default):
            entry["default"] = default
        help_text = getattr(param, "help", None)
        if help_text:
            entry["help"] = help_text
    else:  # argument
        entry = {"arg": param.name, "type": param.type.name.upper()}
        if param.required:
            entry["required"] = True
    return entry


def _command_entry(cmd: Any) -> dict:
    """单个命令 → {"help", "params"}"""
    entry: dict = {}
    if cmd.help:
        # 只取 docstring 首段，保持紧凑
        entry["help"] = cmd.help.strip().split("\n\n")[0].replace("\n", " ")
    params = [e for p in cmd.params if (e := _param_entry(p))]
    if params:
        entry["params"] = params
    return entry


def is_group(cmd: Any) -> bool:
    """命令组判断（兼容 typer 内嵌 click）"""
    return hasattr(cmd, "commands")


def build_schema(root: Any, group_name: Optional[str] = None) -> dict:
    """
    构建 CLI 自描述结构。

    Args:
        root: typer.main.get_command(app) 得到的顶层命令组
        group_name: 仅输出指定命令组；None 输出全量（含协议/枚举/hints）

    Raises:
        KeyError: group_name 不存在（由调用方转 VALIDATION_ERROR）
    """
    groups = {
        name: cmd for name, cmd in root.commands.items()
        if is_group(cmd)
    }
    if group_name is not None:
        if group_name not in groups:
            raise KeyError(group_name)
        target = groups[group_name]
        return {
            "commands": {
                group_name: {sub: _command_entry(c) for sub, c in target.commands.items()}
            }
        }
    commands = {
        name: {sub: _command_entry(c) for sub, c in grp.commands.items()}
        for name, grp in groups.items()
    }
    return {
        "protocol": PROTOCOL,
        "conventions": CONVENTIONS,
        "enums": {k: list(v) for k, v in ENUMS.items()},
        "error_hints": ERROR_HINTS,
        "workflows": WORKFLOWS,
        "commands": commands,
    }
