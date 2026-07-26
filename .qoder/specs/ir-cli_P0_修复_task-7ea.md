# ir-cli P0 缺陷修复

## Summary
两处修复均集中在 `ir-cli/ir_cli/client.py`，另附带 `output.py` 一处类型标注。不改变输出协议结构（仍为 `{"ok": false, "error": {code, message, details?}}`），不影响各命令组代码。

## 修复一：全 4xx/5xx 统一提取结构化错误码

重写 `_handle_response` 的错误分支（当前 42-61 行的 if/elif 链）：

- 合并为单一 `if resp.status_code >= 400` 分支，先按状态码取默认码：
  - 401=`AUTH_REQUIRED`、403=`FORBIDDEN`、404=`NOT_FOUND`、409=`CONFLICT`、422=`VALIDATION_ERROR`、其余 5xx=`SERVER_ERROR`、其余 4xx=`HTTP_ERROR`
- 对所有错误响应调用 `_extract_error_code(resp, default_code)`，后端 `detail.error` 存在时优先使用（修复 400/409 丢码问题）
- 401 保留原有提示语"认证失败或 token 已过期，请执行: ir auth login"作为 message 兜底（当后端无 detail.message 时）
- `error()` 调用附带 `details={"http_status": resp.status_code}`，便于 agent 判断

## 修复二：拆分 connect/read 超时

修改 `APIClient.__init__`（当前 23 行）：

```python
timeout = httpx.Timeout(
    connect=float(os.environ.get("IR_CONNECT_TIMEOUT", "5")),
    read=float(os.environ.get("IR_HTTP_TIMEOUT", "300")),
    write=30.0,
    pool=5.0,
)
```

- `IR_HTTP_TIMEOUT` 语义保持向后兼容（仍控制长任务读超时，默认 300）
- 新增 `IR_CONNECT_TIMEOUT`（默认 5 秒），后端不可达时快速失败

## 附带小改动

- `output.py`：`error()` 返回类型标注为 `NoReturn`（它总是 `sys.exit(1)`），消除 client 中 `resp` 可能未绑定的类型误报

## Test Plan

- `python -c "from ir_cli.client import APIClient"` 验证导入无误
- 在后端未启动的情况下执行 `ir auth status` / 带假 `IR_BASE_URL` 执行任一命令，验证约 5 秒内返回 `CONNECTION_ERROR`（而非等待 300 秒）
- 后端运行时，构造一个 400 类业务错误（如对已 confirmed 交易执行 PUT），验证输出的 `error.code` 为后端业务码（如 `CANNOT_MODIFY_CONFIRMED`）而非 `HTTP_ERROR`

## Assumptions

- ir-cli 无现有单元测试套件，采用手动命令验证
- 不在本次改动中引入重试、退出码分层等 P1 项