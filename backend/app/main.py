from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.database import engine, Base, SessionLocal
from app.routers import auth, investors, portfolios, products, platforms, trading_calendar, data_sources, market_data, subscriptions, trades, share_change_events, positions, logs, tasks, notifications, snapshots, cash_transfers, sync_jobs
from app.services.exceptions import BusinessError
from app.init_tasks import init_scheduled_tasks

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    init_scheduled_tasks(db)
finally:
    db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    from alembic.config import Config as AlembicCfg
    from alembic import command as alembic_command

    alembic_ini = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg = AlembicCfg(alembic_ini)
    alembic_command.upgrade(alembic_cfg, "head")

    from app.services.market_data_service import recover_orphan_jobs
    recover_orphan_jobs()

    from app.services.scheduler_service import init_scheduler, shutdown_scheduler
    init_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="InvestRing API",
    description="资产组合管理系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    """统一领域异常映射：保持 detail.{error,message} 契约不变。"""
    detail = {"error": exc.code, "message": exc.message}
    if exc.details:
        detail["details"] = exc.details
    return JSONResponse(status_code=exc.http_status, content={"detail": detail})

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(investors.router, prefix="/api/investors", tags=["投资人管理"])
app.include_router(portfolios.router, prefix="/api/portfolios", tags=["组合管理"])
app.include_router(products.router, prefix="/api/products", tags=["产品管理"])
app.include_router(platforms.router, prefix="/api/platforms", tags=["平台管理"])
app.include_router(trading_calendar.router, prefix="/api/trading-calendar", tags=["交易日历"])
app.include_router(data_sources.router, prefix="/api/system/data-sources", tags=["数据源配置"])
app.include_router(market_data.router, prefix="/api/market-data", tags=["市场数据"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["申购赎回"])
app.include_router(trades.router, prefix="/api/trades", tags=["调仓交易"])
app.include_router(share_change_events.router, prefix="/api/share-change-events", tags=["份额变动事件"])
app.include_router(positions.router, prefix="/api/positions", tags=["持仓管理"])
app.include_router(logs.router, prefix="/api/system/logs", tags=["系统日志"])
app.include_router(tasks.router, prefix="/api/system/tasks", tags=["任务管理"])
app.include_router(notifications.router, prefix="/api/system/notifications", tags=["通知"])
app.include_router(snapshots.router, prefix="/api/v1", tags=["快照管理"])
app.include_router(cash_transfers.router, prefix="/api", tags=["现金转移"])
app.include_router(sync_jobs.router, prefix="/api/sync-jobs", tags=["价格同步任务"])

@app.get("/")
def read_root():
    return {"message": "Welcome to InvestRing API"}

@app.get("/health")
def health_check():
    """健康检查端点，供 Docker 和 CI/CD 使用"""
    return {"status": "healthy"}
