"""FastAPI 应用入口（T9 完整装配）。

- 注册全部路由域：auth / chat / task(+result) / ws / config / datasource / attachment。
- 全局业务异常处理器（BizError → {code,message,detail}）。
- lifespan：注册工具 → 加载 ConfigCache → 启动 OIDC 密钥 + JWKS 绑定 → 启动任务队列
  （注入 agent.engine.run_task）→ 启动 WS 心跳；关闭时优雅停止。
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ConfigCache, settings
from app.core.db import AsyncSessionLocal
from app.core.errors import BizError, biz_error_handler
from app.core.security import jwt_verifier as _jwt
from app.domains.admin.router import router as admin_monitor_router
from app.domains.agent import engine as agent_engine
from app.domains.agent.tools import register_all
from app.domains.attachment.router import router as attachment_router
from app.domains.auth.keys import oidc_keys
from app.domains.auth.router import router as auth_router
from app.domains.auth.users_router import router as auth_users_router
from app.domains.chat.router import router as chat_router
from app.domains.config.router import router as config_router
from app.domains.datasource.router import router as datasource_router
from app.domains.task.queue import task_queue
from app.domains.task.router import router as task_router
from app.domains.task.ws import manager, router as ws_router

# 触发工具注册
register_all()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 工具注册（幂等）
    register_all()
    # 2. 配置热加载
    async with AsyncSessionLocal() as db:
        await ConfigCache().load(db)
    # 3. OIDC 密钥 + JWKS 本地绑定（合并部署，避免 lifespan 阶段 HTTP 拉取）
    await oidc_keys.start()
    _jwt.bind_local(oidc_keys.jwks())
    await _jwt.start()
    # 4. 任务队列（注入引擎入口）
    await task_queue.start(agent_engine.run_task)
    # 5. WS 心跳
    hb = asyncio.create_task(manager.ping_all(30))
    try:
        yield
    finally:
        hb.cancel()
        await task_queue.stop()


app = FastAPI(title=settings.APP_NAME, version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(BizError, biz_error_handler)

# ---- 路由注册 ----
app.include_router(auth_router)
app.include_router(auth_users_router)
app.include_router(chat_router)
app.include_router(task_router)
app.include_router(config_router)
app.include_router(datasource_router)
app.include_router(attachment_router)
app.include_router(admin_monitor_router)
# WS 路由（websocket 端点 /api/ws）
app.include_router(ws_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
