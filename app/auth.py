"""认证：mock 授权登录 + 登录态（演示级）。"""

import secrets
import time

from fastapi import Depends, Header, HTTPException

from .database import get_connection

TOKEN_TTL = 7200
_TOKENS: dict[str, dict] = {}


def login(username: str, password: str) -> dict | None:
    # 演示级：密码明文校验（正式环境必须接入真实认证中心）
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND status='active'", (username,)
        ).fetchone()
        if row is None or row["password"] != password:
            return None
        user = dict(row)
    token = secrets.token_hex(16)
    _TOKENS[token] = {"user_id": user["id"], "expires_at": time.time() + TOKEN_TTL}
    return {"token": token, "user_info": user}


def get_current_user(token: str | None) -> dict | None:
    if not token:
        return None
    info = _TOKENS.get(token)
    if not info or info["expires_at"] < time.time():
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (info["user_id"],)).fetchone()
        return dict(row) if row else None


def require_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    user = get_current_user(authorization.split(" ", 1)[1].strip())
    if user is None:
        raise HTTPException(status_code=401, detail="登录态失效")
    return user


def require_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
