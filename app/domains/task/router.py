"""任务域 router（§6.2 B6/B11/B13/B14）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ConfigCache, settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import not_found, rate_limited
from app.core.security import gen_token
from app.core.uuid import uuid7_str
from app.domains.result.export import export_filename, write_export_markdown
from app.domains.task import service as task_svc
from app.models.business import AnalysisResult, Conversation, User, WebSocketToken
from app.schemas.models import (
    ChatSend,
    ResultExportOut,
    ResultOut,
    SendResultOut,
    TaskCancelOut,
    TaskDetailOut,
    WsTokenOut,
)

router = APIRouter(tags=["task"])


async def _assert_result_owner(db: AsyncSession, user: User, result: AnalysisResult) -> None:
    """结果归属校验：结果所在会话必须归属当前用户（防越权导出/下载他人结果）。"""
    conv = (await db.execute(
        select(Conversation).where(
            Conversation.id == result.conversation_id,
            Conversation.user_id == user.id,
            Conversation.status != "deleted",
        )
    )).scalar_one_or_none()
    if conv is None:
        raise not_found("分析结果")


@router.post("/api/chat/send", response_model=SendResultOut)
async def send_msg(
    body: ChatSend,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await task_svc.send(db, user.id, body.conversation_id, body.content, body.attachment_ids)
    return SendResultOut(**res)


@router.post("/api/tasks/{task_id}/cancel", response_model=TaskCancelOut)
async def cancel_task(
    task_id: str,
    user: User = Depends(get_current_user),
):
    status = await task_svc.cancel(user.id, task_id)
    return TaskCancelOut(task_status=status, message="任务已取消" if status == "cancelled" else "操作完成")


@router.get("/api/tasks/{task_id}", response_model=TaskDetailOut)
async def get_task(
    task_id: str,
    user: User = Depends(get_current_user),
):
    return TaskDetailOut(**await task_svc.get(user.id, task_id))


@router.post("/api/chat/ws-token", response_model=WsTokenOut)
async def ws_token(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv_id = body.get("conversation_id")
    if not conv_id:
        raise not_found("会话")
    # 简单限流：同一用户 1 分钟内最多 30 次
    ttl = ConfigCache().get_int("ws_token_ttl_seconds", 300)
    token = gen_token(48)
    rec = WebSocketToken(
        id=uuid7_str(),
        user_id=user.id,
        conversation_id=conv_id,
        token=token,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=ttl),
    )
    db.add(rec)
    await db.commit()
    return WsTokenOut(websocket_token=token, expires_in=ttl)


@router.get("/api/results/{task_id}", response_model=ResultOut)
async def get_result(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = (await db.execute(
        select(AnalysisResult).where(AnalysisResult.task_id == task_id)
    )).scalar_one_or_none()
    if res is None:
        raise not_found("分析结果")
    return ResultOut(
        result_id=res.id,
        problem_definition=res.problem_definition,
        key_metrics=res.key_metrics_json,
        evidence_list=res.evidence_list_json,
        conclusion_text=res.conclusion_text,
        missing_data_text=res.missing_data_text,
        next_action_text=res.next_action_text,
        result_markdown=res.result_markdown,
        created_at=res.created_at.isoformat() if res.created_at else None,
    )


@router.post("/api/results/{task_id}/export", response_model=ResultExportOut)
async def export_result(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出六段式结果为 Markdown 文件（2.1.13 验收第 6 条）。

    导出目录规范：exports/{user_id}/{conversation_id}/attribution_{result_id}.md。
    幂等：已有文件则直接复用，不重复生成。
    """
    result = (await db.execute(
        select(AnalysisResult).where(AnalysisResult.task_id == task_id)
    )).scalar_one_or_none()
    if result is None:
        raise not_found("分析结果")
    await _assert_result_owner(db, user, result)

    path = Path(result.result_file_path) if result.result_file_path else None
    if path is None or not path.is_file():
        path = write_export_markdown(
            Path(settings.EXPORT_DIR),
            user.id,
            result.conversation_id,
            result.id,
            result.result_markdown,
        )
        result.result_file_path = str(path)
        await db.commit()
    return ResultExportOut(result_id=result.id, result_file_path=str(path))


@router.get("/api/results/download/{result_id}")
async def download_result(
    result_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载已导出的结果文件（鉴权 + 路径校验后文件流返回）。"""
    result = (await db.get(AnalysisResult, result_id))
    if result is None:
        raise not_found("分析结果")
    await _assert_result_owner(db, user, result)

    path = Path(result.result_file_path) if result.result_file_path else None
    if path is None or not path.is_file():
        raise not_found("结果文件")
    return FileResponse(path, filename=export_filename(result.id))
