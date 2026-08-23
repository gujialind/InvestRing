# CI E2E 种子入口（issue #222）：替代已退役的 scripts/init_data.py。
# 种子体与 pytest 同源（tests/seed_base.py）：维度字典/适用关系/平台/产品/
# 日历/draft 组合 E2E_PORT/ADMIN(admin@2026)/VIEWER。
#
# 用法（须先设置 DATABASE_URL，指向 CI 的 ir_e2e 库）：
#   DATABASE_URL=mysql+pymysql://... python scripts/seed_e2e.py
import os
import sys
from pathlib import Path

if not os.environ.get("DATABASE_URL"):
    sys.exit("错误：未设置 DATABASE_URL——本脚本会向目标库写入种子数据，"
             "必须显式指定数据库连接，拒绝默认值以防误连。")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from tests.seed_base import seed_base_data  # noqa: E402

db = SessionLocal()
try:
    seed_base_data(db)
    print(f"E2E 种子完成（目标库：{os.environ['DATABASE_URL'].split('@')[-1]}）")
finally:
    db.close()
