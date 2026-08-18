"""系统配置管理 API（§6 管理后台）。

- GET  /api/admin/config        列出全部配置（按 group 分组）
- POST /api/admin/config        批量更新配置值（自动推断类型并持久化）
- POST /api/admin/reload        触发 ConfigCache 热重载
均需 admin 角色（require_admin）。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ConfigCache
from app.core.db import get_db
from app.core.deps import require_admin
from app.core.errors import config_reload_failed, not_found
from app.core.logging import get_logger
from app.core.uuid import uuid7_str
from app.models.business import SystemConfig, User
from app.schemas.models import (
    ConfigGroupOut,
    ConfigItemIn,
    ConfigItemOut,
    ConfigUpdateIn,
    ReloadOut,
)

logger = get_logger("config")
router = APIRouter(tags=["admin-config"])


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, (dict, list)):
        return "json"
    return "string"


def _to_storage(config_type: str, value: Any) -> str:
    if config_type == "json":
        return json.dumps(value, ensure_ascii=False)
    if config_type == "bool":
        return "true" if value else "false"
    return str(value)


@router.get("/api/admin/config", response_model=list[ConfigGroupOut])
async def list_config(
    group: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SystemConfig)
    if group:
        stmt = stmt.where(SystemConfig.config_group == group)
    rows = (await db.execute(stmt.order_by(SystemConfig.config_group, SystemConfig.config_key))).scalars().all()
    by_group: dict[str, list[ConfigItemOut]] = {}
    for r in rows:
        by_group.setdefault(r.config_group, []).append(ConfigItemOut(
            config_key=r.config_key, config_value=r.config_value,
            config_type=r.config_type, description=r.description,
        ))
    return [ConfigGroupOut(group=g, items=items) for g, items in by_group.items()]


@router.post("/api/admin/config", response_model=ReloadOut)
async def update_config(
    body: ConfigUpdateIn,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        for item in body.items:
            existing = (await db.execute(
                select(SystemConfig).where(SystemConfig.config_key == item.config_key)
            )).scalar_one_or_none()
            ctype = existing.config_type if existing else _infer_type(item.config_value)
            stored = _to_storage(ctype, item.config_value)
            if existing:
                existing.config_value = stored
                existing.config_type = ctype
            else:
                db.add(SystemConfig(
                    id=uuid7_str(), config_key=item.config_key, config_value=stored,
                    config_type=ctype, config_group="general",
                ))
        await db.commit()
        updated = await ConfigCache().reload(db)
        return ReloadOut(status="ok", message="配置已更新并热加载", updated_keys=updated["updated_keys"])
    except Exception as e:  # noqa: BLE001
        raise config_reload_failed(str(e))


@router.post("/api/admin/reload", response_model=ReloadOut)
async def reload_config(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        updated = await ConfigCache().reload(db)
        return ReloadOut(status="ok", message="配置已热加载", updated_keys=updated["updated_keys"])
    except Exception as e:  # noqa: BLE001
        raise config_reload_failed(str(e))
