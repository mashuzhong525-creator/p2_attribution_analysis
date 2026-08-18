"""一次性 WebSocket token。"""

import secrets
import time

from .utils import now_iso


def issue_ws_token(conn, user_id: int, conversation_id: int, ttl: int = 300) -> str:
    token = secrets.token_hex(16)
    conn.execute(
        "INSERT INTO websocket_tokens(user_id,conversation_id,token,expires_at,consumed_at,created_at) VALUES(?,?,?,?,?,?)",
        (user_id, conversation_id, token, int(time.time()) + ttl, None, now_iso()),
    )
    return token


def consume_ws_token(conn, token: str, user_id: int, conversation_id: int) -> bool:
    row = conn.execute(
        "SELECT id, consumed_at, expires_at, user_id, conversation_id FROM websocket_tokens WHERE token=?",
        (token,),
    ).fetchone()
    if row is None:
        return False
    if row["consumed_at"] is not None or row["expires_at"] < time.time():
        return False
    if row["user_id"] != user_id or row["conversation_id"] != conversation_id:
        return False
    conn.execute("UPDATE websocket_tokens SET consumed_at=? WHERE id=?", (now_iso(), row["id"]))
    return True
