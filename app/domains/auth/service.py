"""OIDC 认证中心业务逻辑（§5 授权码模式，合并进 backend）。

- authenticate：校验 auth_users 凭证。
- issue_auth_code：登录成功后发放一次性授权码（10 分钟有效期）。
- exchange_code：授权码换 RS256 access_token（写 HttpOnly Cookie）+ refresh_token。
- refresh_token：刷新 access_token。
- userinfo：由 claims 返回用户画像。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.db import AsyncSessionLocal
from app.core.errors import auth_expired, forbidden, not_found, validation_error
from app.core.security import gen_token, verify_password
from app.core.uuid import uuid7_str
from app.domains.auth.keys import oidc_keys
from app.models.auth import AuthAuthCode, AuthClient, AuthRefreshToken, AuthUser
from app.models.business import User

_ALLOWED_ROLES = ("admin", "analyst", "viewer")
_ALLOWED_STATUS = ("active", "disabled")


def _now() -> datetime:
    """MySQL DATETIME 列读出为 naive，统一用 naive UTC 比较/写入。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def authenticate(username: str, password: str) -> AuthUser | None:
    async with AsyncSessionLocal() as db:
        u = (await db.execute(
            select(AuthUser).where(AuthUser.username == username)
        )).scalar_one_or_none()
        if u and u.status == "active" and verify_password(password, u.password_hash):
            return u
    return None


async def change_password(user_id: str, old_password: str, new_password: str) -> None:
    """修改密码：校验原密码 → 更新哈希并清除“首次登录需改密”标记 → 吊销既有 refresh_token。"""
    if len(new_password) < 8:
        raise validation_error("新密码长度至少 8 位")
    if new_password == old_password:
        raise validation_error("新密码不能与原密码相同")
    async with AsyncSessionLocal() as db:
        u = (await db.get(AuthUser, user_id))
        if u is None:
            raise not_found("用户")
        if not verify_password(old_password, u.password_hash):
            raise forbidden("原密码错误")
        from app.core.security import hash_password

        u.password_hash = hash_password(new_password)
        u.must_change_password = False
        # 密码已变更：旧 refresh_token 全部失效
        await db.execute(
            update(AuthRefreshToken)
            .where(AuthRefreshToken.user_id == user_id, AuthRefreshToken.revoked_at.is_(None))
            .values(revoked_at=_now())
        )
        await db.commit()


