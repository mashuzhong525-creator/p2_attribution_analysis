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


# ---------- JWT 验签（backend 侧，RS256 + JWKS，§5.2）----------
from datetime import datetime, timezone  # noqa: E402

import httpx  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class JwtClaims(BaseModel):
    sub: str
    username: str
    role: str
    exp: int
    aud: str
    iat: int | None = None


class JwtVerifier:
    """JWKS 公钥缓存 + RS256 本地验签。

    合并部署下，backend 自签自验：lifespan 启动时通过 bind_local() 直接注入进程内公钥，
    避免 lifespan 阶段 HTTP 拉取 JWKS（此时服务尚未监听）失败。仍保留 HTTP 刷新作为兜底。
    """

    def __init__(self) -> None:
        self._keys: dict[str, str] = {}  # kid -> JWK json
        self._started = False

    def bind_local(self, jwks: dict) -> None:
        """注入进程内 JWKS（oidc_keys.jwks()），优先于 HTTP 拉取。"""
        self._keys = {k["kid"]: k for k in jwks.get("keys", [])}
        self._started = True

    async def start(self) -> None:
        # 合并部署：优先本地绑定；若未绑定再尝试 HTTP 拉取。
        if not self._keys:
            try:
                await self.refresh_keys()
            except Exception:  # pragma: no cover
                get_logger_sec().warning("JWKS 初始拉取失败（本地绑定缺失），将在首次验签时重试")
        self._started = True

    async def refresh_keys(self) -> None:
        from app.core.config import settings

        url = f"{settings.OIDC_ISSUER.rstrip('/')}{settings.OIDC_JWKS_PATH}"
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                resp = await c.get(url)
                resp.raise_for_status()
                data = resp.json()
            self._keys = {k["kid"]: k for k in data.get("keys", [])}
            get_logger_sec().info("JWKS 拉取成功，kid=%s", list(self._keys.keys()))
        except Exception as e:  # pragma: no cover
            get_logger_sec().error("JWKS 拉取失败：%s", e)
            if not self._keys:
                raise

    async def verify(self, token: str) -> JwtClaims:
        from app.core.config import settings

        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if kid and kid in self._keys:
            key = jwt.algorithms.RSAAlgorithm.from_jwk(self._keys[kid])
        else:
            await self.refresh_keys()
            kid = header.get("kid")
            key = self._keys.get(kid)  # type: ignore[assignment]
            if key:
                key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            else:
                raise jwt.PyJWTError("no matching JWK")
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.OIDC_CLIENT_ID,
            issuer=settings.OIDC_ISSUER,
        )
        return JwtClaims(**{k: payload[k] for k in JwtClaims.model_fields if k in payload})


def get_logger_sec():  # type: ignore[name-defined]
    import logging

    return logging.getLogger("bia.security")


jwt_verifier = JwtVerifier()
