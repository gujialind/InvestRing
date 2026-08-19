# E2E 测试后端启动器：复用 conftest 做法，空 lifespan 跳过 alembic
# （MySQL 专有 SQL 在 SQLite 上报错，故 E2E 用 SQLite 临时库时必须跳过迁移）
# 用法：python backend/scripts/run_e2e_backend.py（监听 127.0.0.1:8000）
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

os.environ.update(
    DATABASE_URL="sqlite:////tmp/ir_e2e.db",
    SECRET_KEY="test-secret-key-e2e",
    SCHEDULER_ENABLED="false",
    DEBUG="true",
)
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


@asynccontextmanager
async def _noop_lifespan(app):
    yield


app.router.lifespan_context = _noop_lifespan

import uvicorn  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
