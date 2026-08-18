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

    # ---- 认证中心（OIDC，同仓库独立 schema auth_）----
    OIDC_ISSUER: str = "http://auth:8000"
    OIDC_CLIENT_ID: str = "bia-web"
    OIDC_CLIENT_SECRET: str = "change-me-client-secret"
    OIDC_REDIRECT_URI: str = "http://localhost:8080/auth/callback"
    OIDC_SCOPES: str = "openid profile"
    OIDC_AUTH_PATH: str = "/authorize"
    OIDC_TOKEN_PATH: str = "/token"
    OIDC_JWKS_PATH: str = "/.well-known/jwks.json"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_SECONDS: int = 86400  # 业务端会话 Cookie 令牌有效期

    # ---- 加密（数据源密码 AES；生产必填）----
    APP_ENCRYPTION_KEY: str = ""

    # ---- 2C2G 资源限制 ----
    TASK_CONCURRENCY_LIMIT: int = 3  # 同时运行的分析任务数
    AGENT_MAX_STEPS: int = 8
    AGENT_TIMEOUT_SEC: int = 600
    WS_MAX_CONNECTIONS: int = 10  # 并发 WS 会话上限
    ATTACHMENT_MAX_SIZE_MB: int = 20
    UPLOAD_DIR: str = "workspace/uploads"
    EXPORT_DIR: str = "workspace/exports"

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
