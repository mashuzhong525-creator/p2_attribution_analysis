"""安全基础设施：密码哈希、JWT、AES 加密、随机令牌。"""
from __future__ import annotations

import base64
import secrets

import jwt
from cryptography.fernet import Fernet
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------- 密码哈希（认证库 auth_users）----------
def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ---------- JWT（业务端会话 Cookie 令牌）----------
def create_access_token(sub: str, expires_sec: int | None = None, extra: dict | None = None) -> str:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=expires_sec or settings.JWT_EXPIRE_SECONDS)
    payload: dict = {"sub": sub, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.OIDC_CLIENT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.OIDC_CLIENT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


# ---------- AES 加密（数据源密码存储）----------
def _fernet() -> Fernet:
    key = settings.APP_ENCRYPTION_KEY
    if not key:
        # 开发期退化：用 client secret 派生 32 字节密钥；生产必须显式配置 APP_ENCRYPTION_KEY
        key = base64.urlsafe_b64encode(settings.OIDC_CLIENT_SECRET.encode().ljust(32, b"0")[:32])
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


# ---------- 随机令牌（auth code / refresh / ws token）----------
def gen_token(length: int = 48) -> str:
    return secrets.token_urlsafe(length)
