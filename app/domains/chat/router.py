"""会话域 router（§6.2 B1-B5）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.business import User
from app.schemas.models import (
    ConversationCreate,
    ConversationDelete,
    ConversationHistoryOut,
    ConversationOut,
    ConversationUpdate,
    MessageOut,
    PageResult,
)
from app.domains.chat import service as chat_svc

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _conv_out(c: "object") -> ConversationOut:
    return ConversationOut(
        conversation_id=c.id,
        title=c.title,
        status=c.status,
        data_source_id=getattr(c, "data_source_id", None),
        last_message_at=c.last_message_at.isoformat() if c.last_message_at else None,
    )


@router.post("/create", response_model=ConversationOut)
async def create_conv(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = await chat_svc.create(db, user.id, body.title, body.data_source_id)
    return _conv_out(c)


@router.post("/update", response_model=ConversationOut)
async def update_conv(
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = await chat_svc.rename(db, user.id, body.conversation_id, body.title)
    return _conv_out(c)


@router.post("/delete")
async def delete_conv(
    body: ConversationDelete,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await chat_svc.soft_delete(db, user.id, body.conversation_ids)
    return {"status": "ok", "message": f"已删除 {len(deleted)} 个会话", "deleted_ids": deleted}


@router.get("/ls", response_model=PageResult)
async def list_conv(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await chat_svc.list_for_user(db, user.id, page, page_size)
    return PageResult(
        items=[_conv_out(c) for c in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/ls/{conversation_id}", response_model=ConversationHistoryOut)
async def history(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv, msgs = await chat_svc.get_history(db, user.id, conversation_id)
    items = [
        MessageOut(
            message_id=m.id,
            role=m.role,
            message_type=m.message_type,
            content=m.content,
            tool_name=m.tool_name,
            tool_status=m.tool_status,
            seq_no=m.seq_no,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in msgs
    ]
    return ConversationHistoryOut(
        conversation_id=conv.id,
        data_source_id=getattr(conv, "data_source_id", None),
        items=items,
    )
