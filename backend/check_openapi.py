"""
openapi.json 漂移门禁（issue #170）：进程内生成的 OpenAPI schema 与已提交 backend/openapi.json 比对。

改 router/schema 后必须重新导出 openapi.json，否则本脚本 exit 1：
  1. 启动后端后 cd backend && python export_openapi.py
  2. python ir-cli/scripts/gen_response_fields.py
  3. 提交 backend/openapi.json 与 ir-cli/ir_cli/response_fields.py

使用方式（无需起服务）：
  cd backend && python check_openapi.py

import app.main 会执行 create_all + init_scheduled_tasks（对临时 sqlite，
路径默认落在系统 temp 目录，不污染仓库；SCHEDULER_ENABLED 默认关闭）。
"""
import json
import os
import sys
import tempfile

# 先于 app import 预置环境（外部已显式提供时不覆盖）
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(tempfile.gettempdir(), 'openapi_check.db')}",
)
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from app.main import app  # noqa: E402

OPENAPI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openapi.json")


def normalize(spec: dict) -> str:
    """规范化序列化：key 排序，消除字段顺序差异。"""
    return json.dumps(spec, ensure_ascii=False, sort_keys=True)


def main() -> int:
    with open(OPENAPI_PATH, encoding="utf-8") as f:
        committed = json.load(f)
    generated = app.openapi()

    if normalize(generated) == normalize(committed):
        print("[ok] backend/openapi.json 与后端进程内生成的 schema 一致")
        return 0

    # 输出首批差异点辅助定位
    g_paths = generated.get("paths", {})
    c_paths = committed.get("paths", {})
    diffs = []
    for p in sorted(set(g_paths) - set(c_paths)):
        diffs.append(f"新增 path（openapi.json 缺失）: {p}")
    for p in sorted(set(c_paths) - set(g_paths)):
        diffs.append(f"多余 path（后端已不存在）: {p}")
    for p in sorted(set(g_paths) & set(c_paths)):
        if normalize(g_paths[p]) != normalize(c_paths[p]):
            diffs.append(f"path 定义不一致: {p}")

    print("[error] backend/openapi.json 与后端代码漂移：", file=sys.stderr)
    for d in (diffs[:20] or ["(未检出具体 path 差异，可能为 info/components 字段漂移)"]):
        print(f"  - {d}", file=sys.stderr)
    print(
        "\n请重新导出并提交：\n"
        "  1. 启动后端，然后 cd backend && python export_openapi.py\n"
        "  2. python ir-cli/scripts/gen_response_fields.py\n"
        "  3. 提交 backend/openapi.json 与 ir-cli/ir_cli/response_fields.py",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
