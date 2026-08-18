"""业务库 ORM 模型（13 张表），字段级对齐 `docs/design/数据模型设计.md`。

约定：
- 主键 VARCHAR(32) 无横线 UUIDv7（应用层生成）。
- 时间为 UTC（DATETIME）。
- 逻辑外键（无 FK 约束，应用层保证一致性）。
- 软删除列 deleted_at；JSON 列用 sa.JSON。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.uuid import uuid7_str
from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    external_user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="analyst", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conv_user_msg", "user_id", "last_message_at"),
        Index("ix_conv_ds", "data_source_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    data_source_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(128), default="新会话", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_msg_conv_created", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    conversation_id: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    message_type: Mapped[str] = mapped_column(String(16), default="text", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_att_conv", "conversation_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    conversation_id: Mapped[str] = mapped_column(String(32), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    parse_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    __table_args__ = (Index("ix_task_conv_status", "conversation_id", "task_status"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    conversation_id: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    task_status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        Index("ix_res_task", "task_id", unique=True),
        Index("ix_res_conv", "conversation_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    task_id: Mapped[str] = mapped_column(String(32), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(32), nullable=False)
    problem_definition: Mapped[str] = mapped_column(Text, nullable=False)
    key_metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_list_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    conclusion_text: Mapped[str] = mapped_column(Text, nullable=False)
    missing_data_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    next_action_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    result_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    result_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class ContextSummary(Base):
    __tablename__ = "context_summaries"
    __table_args__ = (Index("ix_ctx_conv_end", "conversation_id", "end_seq_no"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    conversation_id: Mapped[str] = mapped_column(String(32), nullable=False)
    start_seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    end_seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class WebSocketToken(Base):
    __tablename__ = "websocket_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(32), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    config_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    config_type: Mapped[str] = mapped_column(String(16), default="string", nullable=False)
    config_group: Mapped[str] = mapped_column(String(32), default="general", nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class TaskLog(Base):
    __tablename__ = "task_logs"
    __table_args__ = (Index("ix_log_task_created", "task_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    task_id: Mapped[str] = mapped_column(String(32), nullable=False)
    log_level: Mapped[str] = mapped_column(String(8), default="INFO", nullable=False)
    log_type: Mapped[str] = mapped_column(String(32), default="system", nullable=False)
    log_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    db_type: Mapped[str] = mapped_column(String(16), default="mysql", nullable=False)
    host: Mapped[str] = mapped_column(String(128), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=3306, nullable=False)
    database: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    is_readonly: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class LLMCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        Index("ix_llm_task", "task_id"),
        Index("ix_llm_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7_str)
    task_id: Mapped[str] = mapped_column(String(32), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
