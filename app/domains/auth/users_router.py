"""管理员：用户管理 API（§6 管理后台 · 用户管理）。

- GET    /api/admin/users           列表（分页）
- POST   /api/admin/users           新增用户（初始密码，首登强制改密）
- PUT    /api/admin/users/{id}      更新（角色 / 状态 / 显示名 / 重置密码）
- DELETE /api/admin/users/{id}      删除（禁用认证源 + 软删业务用户）
均需 admin 角色。

首登强制改密：新建/重置密码的用户 `must_change_password=True`，
`get_current_user`(业务依赖) 与前端路由守卫会拦截其业务访问，强制改密后才放行。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_admin
from app.domains.auth import service as auth_svc
from app.models.business import User
from app.schemas.models import (
    AdminGenericOut,
    AdminUserCreate,
    AdminUserListOut,
    AdminUserOut,
    AdminUserUpdate,
)

router = APIRouter(tags=["admin-users"])


@router.get("/api/admin/users", response_model=AdminUserListOut)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await auth_svc.list_users(db, page, page_size)
    return AdminUserListOut(items=[AdminUserOut(**i) for i in items], total=total,
                            page=page, page_size=page_size)


@router.post("/api/admin/users", response_model=AdminUserOut)
async def create_user(
    body: AdminUserCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    u = await auth_svc.create_user(db, body.username, body.display_name, body.role, body.password)
    return AdminUserOut(**u)


@router.put("/api/admin/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: str,
    body: AdminUserUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    u = await auth_svc.update_user(
        db, user_id,
        display_name=body.display_name, role=body.role,
        status=body.status, password=body.password,
    )
    return AdminUserOut(**u)


@router.delete("/api/admin/users/{user_id}", response_model=AdminGenericOut)
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await auth_svc.delete_user(db, user_id, actor_id=admin.external_user_id)
    return AdminGenericOut(status="ok", message="用户已删除/禁用")
