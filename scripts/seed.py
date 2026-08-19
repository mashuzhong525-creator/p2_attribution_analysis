"""基线种子（幂等）：system_configs(31) + 认证用户/客户端 + 业务用户 + 预置数据源。

运行：python -m scripts.seed
- 使用同步引擎（pymysql）连接业务库。
- 幂等：已存在的记录跳过，不打扰运行期修改（如管理员改过的配置）。
- 表不存在时先 create_all（兜底，正常由 alembic 先行）。

31 项 system_configs 覆盖：LLM / 分析引擎 / 系统 / 附件 / 安全 / 功能开关 / 提示词 / 数据。
配置键命名与 docs/design 一致；运行时提示词以 docs/prompts 资产为准，此处仅存占位便于热加载框架落地。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import encrypt_secret, hash_password
from app.core.uuid import uuid7_str
from app.db.base import Base
import app.models.business  # noqa: F401
import app.models.auth  # noqa: F401

from app.models.business import (
    AuditLog,
    DataSource,
    SystemConfig,
    User,
)
from app.models.auth import AuthClient, AuthUser

ENGINE = create_engine(settings.SYNC_DB_URL, poolclass=NullPool)
Session = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(bind=ENGINE)

# (key, value, type, group, description) — 31 项
CONFIGS: list[tuple[str, str, str, str, str]] = [
    ("llm_base_url", "https://api.deepseek.com/v1", "string", "llm", "LLM 网关地址"),
    ("llm_model", "deepseek-chat", "string", "llm", "默认模型"),
    ("llm_api_key", "", "string", "llm", "LLM API Key（生产走环境变量）"),
    ("llm_temperature", "0.0", "float", "llm", "采样温度（归因需稳定）"),
    ("llm_max_tokens", "4096", "int", "llm", "单次最大输出 token"),
    ("llm_cost_per_1k_input", "0.001", "float", "llm", "输入单价（元/1k）"),
    ("llm_cost_per_1k_output", "0.002", "float", "llm", "输出单价（元/1k）"),
    ("agent_max_steps", "8", "int", "分析引擎", "Agent 单任务最大工具步数"),
    ("agent_timeout_sec", "600", "int", "分析引擎", "单任务超时（秒）"),
    ("agent_seed", "2026", "string", "分析引擎", "固定随机种子，保证演示可复现"),
    ("task_concurrency_limit", "3", "int", "系统", "2C2G 并发分析任务上限"),
    ("attachment_max_size_mb", "20", "int", "附件", "单附件大小上限(MB)"),
    ("ws_heartbeat_sec", "30", "int", "系统", "WS 心跳间隔（秒）"),
    ("ws_max_connections", "10", "int", "系统", "WS 并发会话上限"),
    ("cleanup_soft_delete_days", "90", "int", "系统", "软删数据物理清理保留期(天)"),
    ("cleanup_task_logs_days", "90", "int", "系统", "task_logs 保留期(天)"),
    ("cleanup_llm_calls_days", "180", "int", "系统", "llm_calls 保留期(天)"),
    ("ui_page_size", "20", "int", "系统", "列表默认分页大小"),
    ("data_source_default_schema", "scenario_goods", "string", "数据", "默认会话绑定数据源"),
    ("prompt_agent_system", '{"version":"0.1","note":"见 docs/prompts/agent-system-prompt.md"}', "json", "提示词", "Agent 系统提示词（热加载）"),
    ("prompt_tool_descriptions", '{"version":"0.1","note":"见 docs/prompts/tool-descriptions.md"}', "json", "提示词", "工具描述（热加载）"),
    ("prompt_context_summary", '{"version":"0.1","note":"见 docs/prompts/context-summary-prompt.md"}', "json", "提示词", "上下文摘要提示词（热加载）"),
    ("flag_scenario_data", "true", "bool", "feature_flag", "示例数据 schema 注入与检索"),
    ("flag_command_exec", "true", "bool", "feature_flag", "命令执行工具（工作区沙箱+白名单）"),
    ("flag_attachment", "true", "bool", "feature_flag", "附件上传与解析"),
    ("flag_external_ds", "false", "bool", "feature_flag", "外部数据源连接（仅 MySQL）"),
    ("flag_result_generate", "false", "bool", "feature_flag", "result_generate 工具（默认关）"),
    ("flag_ws_heartbeat", "true", "bool", "feature_flag", "WS 心跳通道"),
    ("security_cors_origins", '["http://localhost:5173","http://localhost:8080"]', "json", "security", "CORS 允许源"),
    ("security_jwt_expire_sec", "86400", "int", "security", "业务端会话令牌有效期(秒)"),
    ("security_max_login_fail", "5", "int", "security", "最大登录失败次数后锁定"),
]

AUTH_USERS = [
    ("admin", "admin123", "admin", "系统管理员"),
    ("analyst", "analyst123", "analyst", "分析师"),
]

DATA_SOURCES = [
    # 场景示例库：host 跟随 settings.DB_HOST（容器内=mysql 服务名，本地=localhost），避免硬编码漂移导致连接失败
    ("商品目录优化示例库", "scenario_goods", "mysql", settings.DB_HOST, 3306, "scenario_goods", "bia", settings.DB_PASSWORD, True, True),
    ("库存异常分析示例库", "scenario_inventory", "mysql", settings.DB_HOST, 3306, "scenario_inventory", "bia", settings.DB_PASSWORD, True, True),
    ("外部业务库 bi-prod", "bi-prod", "mysql", "10.0.0.8", 3306, "bi_warehouse", "bi_ro", "bi_pass", True, False),
]


def seed_configs(s) -> None:
    for key, value, ctype, group, desc in CONFIGS:
        if s.execute(select(SystemConfig).where(SystemConfig.config_key == key)).scalar_one_or_none():
            continue
        s.add(SystemConfig(id=uuid7_str(), config_key=key, config_value=value,
                           config_type=ctype, config_group=group, description=desc))


def seed_auth_users(s) -> None:
    for username, pw, role, disp in AUTH_USERS:
        if s.execute(select(AuthUser).where(AuthUser.username == username)).scalar_one_or_none():
            continue
        s.add(AuthUser(id=uuid7_str(), username=username, password_hash=hash_password(pw),
                       display_name=disp, role=role, status="active",
                       must_change_password=True))


def seed_auth_client(s) -> None:
    cid = settings.OIDC_CLIENT_ID
    if s.execute(select(AuthClient).where(AuthClient.client_id == cid)).scalar_one_or_none():
        return
    s.add(AuthClient(id=uuid7_str(), client_id=cid,
                     client_secret_hash=hash_password(settings.OIDC_CLIENT_SECRET),
                     redirect_uris=json.dumps([settings.OIDC_REDIRECT_URI]),
                     scopes=json.dumps(["openid", "profile"]), status="active"))


def seed_biz_users(s) -> None:
    for username, role, disp in [("admin", "admin", "系统管理员"), ("analyst", "analyst", "分析师")]:
        if s.execute(select(User).where(User.username == username)).scalar_one_or_none():
            continue
        auth = s.execute(select(AuthUser).where(AuthUser.username == username)).scalar_one_or_none()
        sub = auth.id if auth else uuid7_str()
        s.add(User(id=uuid7_str(), external_user_id=sub, username=username,
                   display_name=disp, role=role, status="active"))


def seed_data_sources(s) -> None:
    for name, _dbkey, dtype, host, port, database, user, pw, readonly, enabled in DATA_SOURCES:
        existing = s.execute(select(DataSource).where(DataSource.name == name)).scalar_one_or_none()
        if existing:
            # 幂等更新：账号/密码/地址跟随配置漂移
            existing.host = host
            existing.port = port
            existing.database = database
            existing.username = user
            existing.password_encrypted = encrypt_secret(pw)
            existing.is_readonly = bool(readonly)
            existing.is_enabled = bool(enabled)
            continue
        s.add(DataSource(id=uuid7_str(), name=name, db_type=dtype, host=host, port=port,
                        database=database, username=user, password_encrypted=encrypt_secret(pw),
                        is_readonly=bool(readonly), is_enabled=bool(enabled)))


def seed_all() -> None:
    Base.metadata.create_all(ENGINE)  # 兜底：若迁移未先行
    with Session() as s:
        seed_configs(s)
        seed_auth_users(s)
        seed_auth_client(s)
        seed_biz_users(s)
        seed_data_sources(s)
        # 初始审计留痕
        s.add(AuditLog(id=uuid7_str(), user_id="seed", action_type="seed",
                       target_type="system", target_id="init",
                       after_value={"note": "基线种子初始化"}, created_at=datetime.now(timezone.utc)))
        s.commit()
    print("[seed] 基线种子完成：configs/auth_users/auth_client/biz_users/data_sources")


if __name__ == "__main__":
    seed_all()
