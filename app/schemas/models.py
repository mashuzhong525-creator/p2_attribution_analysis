"""请求/响应 Pydantic 模型（§6 字段级契约）。

时间统一 ISO 8601 UTC 字符串。分页响应统一 {items,total,page,page_size}。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------- 通用 ----------------
class Page(BaseModel):
    page: int = 1
    page_size: int = 20


class PageResult(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


# ---------------- Auth ----------------
class CurrentUserOut(BaseModel):
    id: str
    username: str
    display_name: str
    role: str


# ---------------- Chat ----------------
class ConversationCreate(BaseModel):
    title: str | None = None
    data_source_id: str | None = None


class ConversationUpdate(BaseModel):
    conversation_id: str
    title: str


class ConversationDelete(BaseModel):
    conversation_ids: list[str]


class ConversationOut(BaseModel):
    conversation_id: str
    title: str
    status: str
    data_source_id: str | None = None
    last_message_at: str | None = None


class MessageOut(BaseModel):
    message_id: str
    role: str
    message_type: str
    content: str
    tool_name: str | None = None
    tool_status: str | None = None
    seq_no: int
    attachments: list[Any] = Field(default_factory=list)
    created_at: str | None = None


class ConversationHistoryOut(BaseModel):
    conversation_id: str
    data_source_id: str | None = None
    items: list[MessageOut]


# ---------------- Task / Send ----------------
class ChatSend(BaseModel):
    conversation_id: str
    content: str
    attachment_ids: list[str] | None = None


class SendResultOut(BaseModel):
    message_id: str
    task_id: str
    queue_position: int


class TaskCancelOut(BaseModel):
    task_status: str
    message: str


class TaskDetailOut(BaseModel):
    task_id: str
    task_status: str
    current_step: int
    queue_position: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None


class WsTokenOut(BaseModel):
    websocket_token: str
    expires_in: int


# ---------------- Attachment ----------------
class AttachmentUploadOut(BaseModel):
    attachment_id: str
    file_name: str
    file_type: str
    file_size: int
    parse_status: str


class AttachmentDelete(BaseModel):
    attachment_id: str


class AttachmentGetOut(BaseModel):
    attachment_id: str
    file_name: str
    file_type: str
    file_size: int
    parse_status: str
    parse_result_json: dict | None = None
    created_at: str | None = None


# ---------------- Result ----------------
class ResultOut(BaseModel):
    result_id: str
    problem_definition: str
    key_metrics: list[dict] = Field(default_factory=list)
    evidence_list: list[dict] = Field(default_factory=list)
    conclusion_text: str
    missing_data_text: str = ""
    next_action_text: str = ""
    result_markdown: str
    created_at: str | None = None


class ResultExportOut(BaseModel):
    result_id: str
    result_file_path: str


# ---------------- Admin ----------------
class ConfigItemIn(BaseModel):
    config_key: str
    config_value: Any


class ConfigUpdateIn(BaseModel):
    items: list[ConfigItemIn]


class ConfigItemOut(BaseModel):
    config_key: str
    config_value: Any
    config_type: str
    description: str | None = None


class ConfigGroupOut(BaseModel):
    group: str
    items: list[ConfigItemOut]


class DataSourceCreate(BaseModel):
    name: str
    db_type: str = "mysql"
    host: str
    port: int = 3306
    database: str
    username: str
    password: str
    is_readonly: bool = True
    is_enabled: bool = True
    description: str | None = None


class DataSourceUpdate(BaseModel):
    name: str | None = None
    db_type: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    is_readonly: bool | None = None
    is_enabled: bool | None = None
    description: str | None = None


class DataSourceOut(BaseModel):
    id: str
    name: str
    db_type: str
    host: str
    port: int
    database: str
    username: str
    is_readonly: bool
    is_enabled: bool
    description: str | None = None


class ReloadOut(BaseModel):
    status: str
    message: str
    updated_keys: list[str] = Field(default_factory=list)


class TestDsOut(BaseModel):
    ok: bool
    message: str
    latency_ms: int | None = None


class LogItemOut(BaseModel):
    log_id: str
    task_id: str
    log_level: str
    log_type: str
    log_content: str
    created_at: str | None = None


class AdminGenericOut(BaseModel):
    status: str
    message: str
