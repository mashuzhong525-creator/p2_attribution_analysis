"""OIDC 签名密钥（§5.2 合并进 backend）。

单例持有 RSA 私钥（RS256）。启动时：
- 若配置了 OIDC_RSA_PRIVATE_KEY（PEM）→ 加载；
- 否则生成临时密钥（仅开发，重启失效，日志告警）。

对外提供：
- sign(claims, expires_sec)：签发 RS256 JWT（自动带 iat/exp/iss/aud/kid）。
- jwks()：JWKS 文档（供 /.well-known/jwks.json 与 jwt_verifier.bind_local）。
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("auth.keys")


class OidcKeys:
    _instance: "OidcKeys | None" = None

    def __init__(self) -> None:
        self._priv = None  # type: ignore[var-annotated]
        self._kid = "bia-rsa-1"
        self._started = False

    @classmethod
    def instance(cls) -> "OidcKeys":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start(self) -> None:
        await self._load_or_gen()
        self._started = True

    async def _load_or_gen(self) -> None:
        pem = settings.OIDC_RSA_PRIVATE_KEY
        if pem:
            self._priv = serialization.load_pem_private_key(pem.encode(), password=None)
            logger.info("已加载 OIDC RSA 私钥（来自配置）")
        else:
            self._priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            logger.warning(
                "未配置 OIDC_RSA_PRIVATE_KEY，已生成临时 RSA 密钥（重启失效，仅限开发）"
            )

    def _public_numbers(self):
        return self._priv.public_key().public_numbers()

    def sign(self, claims: dict, expires_sec: int | None = None) -> str:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=expires_sec or settings.JWT_EXPIRE_SECONDS)
        payload = {
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "iss": settings.OIDC_ISSUER,
            "aud": settings.OIDC_CLIENT_ID,
            **claims,
        }
        return jwt.encode(
            payload, self._priv, algorithm="RS256", headers={"kid": self._kid}
        )

    def jwks(self) -> dict:
        nums = self._public_numbers()
        e = (
            base64.urlsafe_b64encode(
                nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")
            )
            .rstrip(b"=")
            .decode()
        )
        n = (
            base64.urlsafe_b64encode(
                nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")
            )
            .rstrip(b"=")
            .decode()
        )
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self._kid,
                    "n": n,
                    "e": e,
                }
            ]
        }


oidc_keys = OidcKeys.instance()
