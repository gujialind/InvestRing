"""
导出 OpenAPI 规范 JSON 文件，用于导入 Apifox 等工具。

使用方式（后端运行时）：
  python export_openapi.py

或直接通过 curl（后端运行时）：
  curl http://localhost:8000/openapi.json -o openapi.json
"""
import json
import sys
import requests

DEFAULT_URL = "http://localhost:8000/openapi.json"
OUTPUT_FILE = "openapi.json"

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    output = sys.argv[2] if len(sys.argv) > 2 else OUTPUT_FILE

    print(f"正在从 {url} 获取 OpenAPI 规范...")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.ConnectionError:
        print("错误：无法连接后端服务。请先启动后端，或使用 --offline 模式。")
        print("  启动后端: cd backend && uvicorn app.main:app --reload")
        print("  然后重新运行此脚本。")
        sys.exit(1)

    spec = resp.json()
    with open(output, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    paths_count = len(spec.get("paths", {}))
    print(f"成功导出 {paths_count} 个接口路径到 {output}")
    print(f"\n导入 Apifox 步骤：")
    print(f"  1. 打开 Apifox → 项目设置 → 导入数据")
    print(f"  2. 选择 'OpenAPI/Swagger' 格式")
    print(f"  3. 上传 {output} 文件")
    print(f"  4. 选择导入模式（普通导入/自动合并）")
    print(f"  5. 确认导入")

if __name__ == "__main__":
    main()
