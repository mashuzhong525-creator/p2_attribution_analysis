"""数据源管理 API（§6 管理后台）。

- GET    /api/admin/datasources         列表
- POST   /api/admin/datasources         新建（密码 AES 加密存储）
- PUT    /api/admin/datasources/{id}    更新（密码可选，传则重加密）
- DELETE /api/admin/datasources/{id}    删除
- POST   /api/admin/datasources/test    测试连接（按 id 或直连参数）
均需 admin 角色。
"""
from __future__ import annotations

import time

import asyncmy
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ConfigCache
from app.core.db import get_db
from app.core.deps import require_admin
from app.core.errors import data_source_unavailable, not_found, validation_error
from app.core.logging import get_logger
from app.core.security import decrypt_secret, encrypt_secret
from app.core.uuid import uuid7_str
from app.models.business import DataSource, User
from app.schemas.models import DataSourceCreate, DataSourceOut, DataSourceUpdate, TestDsOut

logger = get_logger("datasource")
router = APIRouter(tags=["admin-datasource"])


class TestDsIn(BaseModel):
    id: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None


def _out(ds: DataSource) -> DataSourceOut:
    return DataSourceOut(
        id=ds.id, name=ds.name, db_type=ds.db_type, host=ds.host, port=ds.port,
        database=ds.database, username=ds.username, is_readonly=ds.is_readonly,
        is_enabled=ds.is_enabled,
    )


@router.get("/api/admin/datasources", response_model=list[DataSourceOut])
async def list_ds(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(DataSource).order_by(DataSource.name))).scalars().all()
    return [_out(r) for r in rows]


@router.post("/api/admin/datasources", response_model=DataSourceOut)
async def create_ds(body: DataSourceCreate, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    ds = DataSource(
        id=uuid7_str(), name=body.name, db_type=body.db_type, host=body.host, port=body.port,
        database=body.database, username=body.username,
        password_encrypted=encrypt_secret(body.password),
        is_readonly=body.is_readonly, is_enabled=body.is_enabled,
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return _out(ds)


@router.put("/api/admin/datasources/{ds_id}", response_model=DataSourceOut)
async def update_ds(ds_id: str, body: DataSourceUpdate, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    ds = (await db.get(DataSource, ds_id))
    if ds is None:
        raise not_found("数据源")
    for f in ("name", "db_type", "host", "port", "database", "username", "is_readonly", "is_enabled"):
        v = getattr(body, f)
        if v is not None:
            setattr(ds, f, v)
    if body.password is not None:
        ds.password_encrypted = encrypt_secret(body.password)
    await db.commit()
    await db.refresh(ds)
    return _out(ds)


@router.delete("/api/admin/datasources/{ds_id}")
async def delete_ds(ds_id: str, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    ds = (await db.get(DataSource, ds_id))
    if ds is None:
        raise not_found("数据源")
    await db.delete(ds)
    await db.commit()
    return {"status": "ok", "message": "已删除"}


async def _test_connect(host, port, database, username, password) -> tuple[bool, str, int | None]:
    t0 = time.time()
    try:
        conn = await asyncmy.connect(host=host, port=port, user=username, password=password,
                                     database=database, charset="utf8mb4")
        try:
            cur = conn.cursor()
            await cur.execute("SELECT 1")
            await cur.fetchone()
            return True, "连接成功", int((time.time() - t0) * 1000)
        finally:
            await conn.close()
    except Exception as e:  # noqa: BLE001
        return False, f"连接失败：{e}", None


@router.post("/api/admin/datasources/test", response_model=TestDsOut)
async def test_ds(body: TestDsIn, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if body.id:
        ds = (await db.get(DataSource, body.id))
        if ds is None:
            raise not_found("数据源")
        ok, msg, lat = await _test_connect(ds.host, ds.port, ds.database, ds.username,
                                           decrypt_secret(ds.password_encrypted))
        return TestDsOut(ok=ok, message=msg, latency_ms=lat)
    if not all([body.host, body.database, body.username, body.password is not None]):
        raise validation_error("缺少连接参数")
    ok, msg, lat = await _test_connect(body.host, body.port or 3306, body.database,
                                       body.username, body.password)
    return TestDsOut(ok=ok, message=msg, latency_ms=lat)
