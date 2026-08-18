"""FastAPI 依赖：当前用户解析与 admin 鉴权（§4.2 core/deps.py）。

Cookie(access_token) 或 Authorization: Bearer → 经 jwt_verifier 验签（RS256/JWKS）
→ 本地 users 表 upsert（external_user_id 匹配）→ 返回 User。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select

from app.core.db import get_db
from app.core.security import JwtClaims, jwt_verifier
from app.models.business import User

_COOKIE_NAME = "access_token"


async def get_current_user(
    request: Request,
    access_token: str | None = Cookie(default=None),
    db=Depends(get_db),
) -> User:
    auth = request.headers.get("Authorization")
    token = access_token
    if not token and auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()

    if not token:
        from app.core.errors import auth_required

        raise auth_required()

    try:
        claims: JwtClaims = await jwt_verifier.verify(token)
    except Exception:
        from app.core.errors import auth_expired

        raise auth_expired()

    if claims.exp and claims.exp < int(datetime.now(timezone.utc).timestamp()):
        from app.core.errors import auth_expired

        raise auth_expired()

    user = (
        await db.execute(select(User).where(User.external_user_id == claims.sub))
    ).scalar_one_or_none()
    if user is None:
        # 兜底：合法 JWT 但本地无记录（如直接带 token 访问），按 claims 建本地用户
        user = User(
            external_user_id=claims.sub,
            username=claims.username,
            display_name=claims.username,
            role=claims.role if claims.role in ("admin", "analyst") else "analyst",
            status="active",
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # 角色以认证源为准（管理员降权需重新登录才生效）
        if user.role != claims.role:
            user.role = claims.role
            await db.commit()
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        from app.core.errors import forbidden

        raise forbidden()
    return user
