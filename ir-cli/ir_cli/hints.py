"""
错误码 → 补救指引映射

后端业务错误码是稳定契约（见 AGENTS.md 附录 D），此表将常见错误码映射为
下一步可直接执行的 ir 命令或操作指引，随错误 JSON 一并输出（error.hints），
帮助 AI agent 一次失败即收敛到正确路径，无需反复试错。
"""

ERROR_HINTS: dict = {
    "DATE_BEFORE_SNAPSHOT": "日期须晚于最新快照日，用 ir snapshot status <portfolio_code> 查询最新快照日",
    "SNAPSHOT_DEPENDENCY": "记录已被快照纳入，先删除确认日及之后快照: ir snapshot delete-bulk <portfolio_code> <date> --yes，操作完成后需重新生成/重算快照",
    "SNAPSHOT_NOT_CONTINUOUS": "目标日须为最新快照日或其下一交易日，用 ir snapshot status <portfolio_code> 查询后按交易日顺序逐日生成",
    "NAV_NOT_AVAILABLE": "申请日组合净值快照缺失: ir snapshot status <portfolio_code> 查询最新快照日后，用 ir snapshot generate 按交易日顺序逐日生成至申请日",
    "NON_TRADING_DAY": "仅交易日可操作: ir system calendar 查询交易日历",
    "INSUFFICIENT_CASH": "ir position available-cash <portfolio_code> 查询实时可用现金；pending 卖出不增加可用现金，须先卖出确认后再买入",
    "INSUFFICIENT_SHARES": "ir position available-shares <portfolio_code> <product_code> 查询实时可用份额",
    "CANNOT_MODIFY_CONFIRMED": "confirmed 记录不可直接修改，先执行 unconfirm 回退至 pending",
    "CANNOT_DELETE_CONFIRMED": "confirmed 记录不可直接删除，先执行 unconfirm 回退至 pending",
    "PENDING_TRANSACTIONS_EXIST": "存在 pending 申赎/交易，先逐笔 confirm 或 cancel 后重试",
    "CASH_TRADE_FORBIDDEN": "禁止直接创建 CASH 交易，现金变动须走 ir sub（申赎）/ ir cash-transfer（跨平台转移）/ 基金调仓自动配对",
    "PRICE_NAV_MISMATCH": "传入价格与 T 日净值不一致: ir market price 查询净值核对，或省略 --price 由后端取 T 日净值",
    "MISSING_NAV": "T 日净值尚未同步: ir market sync <product_code> <market> 同步后重试，或 ir market price 查询净值确认覆盖",
    "MISSING_OR_INVALID_PRICE": "场内交易必须传入有效 --price（成交价）",
    "CANNOT_CANCEL_EXCHANGE": "场内交易当天确认、不可 cancel；已确认的用 unconfirm 回退",
    "TRANSFER_NOT_READY": "转移未到确认日，到 confirm_date 当日再执行 ir cash-transfer confirm",
    "MISSING_POSITION_SNAPSHOT": "权益登记日持仓快照缺失，先生成该日快照: ir snapshot generate",
    "PLATFORM_NOT_COVERED": "平台级事件未覆盖全部有持仓平台，补录其余平台事件，或传 --force-cover 降级为 warning",
    "CANNOT_UNCONFIRM_CHILD": "基金级事件的子记录不可单独 unconfirm，请对父事件执行 unconfirm",
    "AUTH_REQUIRED": "执行 ir auth login 登录后重试",
}
