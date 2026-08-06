from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  确保模型注册到 Base.metadata
from app.config import settings
from app.database import Base, engine
from app.logger import LOG_DIR, logger
from app.routers import cash as cash_router
from app.routers import fund as fund_router
from app.routers import holding as holding_router
from app.routers import price as price_router
from app.routers import purchase as purchase_router
from app.routers import quarter as quarter_router
from app.routers import quote as quote_router
from app.routers import sync as sync_router
from app.routers import xirr as xirr_router
from app.schemas import ApiResponse, success
from app.services import sync as sync_service

_scheduler: BackgroundScheduler | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 仅补建缺失的表，不会改动已有表结构（表结构由 schema.sql 管理）
    Base.metadata.create_all(bind=engine)
    logger.info(f"数据库表检查完成（日志目录：{LOG_DIR}）")

    # 定时同步行情：工作日收盘后（默认 17:30，可 .env 调整）
    global _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(
        sync_service.run_scheduled_sync,
        CronTrigger(
            day_of_week="mon-fri",
            hour=settings.SYNC_HOUR,
            minute=settings.SYNC_MINUTE,
        ),
        id="daily_sync",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info(
        f"定时同步已启动：工作日 {settings.SYNC_HOUR}:{settings.SYNC_MINUTE:02d}（Asia/Shanghai）"
    )
    yield
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)


app = FastAPI(
    title="基金定投记录 API",
    description="记录每季度指数基金定投信息，提供基金与购买记录的 CRUD 及汇总统计。",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS：开发期默认放开全部来源；可在 .env 的 CORS_ORIGINS 用逗号分隔指定
if settings.CORS_ORIGINS.strip() == "*":
    origins = ["*"]
else:
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cash_router.router)
app.include_router(fund_router.router)
app.include_router(holding_router.router)
app.include_router(price_router.router)
app.include_router(purchase_router.router)
app.include_router(quarter_router.router)
app.include_router(quote_router.router)
app.include_router(sync_router.router)
app.include_router(xirr_router.router)


@app.get("/", response_model=ApiResponse)
def health() -> ApiResponse:
    return success(message="基金定投 API 运行中")


if __name__ == "__main__":
    # 直接运行：python -m app.main
    # 端口/主机在 config.py 的 HTTP_HOST/HTTP_PORT 配置，可用 .env 覆盖
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HTTP_HOST,
        port=settings.HTTP_PORT,
        reload=settings.HTTP_RELOAD,
    )
