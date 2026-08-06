from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  确保模型注册到 Base.metadata
from app.config import settings
from app.database import Base, engine
from app.routers import fund as fund_router
from app.routers import purchase as purchase_router
from app.routers import quarter as quarter_router
from app.routers import quote as quote_router
from app.schemas import ApiResponse, success


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 仅补建缺失的表，不会改动已有表结构（表结构由 schema.sql 管理）
    Base.metadata.create_all(bind=engine)
    yield


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

app.include_router(fund_router.router)
app.include_router(purchase_router.router)
app.include_router(quarter_router.router)
app.include_router(quote_router.router)


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
        reload=True,
    )
