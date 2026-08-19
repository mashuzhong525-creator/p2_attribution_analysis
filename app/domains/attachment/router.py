"""附件管理 API（§6）。

- POST /api/attachments/upload              上传并解析（AES 无关，明文落盘到工作区上传目录）
- GET  /api/attachments/list?conversation_id=  会话附件列表（附件侧栏）
- GET  /api/attachments/{id}                查看解析结果
- GET  /api/attachments/{id}/download       下载文件流
- DELETE /api/attachments/{id}              删除
需登录；上传/查询/删除均校验会话归属当前用户。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import file_parse_failed, file_too_large, file_type_not_allowed, not_found
from app.core.logging import get_logger
from app.core.uuid import uuid7_str
from app.models.business import Attachment, Conversation, User
from app.schemas.models import AttachmentGetOut, AttachmentUploadOut

logger = get_logger("attachment")
router = APIRouter(tags=["attachment"])

_TEXT_SUFFIX = {".txt", ".csv", ".md", ".json", ".log", ".tsv", ".yaml", ".yml"}
_ALLOWED_SUFFIX = _TEXT_SUFFIX | {".pdf", ".xlsx", ".xls", ".docx", ".png", ".jpg", ".jpeg", ".zip"}


async def _assert_conv_owner(db: AsyncSession, user: User, conv_id: str) -> None:
    """附件操作前置校验：会话存在、归属当前用户、未删除。"""
    conv = (await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user.id,
            Conversation.status != "deleted",
        )
    )).scalar_one_or_none()
    if conv is None:
        raise not_found("会话")


async def _assert_att_owner(db: AsyncSession, user: User, att: Attachment) -> None:
    """附件归属校验：附件所在会话必须归属当前用户（防越权读删他人附件）。"""
    if att.conversation_id:
        conv = (await db.execute(
            select(Conversation).where(
                Conversation.id == att.conversation_id,
                Conversation.user_id == user.id,
                Conversation.status != "deleted",
            )
        )).scalar_one_or_none()
        if conv is None:
            raise not_found("附件")


def _parse_text(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [l for l in text.splitlines() if l.strip()]
    return {
        "summary": text[:500],
        "char_count": len(text),
        "line_count": len(lines),
        "preview_rows": lines[:20],
    }


async def _save_and_parse(file: UploadFile, conv_id: str, user: User) -> Attachment:
    content = await file.read()
    size = len(content)
    if size > settings.ATTACHMENT_MAX_SIZE_MB * 1024 * 1024:
        raise file_too_large(settings.ATTACHMENT_MAX_SIZE_MB)
    suffix = Path(file.filename or "file").suffix.lower()
    if suffix and suffix not in _ALLOWED_SUFFIX:
        raise file_type_not_allowed()

    base = Path(settings.DATA_ROOT) / "uploads" / user.id / conv_id
    base.mkdir(parents=True, exist_ok=True)
    # 防重名
    safe_name = Path(file.filename or "file").name
    dest = base / safe_name
    if dest.exists():
        dest = base / f"{uuid7_str()[:8]}_{safe_name}"
    dest.write_bytes(content)

    att = Attachment(
        id=uuid7_str(), conversation_id=conv_id, file_name=safe_name,
        file_path=str(dest), file_type=suffix.lstrip(".") or "bin", file_size=size,
        parse_status="pending",
    )
    if suffix in _TEXT_SUFFIX:
        try:
            att.parse_result_json = _parse_text(dest)
            att.parse_status = "parsed"
        except Exception as e:  # noqa: BLE001
            att.parse_status = "failed"
            att.parse_result_json = {"error": str(e)}
    else:
        att.parse_result_json = {"summary": f"二进制文件（{att.file_type}），暂不支持文本解析"}
        att.parse_status = "parsed"
    return att


@router.post("/api/attachments/upload", response_model=AttachmentUploadOut)
async def upload(
    conversation_id: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_conv_owner(db, user, conversation_id)
    att = await _save_and_parse(file, conversation_id, user)
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return AttachmentUploadOut(
        attachment_id=att.id, file_name=att.file_name, file_type=att.file_type,
        file_size=att.file_size, parse_status=att.parse_status,
    )


@router.get("/api/attachments/list")
async def list_attachments(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """会话附件列表（附件侧栏数据源），按上传时间倒序。"""
    await _assert_conv_owner(db, user, conversation_id)
    rows = (await db.execute(
        select(Attachment)
        .where(Attachment.conversation_id == conversation_id, Attachment.deleted_at.is_(None))
        .order_by(Attachment.created_at.desc())
    )).scalars().all()
    items = [
        AttachmentGetOut(
            attachment_id=a.id, file_name=a.file_name, file_type=a.file_type,
            file_size=a.file_size, parse_status=a.parse_status,
            parse_result_json=a.parse_result_json,
            created_at=a.created_at.isoformat() if a.created_at else None,
        ).model_dump()
        for a in rows
    ]
    return {"items": items, "total": len(items)}


@router.get("/api/attachments/{att_id}", response_model=AttachmentGetOut)
async def get_att(att_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    att = (await db.get(Attachment, att_id))
    if att is None:
        raise not_found("附件")
    await _assert_att_owner(db, user, att)
    return AttachmentGetOut(
        attachment_id=att.id, file_name=att.file_name, file_type=att.file_type,
        file_size=att.file_size, parse_status=att.parse_status,
        parse_result_json=att.parse_result_json, created_at=att.created_at.isoformat() if att.created_at else None,
    )


@router.get("/api/attachments/{att_id}/download")
async def download_att(att_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """下载附件原始文件（FileResponse 文件流）。"""
    att = (await db.get(Attachment, att_id))
    if att is None:
        raise not_found("附件")
    await _assert_att_owner(db, user, att)
    path = Path(att.file_path)
    if not path.is_file():
        raise not_found("附件文件")
    return FileResponse(path, filename=att.file_name)


@router.delete("/api/attachments/{att_id}")
async def delete_att(att_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    att = (await db.get(Attachment, att_id))
    if att is None:
        raise not_found("附件")
    await _assert_att_owner(db, user, att)
    await db.delete(att)
    await db.commit()
    return {"status": "ok", "message": "已删除"}
