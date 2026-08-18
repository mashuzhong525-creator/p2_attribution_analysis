"""一次性 WebSocket token：签发、消费、过期。"""

import time

from app.database import get_connection
from app.tokens import consume_ws_token, issue_ws_token


def test_ws_token_is_single_use(db):
    with get_connection() as conn:
        token = issue_ws_token(conn, user_id=1, conversation_id=1, ttl=300)
        assert consume_ws_token(conn, token, user_id=1, conversation_id=1) is True
        assert consume_ws_token(conn, token, user_id=1, conversation_id=1) is False


def test_ws_token_wrong_conversation_rejected(db):
    with get_connection() as conn:
        token = issue_ws_token(conn, user_id=1, conversation_id=1, ttl=300)
        assert consume_ws_token(conn, token, user_id=1, conversation_id=2) is False


def test_ws_token_expired_rejected(db, monkeypatch):
    with get_connection() as conn:
        token = issue_ws_token(conn, user_id=1, conversation_id=1, ttl=300)
    base = time.time()
    monkeypatch.setattr(time, "time", lambda: base + 10000)
    with get_connection() as conn:
        assert consume_ws_token(conn, token, user_id=1, conversation_id=1) is False
