"""FastAPI 应用入口。

M1 阶段仅含健康检查与 CORS；认证、会话、任务、WS、Agent 路由将在 T9 逐步挂载。
容器启动时由 entrypoint 脚本执行 `alembic upgrade head` + 种子，本 lifespan 仅做轻量自检。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO(T9): 启动异步任务队列 worker、Redis 连接池预热、配置热加载订阅
    yield
    # TODO(T9): 优雅关闭 worker、释放连接


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
