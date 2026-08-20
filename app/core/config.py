"""全局配置（pydantic-settings）。

所有可调项通过环境变量或 .env 注入；功能开关的运行时值以 system_configs 表为准（热加载覆盖此处默认值）。
资源限制按 2C2G 收敛：连接池/并发任务/WS 上限均保守设置。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 应用 ----
    APP_NAME: str = "经营归因分析系统"
    APP_ENV: Literal["dev", "prod", "test"] = "dev"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    # Secure Cookie 开关：None=跟随 APP_ENV（prod 时 Secure，dev 时不 Secure）。
    # 云上 http 直连（无 HTTPS 网关）时必须显式设 COOKIE_SECURE=false，
    # 否则浏览器在非 HTTPS/非 localhost 连接下拒绝保存会话 Cookie，登录必然失效。
    COOKIE_SECURE: bool | None = None

    # ---- 数据库（异步，asyncmy 驱动；2C2G 保守连接池）----
    DB_HOST: str = "mysql"
    DB_PORT: int = 3306
    DB_USER: str = "bia"
    DB_PASSWORD: str = "bia_password"
    DB_NAME: str = "bia"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_RECYCLE: int = 1800

    # ---- Redis（分布式锁 / 任务队列信号量 / WS 心跳）----
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # ---- 认证中心（OIDC，合并进 backend；RS256 签发 + JWKS 验签）----
    OIDC_ISSUER: str = "http://localhost:8000"
    OIDC_CLIENT_ID: str = "bia-web"
    OIDC_CLIENT_SECRET: str = "change-me-client-secret"
    OIDC_REDIRECT_URI: str = "http://localhost:8080/auth/callback"
    OIDC_SCOPES: str = "openid profile"
    OIDC_AUTH_PATH: str = "/authorize"
    OIDC_TOKEN_PATH: str = "/token"
    OIDC_JWKS_PATH: str = "/.well-known/jwks.json"
    OIDC_RSA_PRIVATE_KEY: str = ""  # PEM 私钥；为空则启动时生成临时密钥（仅开发，重启失效）
    JWT_ALGORITHM: str = "RS256"
    JWT_EXPIRE_SECONDS: int = 86400  # 业务端会话 Cookie 令牌有效期

    # ---- 加密（数据源密码 AES；生产必填）----
    APP_ENCRYPTION_KEY: str = ""

    # ---- 2C2G 资源限制 ----
    TASK_CONCURRENCY_LIMIT: int = 3  # 同时运行的分析任务数
    AGENT_MAX_STEPS: int = 8
    AGENT_TIMEOUT_SEC: int = 600
    WS_MAX_CONNECTIONS: int = 10  # 并发 WS 会话上限
    ATTACHMENT_MAX_SIZE_MB: int = 20
    DATA_ROOT: str = "data"  # 工作区/上传/导出根目录（paths.py 与附件服务基于此）
    UPLOAD_DIR: str = "data/uploads"
    EXPORT_DIR: str = "data/exports"

    # ---- 功能开关（默认值；运行时以 system_configs 覆盖）----
    FLAG_SCENARIO_DATA: bool = True
    FLAG_COMMAND_EXEC: bool = True
    FLAG_ATTACHMENT: bool = True
    FLAG_EXTERNAL_DS: bool = False
    FLAG_RESULT_GENERATE: bool = False
    FLAG_WS_HEARTBEAT: bool = True

    # ---- LLM（运行时从 system_configs 热加载，此处占位）----
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_API_KEY: str = ""

    @property
    def ASYNC_DB_URL(self) -> str:
        return (
            f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def SYNC_DB_URL(self) -> str:
        # Alembic / 种子脚本使用同步驱动（pymysql）
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


# ---------------------------------------------------------------------------
# system_configs 热更新缓存（§2.4）
# 启动时全量加载；POST /api/admin/reload 后全量刷新。值按 config_type 反序列化。
# ---------------------------------------------------------------------------
from typing import Any  # noqa: E402

_TYPE_DESER = {
    "bool": lambda v: str(v).strip().lower() in ("1", "true", "yes", "on"),
    "int": lambda v: int(str(v).strip()),
    "float": lambda v: float(str(v).strip()),
    "string": lambda v: str(v),
    "json": lambda v: __import__("json").loads(v),
}


class ConfigCache:
    """system_configs 单例缓存。"""

    _instance: "ConfigCache | None" = None
    _values: dict[str, Any] = {}

    def __new__(cls) -> "ConfigCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def load(self, db) -> None:
        from sqlalchemy import select

        from app.models.business import SystemConfig

        rows = (await db.execute(select(SystemConfig))).scalars().all()
        self._values = {}
        for r in rows:
            fn = _TYPE_DESER.get(r.config_type, str)
            try:
                self._values[r.config_key] = fn(r.config_value)
            except Exception:
                self._values[r.config_key] = r.config_value
        get_logger_cache("config").info("ConfigCache loaded %d keys", len(self._values))

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        v = self._values.get(key, default)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        v = self._values.get(key, default)
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("1", "true", "yes", "on")

    def get_float(self, key: str, default: float = 0.0) -> float:
        v = self._values.get(key, default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    async def reload(self, db) -> dict:
        before = dict(self._values)
        await self.load(db)
        updated = [k for k in self._values if self._values.get(k) != before.get(k)]
        return {"updated_keys": updated}


def get_logger_cache(module: str) -> logging.Logger:  # type: ignore[name-defined]
    import logging

    return logging.getLogger(f"bia.{module}")

