"""附件接口（最小实现：上传/删除/下载）。"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..auth import require_user
from ..chat import add_attachment, get_attachment, list_attachments
from ..config import settings
from ..database import db

router = APIRouter(prefix="/api/attachment", tags=["attachment"])


@router.post("/upload")
async def upload(
    conversation_id: int = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    folder = settings.upload_dir / str(user["id"]) / str(conversation_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (file.filename or "upload.bin")
    path.write_bytes(await file.read())
    with db() as conn:
        attachment_id = add_attachment(
            conn,
            conversation_id,
            file.filename or "upload.bin",
            str(path),
            (file.filename or "").rsplit(".", 1)[-1],
            path.stat().st_size,
        )
        row = get_attachment(conn, attachment_id)
    return row


@router.delete("/delete")
def delete(attachment_id: int, user: dict = Depends(require_user)):
    with db() as conn:
        row = get_attachment(conn, attachment_id)
        if row is None:
            raise HTTPException(status_code=404, detail="附件不存在")
        path = row["file_path"]
        conn.execute("DELETE FROM attachments WHERE id=?", (attachment_id,))
    try:
        from pathlib import Path

        Path(path).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True}


@router.get("/get")
def get(attachment_id: int, user: dict = Depends(require_user)):
    with db() as conn:
        row = get_attachment(conn, attachment_id)
        if row is None:
            raise HTTPException(status_code=404, detail="附件不存在")
    return FileResponse(row["file_path"], filename=row["file_name"])


@router.get("/ls")
def ls(conversation_id: int, user: dict = Depends(require_user)):
    with db() as conn:
        return list_attachments(conn, conversation_id)
