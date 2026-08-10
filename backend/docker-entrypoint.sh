#!/bin/sh
# ============================================================================
# 后端容器启动入口：迁移串行化（issue #104）
# ============================================================================
# uvicorn --workers 2 下若在每个 worker 的 lifespan 中各自执行 alembic upgrade，
# 两个 worker 会并发更新 alembic_version 产生竞态（Deploy #138 故障根因）。
# 改为在 worker 启动前由 entrypoint 一次性执行迁移，天然串行。
#
# 命令分流：仅当启动命令是 uvicorn（应用启动）时才先执行迁移，其余命令
# 原样透传——deploy.yml 回滚前置探测 `docker run ... python -m alembic current`
# 绝不能先触发 upgrade，否则旧镜像探测会对生产库执行迁移并自证失败。
# ============================================================================
set -e

case "$*" in
  *uvicorn*)
    echo "[entrypoint] Running alembic upgrade head ..."
    python -m alembic upgrade head
    echo "[entrypoint] Migrations applied, starting app ..."
    ;;
esac

exec "$@"
