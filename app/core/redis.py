"""Redis 助手：WS seq 分配 / 基线对齐 / 分布式锁。

§7.1.2：消息落库后抬升 seq 基线，防重启回卷。redis 开启 appendonly + 数据卷。
"""
from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings


redis_client: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
)


def _seq_key(conversation_id: str) -> str:
    return f"ws:seq:{conversation_id}"


async def incr_ws_seq(conversation_id: str) -> int:
    """业务事件分配递增 seq（从 1 起）。"""
    return await redis_client.incr(_seq_key(conversation_id))


async def set_ws_seq_if_greater(conversation_id: str, seq: int) -> None:
    """消息落库后抬升基线：当前值 < seq 则 SET。"""
    key = _seq_key(conversation_id)
    cur = await redis_client.get(key)
    if cur is None or int(cur) < seq:
        await redis_client.set(key, seq)


async def ensure_seq_baseline(conversation_id: str, max_seq_in_db: int) -> None:
    """启动惰性对齐：若 Redis 无基线，则设为 DB 中 MAX(seq_no)。"""
    key = _seq_key(conversation_id)
    cur = await redis_client.get(key)
    if cur is None:
        await redis_client.set(key, max(0, max_seq_in_db))


async def acquire_lock(name: str, ttl: int = 1800) -> bool:
    return bool(await redis_client.set(f"lock:{name}", "1", nx=True, ex=ttl))


async def release_lock(name: str) -> None:
    await redis_client.delete(f"lock:{name}")


async def ping() -> bool:
    try:
        return bool(await redis_client.ping())
    except Exception:
        return False
