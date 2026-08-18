"""认证接口。"""

from fastapi import APIRouter, Depends, HTTPException

from ..auth import login, require_user
from ..models import LoginRequest

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login")
def do_login(body: LoginRequest):
    result = login(body.username, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return result


@router.get("/auth/me")
def me(user: dict = Depends(require_user)):
    return user
