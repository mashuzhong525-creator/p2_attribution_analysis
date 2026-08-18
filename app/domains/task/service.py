"""任务域 service（§4.6 service.py）。

send：互斥检查 → user 消息落库(seq_no=MAX+1) → 关联附件 → analysis_task 落库(queued)
      → WS seq 基线抬升 → 入队返回 queue_position。
cancel：终态不可取消；queued 直接置 cancelled；running 取消引擎协程。
get：任务详情 + 队列位置。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.errors import (
    not_found,
    task_busy,
    task_not_cancellable,
    task_queue_full,
)
from app.core.logging import get_logger
from app.core.redis import set_ws_seq_if_greater
from app.core.uuid import uuid7_str
from app.domains.task.queue import task_queue
from app.domains.task.state_machine import TERMINAL, transition
from app.models.business import AnalysisTask, Attachment, Conversation, Message

logger = get_logger("task.service")


async def _next_seq(db, conv_id: str) -> int:
    for _ in range(5):
        cur = (await db.execute(
            select(func.max(Message.seq_no)).where(Message.conversation_id == conv_id)
        )).scalar()
        nxt = (cur or 0) + 1
        try:
            m = Message(
                id=uuid7_str(),
                conversation_id=conv_id,
                role="user",
                message_type="text",
                content="",  # 由调用方填充
                seq_no=nxt,
            )
            db.add(m)
            await db.flush()
            return nxt
        except Exception:
            await db.rollback()
    raise task_queue_full()  # 极端并发冲突兜底


async def send(
    db, user_id: str, conv_id: str, content: str, attachment_ids: list[str] | None
) -> dict[str, Any]:
    conv = (await db.execute(select(Conversation).where(Conversation.id == conv_id))).scalar_one_or_none()
    if conv is None or conv.user_id != user_id:
        raise not_found("会话")

    # 1. 互斥：会话无 queued/running 任务
    running = (await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.conversation_id == conv_id,
            AnalysisTask.task_status.in_(["queued", "running"]),
        )
    )).scalars().first()
    if running is not None:
        raise task_busy(running.id)

    # 2. user 消息落库（seq_no = MAX+1）
    seq_no = await _next_seq(db, conv_id)
    msg = (
        await db.execute(select(Message).where(Message.conversation_id == conv_id, Message.seq_no == seq_no))
    ).scalar_one_or_none()
    assert msg is not None
    msg.content = content
    msg.created_at = datetime.now(timezone.utc)

    # 3. 关联附件
    if attachment_ids:
        atts = (await db.execute(select(Attachment).where(Attachment.id.in_(attachment_ids)))).scalars().all()
        for a in atts:
            if a.conversation_id == conv_id:
                a.message_id = msg.id

    # 4. analysis_task 落库
    task = AnalysisTask(
        id=uuid7_str(),
        conversation_id=conv_id,
        user_id=user_id,
        input_text=content,
        task_status="queued",
    )
    db.add(task)
    conv.last_message_at = datetime.now(timezone.utc)
    await db.commit()

    # 5. WS seq 基线抬升
    await set_ws_seq_if_greater(conv_id, seq_no)

    # 6. 入队
    try:
        queue_position = await task_queue.put(task.id)
    except Exception:
        raise task_queue_full()

    return {"message_id": msg.id, "task_id": task.id, "queue_position": queue_position}


async def cancel(user_id: str, task_id: str) -> str:
    async with SessionLocal() as db:
        task = (await db.get(AnalysisTask, task_id))
        if task is None:
            raise not_found("任务")
        if task.user_id != user_id:
            raise not_found("任务")
        if task.task_status in TERMINAL:
            raise task_not_cancellable(task_id)

        if task.task_status == "queued":
            transition(task.task_status, "cancelled")
            task.task_status = "cancelled"
            task.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return "cancelled"

        # running：取消引擎协程 + 状态置 cancelled
        transition(task.task_status, "cancelled")
        task.task_status = "cancelled"
        task.finished_at = datetime.now(timezone.utc)
        await db.commit()
    # 取消运行中的协程（若已在 worker 中执行）
    rt = task_queue._running.get(task_id)
    if rt is not None:
        rt.cancel()
    return "cancelled"


async def get(user_id: str, task_id: str) -> dict[str, Any]:
    async with SessionLocal() as db:
        task = (await db.get(AnalysisTask, task_id))
        if task is None or task.user_id != user_id:
            raise not_found("任务")
        qpos = None
        if task.task_status == "queued":
            qpos = task_queue._queue.qsize()  # 近似位置
        return {
            "task_id": task.id,
            "task_status": task.task_status,
            "current_step": task.current_step,
            "queue_position": qpos,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "error_message": task.error_message,
        }
