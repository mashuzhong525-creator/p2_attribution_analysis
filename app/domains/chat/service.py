"""会话域 service（§4.4）。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.errors import not_found, validation_error
from app.core.uuid import uuid7_str
from app.models.business import Conversation, DataSource, Message


async def _default_data_source_id(db) -> str | None:
    """data_source_id 空值回退内置示例库（name='business'，§2.3）。"""
    row = (await db.execute(select(DataSource).where(DataSource.name == "business"))).scalar_one_or_none()
    return row.id if row else None


async def create(db, user_id: str, title: str | None, data_source_id: str | None) -> Conversation:
    if data_source_id:
        ds = (await db.execute(select(DataSource).where(DataSource.id == data_source_id))).scalar_one_or_none()
        if ds is None or not ds.is_enabled:
            raise validation_error("数据源不存在或已禁用", {"data_source_id": data_source_id})
    else:
        data_source_id = await _default_data_source_id(db)

    conv = Conversation(
        id=uuid7_str(),
        user_id=user_id,
        data_source_id=data_source_id,
        title=title or "新会话",
        status="active",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def list_for_user(db, user_id: str, page: int, page_size: int) -> tuple[list[Conversation], int]:
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    base = select(Conversation).where(
        Conversation.user_id == user_id, Conversation.status == "active"
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(rows), int(total)


async def rename(db, user_id: str, conv_id: str, title: str) -> Conversation:
    conv = await _get_owned(db, user_id, conv_id)
    conv.title = title
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(conv)
    return conv


async def soft_delete(db, user_id: str, conv_ids: list[str]) -> list[str]:
    deleted: list[str] = []
    for cid in conv_ids:
        conv = await _get_owned(db, user_id, cid, raise_if_missing=False)
        if conv is None:
            continue
        conv.status = "deleted"
        conv.deleted_at = datetime.now(timezone.utc)
        conv.updated_at = datetime.now(timezone.utc)
        deleted.append(cid)
    await db.commit()
    return deleted


async def get_history(db, user_id: str, conv_id: str) -> tuple[Conversation, list[Message]]:
    conv = await _get_owned(db, user_id, conv_id)
    msgs = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id, Message.deleted_at.is_(None))
            .order_by(Message.seq_no.asc())
        )
    ).scalars().all()
    return conv, list(msgs)


async def _get_owned(db, user_id: str, conv_id: str, raise_if_missing: bool = True) -> Conversation | None:
    conv = (await db.execute(select(Conversation).where(Conversation.id == conv_id))).scalar_one_or_none()
    if conv is None:
        if raise_if_missing:
            raise not_found("会话")
        return None
    if conv.user_id != user_id:
        raise not_found("会话")
    return conv