# ---------------------------------------------------------------------------
# 管理员：用户管理（新增用户 / 控制权限 / 首登强制改密）
# ---------------------------------------------------------------------------
async def list_users(db, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    """列出全部用户（含认证源状态与首登标记）。"""
    from sqlalchemy import func as _func
    from sqlalchemy import select as _sel

    total = (await db.execute(_sel(_func.count(AuthUser.id)))).scalar_one()
    rows = (
        await db.execute(
            _sel(AuthUser).order_by(AuthUser.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    items = []
    for a in rows:
        biz = (await db.execute(_sel(User).where(User.external_user_id == a.id))).scalar_one_or_none()
        items.append({
            "id": a.id,
            "username": a.username,
            "display_name": biz.display_name if biz else a.display_name,
            "role": a.role,
            "status": a.status,
            "must_change_password": bool(a.must_change_password),
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return items, int(total)


async def create_user(db, username: str, display_name: str, role: str, password: str) -> dict:
    """管理员新增用户：写 auth_users + 业务 users，并强制首登改密。"""
    from sqlalchemy import select as _sel

    from app.core.security import hash_password as _hash

    if len(password) < 8:
        raise validation_error("密码长度至少 8 位")
    if role not in _ALLOWED_ROLES:
        raise validation_error("角色必须是 admin / analyst / viewer")
    if (await db.execute(_sel(AuthUser).where(AuthUser.username == username))).scalar_one_or_none():
        raise validation_error(f"用户名 {username} 已存在")
    aid = uuid7_str()
    auth_u = AuthUser(
        id=aid, username=username, password_hash=_hash(password),
        must_change_password=True,  # 首登强制改密
        display_name=display_name, role=role, status="active",
        created_at=_now(),
    )
    biz_u = User(
        id=uuid7_str(), external_user_id=aid, username=username,
        display_name=display_name, role=role, status="active",
    )
    db.add(auth_u)
    db.add(biz_u)
    await db.commit()
    return {
        "id": aid, "username": username, "display_name": display_name,
        "role": role, "status": "active", "must_change_password": True,
        "created_at": auth_u.created_at.isoformat() if auth_u.created_at else None,
    }


async def update_user(db, user_id: str, *, display_name=None, role=None, status=None,
                      password=None) -> dict:
    """管理员改用户：角色/状态/显示名可改；重置密码则强制首登改密。"""
    from sqlalchemy import select as _sel

    from app.core.security import hash_password as _hash

    auth_u = (await db.get(AuthUser, user_id))
    if auth_u is None:
        raise not_found("用户")
    biz = (await db.execute(_sel(User).where(User.external_user_id == auth_u.id))).scalar_one_or_none()
    if role is not None:
        if role not in _ALLOWED_ROLES:
            raise validation_error("角色必须是 admin / analyst / viewer")
        auth_u.role = role
        if biz:
            biz.role = role
    if status is not None:
        if status not in _ALLOWED_STATUS:
            raise validation_error("状态必须是 active / disabled")
        auth_u.status = status
        if biz:
            biz.status = status
    if display_name is not None:
        auth_u.display_name = display_name
        if biz:
            biz.display_name = display_name
    if password is not None:
        if len(password) < 8:
            raise validation_error("密码长度至少 8 位")
        auth_u.password_hash = _hash(password)
        auth_u.must_change_password = True  # 重置密码 → 首登待改密
    await db.commit()
    return {
        "id": auth_u.id, "username": auth_u.username,
        "display_name": biz.display_name if biz else auth_u.display_name,
        "role": auth_u.role, "status": auth_u.status,
        "must_change_password": bool(auth_u.must_change_password),
        "created_at": auth_u.created_at.isoformat() if auth_u.created_at else None,
    }


async def delete_user(db, user_id: str, actor_id: str) -> None:
    """管理员删除用户：禁用认证源 + 软删业务用户。不允许删自己。"""
    from sqlalchemy import select as _sel

    if user_id == actor_id:
        raise validation_error("不能删除当前登录的管理员账号")
    auth_u = (await db.get(AuthUser, user_id))
    if auth_u is None:
        raise not_found("用户")
    auth_u.status = "disabled"
    biz = (await db.execute(_sel(User).where(User.external_user_id == auth_u.id))).scalar_one_or_none()
    if biz:
        from datetime import datetime as _dt, timezone as _tz

        biz.status = "disabled"
        biz.deleted_at = _dt.now(_tz)
    await db.commit()


async def get_active_client(client_id: str) -> AuthClient | None:
    async with AsyncSessionLocal() as db:
        c = (await db.execute(
            select(AuthClient).where(AuthClient.client_id == client_id)
        )).scalar_one_or_none()
        if c and c.status == "active":
            return c
    return None


async def issue_auth_code(user: AuthUser, client_id: str, redirect_uri: str, scope: dict) -> str:
    async with AsyncSessionLocal() as db:
        code = gen_token(32)
        db.add(AuthAuthCode(
            code=code,
            client_id=client_id,
            user_id=user.id,
            redirect_uri=redirect_uri,
            scope=scope,
            expires_at=_now() + timedelta(minutes=10),
        ))
        await db.commit()
    return code


async def exchange_code(code: str, client_id: str, redirect_uri: str) -> tuple[str, str]:
    """授权码换 token。返回 (access_token, refresh_token)。"""
    async with AsyncSessionLocal() as db:
        ac = (await db.execute(
            select(AuthAuthCode).where(AuthAuthCode.code == code)
        )).scalar_one_or_none()
        now = _now()
        if (
            ac is None
            or ac.consumed_at is not None
            or ac.expires_at < now
            or ac.client_id != client_id
            or ac.redirect_uri != redirect_uri
        ):
            raise forbidden("授权码无效或已过期")
        ac.consumed_at = now
        user = await db.get(AuthUser, ac.user_id)
        if user is None:
            raise not_found("用户")

        access = oidc_keys.sign(
            {"sub": user.id, "username": user.username, "role": user.role},
            expires_sec=900,
        )
        refresh = gen_token(48)
        db.add(AuthRefreshToken(
            token_hash=refresh,
            client_id=client_id,
            user_id=user.id,
            expires_at=now + timedelta(days=30),
        ))
        await db.commit()
        return access, refresh


async def refresh_access(refresh_token: str, client_id: str) -> tuple[str, str]:
    async with AsyncSessionLocal() as db:
        rt = (await db.execute(
            select(AuthRefreshToken).where(AuthRefreshToken.token_hash == refresh_token)
        )).scalar_one_or_none()
        now = _now()
        if rt is None or rt.revoked_at is not None or rt.expires_at < now:
            raise auth_expired("refresh_token 无效")
        if rt.client_id != client_id:
            raise forbidden("client 不匹配")
        user = await db.get(AuthUser, rt.user_id)
        if user is None:
            raise not_found("用户")
        access = oidc_keys.sign(
            {"sub": user.id, "username": user.username, "role": user.role},
            expires_sec=900,
        )
        new_refresh = gen_token(48)
        rt.token_hash = new_refresh  # 轮换
        await db.commit()
        return access, new_refresh


async def revoke_refresh(refresh_token: str) -> None:
    async with AsyncSessionLocal() as db:
        rt = (await db.execute(
            select(AuthRefreshToken).where(AuthRefreshToken.token_hash == refresh_token)
        )).scalar_one_or_none()
        if rt:
            rt.revoked_at = _now()
            await db.commit()


def build_userinfo(user: AuthUser) -> dict:
    return {
        "sub": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }
