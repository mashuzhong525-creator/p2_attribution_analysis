"""OIDC 认证中心业务逻辑（§5 授权码模式，合并进 backend）。

- authenticate：校验 auth_users 凭证。
- issue_auth_code：登录成功后发放一次性授权码（10 分钟有效期）。
- exchange_code：授权码换 RS256 access_token（写 HttpOnly Cookie）+ refresh_token。
- refresh_token：刷新 access_token。
- userinfo：由 claims 返回用户画像。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.errors import auth_expired, forbidden, not_found, validation_error
from app.core.security import gen_token, verify_password
from app.core.uuid import uuid7_str
from app.domains.auth.keys import oidc_keys
from app.models.auth import AuthAuthCode, AuthClient, AuthRefreshToken, AuthUser


async def authenticate(username: str, password: str) -> AuthUser | None:
    async with AsyncSessionLocal() as db:
        u = (await db.execute(
            select(AuthUser).where(AuthUser.username == username)
        )).scalar_one_or_none()
        if u and u.status == "active" and verify_password(password, u.password_hash):
            return u
    return None


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
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        ))
        await db.commit()
    return code


async def exchange_code(code: str, client_id: str, redirect_uri: str) -> tuple[str, str]:
    """授权码换 token。返回 (access_token, refresh_token)。"""
    async with AsyncSessionLocal() as db:
        ac = (await db.execute(
            select(AuthAuthCode).where(AuthAuthCode.code == code)
        )).scalar_one_or_none()
        now = datetime.now(timezone.utc)
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
        now = datetime.now(timezone.utc)
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
            rt.revoked_at = datetime.now(timezone.utc)
            await db.commit()


def build_userinfo(user: AuthUser) -> dict:
    return {
        "sub": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }
