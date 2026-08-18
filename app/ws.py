"""WebSocket 实时链路：鉴权 + 事件推送。"""

import asyncio
import queue

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .database import db
from .engine.pipeline import run_analysis
from .tokens import consume_ws_token

router = APIRouter()


@router.websocket("/api/chat/ws/chat")
async def chat_ws(websocket: WebSocket, token: str, conversation_id: int):
    await websocket.accept()
    with db() as conn:
        row = conn.execute(
            "SELECT user_id FROM websocket_tokens WHERE token=?", (token,)
        ).fetchone()
        if row is None or not consume_ws_token(conn, token, row["user_id"], conversation_id):
            await websocket.send_json({"event": "error", "error_message": "WebSocket 鉴权失败"})
            await websocket.close(code=4401)
            return
        user_id = row["user_id"]
        user = dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())

    events: queue.Queue = queue.Queue()

    async def pump():
        while True:
            try:
                evt = events.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue
            await websocket.send_json(evt)

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") != "question":
                continue
            question = (data.get("question") or "").strip()
            if not question:
                continue
            await asyncio.to_thread(run_analysis, question, conversation_id, user_id, events.put)
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
