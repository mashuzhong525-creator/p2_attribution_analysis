"""OIDC 认证中心路由（§5，合并进 backend）。

登录链路：POST /api/auth/login（校验凭证）→ 发放授权码 →
POST /api/auth/token（授权码换 RS256 access_token，写入 HttpOnly Cookie）。
浏览器后续请求携带 Cookie，由 core/deps 经 JWKS 本地验签解析。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user_relaxed
from app.core.errors import auth_expired, forbidden, validation_error
from app.domains.auth.keys import oidc_keys
from app.domains.auth import service as auth_svc
from app.models.auth import AuthUser
from app.models.business import User
from app.schemas.models import CurrentUserOut

router = APIRouter(tags=["auth"])

_COOKIE = "access_token"


class LoginIn(BaseModel):
    username: str
    password: str


class TokenIn(BaseModel):
    grant_type: str = "authorization_code"
    code: str
    client_id: str | None = None
    redirect_uri: str | None = None
    refresh_token: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str
    client_id: str | None = None


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


def _set_cookie(resp: Response, token: str) -> None:
    # secure 优先级：显式配置 COOKIE_SECURE > 跟随 APP_ENV（prod 时 Secure）
    # 云上 http 直连（无 HTTPS 网关）时必须在 .env 设 COOKIE_SECURE=false，
    # 否则浏览器在非 HTTPS/非 localhost 连接下拒绝保存会话 Cookie，登录失效。
    secure = (
        settings.COOKIE_SECURE
        if settings.COOKIE_SECURE is not None
        else settings.APP_ENV == "prod"
    )
    resp.set_cookie(
        _COOKIE,
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.JWT_EXPIRE_SECONDS,
    )


@router.post("/api/auth/login")
async def login(body: LoginIn) -> dict:
    user = await auth_svc.authenticate(body.username, body.password)
    if user is None:
        raise forbidden("用户名或密码错误")
    code = await auth_svc.issue_auth_code(
        user, settings.OIDC_CLIENT_ID, settings.OIDC_REDIRECT_URI, {"openid": True}
    )
    return {"code": code, "must_change_password": user.must_change_password}


@router.post("/api/auth/token")
async def token(body: TokenIn, response: Response) -> dict:
    if body.grant_type == "refresh_token":
        if not body.refresh_token:
            raise validation_error("refresh_token 必填")
        access, refresh = await auth_svc.refresh_access(
            body.refresh_token, body.client_id or settings.OIDC_CLIENT_ID
        )
        _set_cookie(response, access)
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": settings.JWT_EXPIRE_SECONDS,
            "refresh_token": refresh,
        }
    # authorization_code
    if not body.code:
        raise validation_error("code 必填")
    access, refresh = await auth_svc.exchange_code(
        body.code,
        body.client_id or settings.OIDC_CLIENT_ID,
        body.redirect_uri or settings.OIDC_REDIRECT_URI,
    )
    _set_cookie(response, access)
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": settings.JWT_EXPIRE_SECONDS,
        "refresh_token": refresh,
    }


@router.post("/api/auth/refresh")
async def refresh(body: RefreshIn, response: Response) -> dict:
    access, refresh = await auth_svc.refresh_access(
        body.refresh_token, body.client_id or settings.OIDC_CLIENT_ID
    )
    _set_cookie(response, access)
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": settings.JWT_EXPIRE_SECONDS,
        "refresh_token": refresh,
    }


@router.get("/.well-known/jwks.json")
@router.get("/api/auth/jwks")
async def jwks() -> dict:
    return oidc_keys.jwks()


@router.get("/api/auth/userinfo")
async def userinfo(user: User = Depends(get_current_user_relaxed)) -> dict:
    return {
        "sub": user.external_user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }


@router.get("/api/auth/me", response_model=CurrentUserOut)
async def me(
    user: User = Depends(get_current_user_relaxed),
    db=Depends(get_db),
) -> CurrentUserOut:
    auth_user = (
        await db.execute(select(AuthUser).where(AuthUser.id == user.external_user_id))
    ).scalar_one_or_none()
    return CurrentUserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        must_change_password=bool(auth_user and auth_user.must_change_password),
    )


@router.post("/api/auth/change-password")
async def change_password(
    body: ChangePasswordIn,
    user: User = Depends(get_current_user_relaxed),
) -> dict:
    await auth_svc.change_password(user.external_user_id, body.old_password, body.new_password)
    return {"status": "ok", "message": "密码修改成功，请牢记新密码"}


@router.post("/api/auth/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(_COOKIE, path="/")
    return {"status": "ok", "message": "已登出"}
