"""会话接口。"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_user
from ..chat import (
    add_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
    update_conversation,
)
from ..config import settings
from ..database import db
from ..models import CreateConversationRequest, DeleteConversationRequest, UpdateConversationRequest, WsTokenRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/create")
def create(body: CreateConversationRequest, user: dict = Depends(require_user)):
    with db() as conn:
        conversation_id = create_conversation(conn, user["id"], body.title)
        row = get_conversation(conn, conversation_id, user["id"])
    return row


@router.post("/delete")
def delete(body: DeleteConversationRequest, user: dict = Depends(require_user)):
    removed_paths = []
    with db() as conn:
        for cid in body.conversation_ids:
            removed_paths += delete_conversation(conn, cid, user["id"])
    for p in removed_paths:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
    return {"deleted": body.conversation_ids}


@router.post("/update")
def update(body: UpdateConversationRequest, user: dict = Depends(require_user)):
    with db() as conn:
        ok = update_conversation(conn, body.conversation_id, user["id"], body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@router.get("/ls")
def ls(user: dict = Depends(require_user)):
    with db() as conn:
        return list_conversations(conn, user["id"])


@router.get("/ls/{conversation_id}")
def ls_detail(conversation_id: int, user: dict = Depends(require_user)):
    with db() as conn:
        if get_conversation(conn, conversation_id, user["id"]) is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        return list_messages(conn, conversation_id)


@router.post("/ws-token")
def ws_token(body: WsTokenRequest, user: dict = Depends(require_user)):
    from ..tokens import issue_ws_token

    with db() as conn:
        if get_conversation(conn, body.conversation_id, user["id"]) is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        token = issue_ws_token(conn, user["id"], body.conversation_id, ttl=300)
    return {"websocket_token": token, "expires_in": 300}
