"""异步数据库引擎与会话工厂（SQLAlchemy 2.0 异步，asyncmy 驱动）。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base

engine = create_async_engine(
    settings.ASYNC_DB_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.APP_ENV == "dev",
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# task/service、queue、router 等已按 `SessionLocal` 命名引用；保留别名以兼容。
SessionLocal = AsyncSessionLocal


async def get_db() -> AsyncSession:
    """FastAPI 依赖：提供请求级异步会话。"""
    async with AsyncSessionLocal() as session:
        yield session


__all__ = ["engine", "AsyncSessionLocal", "SessionLocal", "get_db", "Base"]
