"""WS 网关（§4.6 / §7）。

- ConnectionManager：conversation_id -> set[WebSocket]。
- push_event：构建统一信封并广播。业务事件(seq=True)走 Redis INCR ws:seq:{conv_id}
  （§7.1.2 per-conversation 单调递增，断线用 REST 补偿）；控制消息(如 ping)不带 seq。
- /api/ws：一次性令牌(WebSocketToken)校验后接受连接；心跳保活；断线清理。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.core.redis import incr_ws_seq
from app.core.uuid import uuid7_str
from app.models.business import WebSocketToken

logger = get_logger("ws")

router = APIRouter(tags=["ws"])


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, conv_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.setdefault(conv_id, set()).add(ws)

    async def disconnect(self, conv_id: str, ws: WebSocket) -> None:
        async with self._lock:
            s = self._conns.get(conv_id)
            if s:
                s.discard(ws)
                if not s:
                    self._conns.pop(conv_id, None)

    async def send(self, conv_id: str, envelope: dict) -> None:
        for ws in list(self._conns.get(conv_id, set())):
            try:
                await ws.send_json(envelope)
            except Exception:  # pragma: no cover
                await self.disconnect(conv_id, ws)

    def has(self, conv_id: str) -> bool:
        return bool(self._conns.get(conv_id))

    async def ping_all(self, interval: int = 30) -> None:
        """心跳：定时向所有连接发送控制 ping（不带 seq）。"""
        while True:
            await asyncio.sleep(interval)
            ping = {"v": 1, "type": "ping", "ts": datetime.now(timezone.utc).isoformat()}
            async with self._lock:
                targets = [ws for s in self._conns.values() for ws in s]
            for ws in targets:
                try:
                    await ws.send_json(ping)
                except Exception:  # pragma: no cover
                    pass


manager = ConnectionManager()


async def push_event(
    conversation_id: str,
    msg_type: str,
    payload: dict,
    task_id: str | None = None,
    seq: bool = True,
) -> None:
    """构建统一信封并广播。seq=True 分配 per-conversation 递增 seq（§7.1.2）。"""
    envelope = {
        "v": 1,
        "type": msg_type,
        "conversation_id": conversation_id,
        "task_id": task_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    if seq:
        try:
            envelope["seq"] = await incr_ws_seq(conversation_id)
        except Exception:  # pragma: no cover - redis 不可用时降级为无 seq
            logger.warning("WS seq 分配失败（redis 不可用），降级为无 seq 广播")
    await manager.send(conversation_id, envelope)


@router.websocket("/api/ws")
async def ws_endpoint(
    ws: WebSocket,
    token: str = Query(...),
    conversation_id: str = Query(...),
):
    # 一次性令牌校验
    async with AsyncSessionLocal() as db:
        rec = (await db.execute(
            select(WebSocketToken).where(WebSocketToken.token == token))
        ).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if (
            rec is None
            or rec.conversation_id != conversation_id
            or rec.expires_at < now
            or rec.consumed_at is not None
        ):
            await ws.close(code=4401)
            return
        rec.consumed_at = now
        await db.commit()

    await ws.accept()
    await manager.connect(conversation_id, ws)
    try:
        while True:
            data = await ws.receive_text()
            # 客户端心跳回执 / 控制消息（如 pong），服务端忽略业务处理
            if data.strip().lower() == "pong":
                continue
    except WebSocketDisconnect:
        await manager.disconnect(conversation_id, ws)
    except Exception:  # pragma: no cover
        await manager.disconnect(conversation_id, ws)
