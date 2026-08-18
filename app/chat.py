"""会话 / 消息 / 附件。"""

from .utils import now_iso


def create_conversation(conn, user_id: int, title: str) -> int:
    now = now_iso()
    cur = conn.execute(
        "INSERT INTO conversations(user_id,title,status,created_at,updated_at) VALUES(?,?,?,?,?)",
        (user_id, title or "新会话", "active", now, now),
    )
    return cur.lastrowid


def list_conversations(conn, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(conn, conversation_id: int, user_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)
    ).fetchone()
    return dict(row) if row else None


def update_conversation(conn, conversation_id: int, user_id: int, title: str) -> bool:
    cur = conn.execute(
        "UPDATE conversations SET title=?, updated_at=? WHERE id=? AND user_id=?",
        (title, now_iso(), conversation_id, user_id),
    )
    return cur.rowcount > 0


def delete_conversation(conn, conversation_id: int, user_id: int) -> list[str]:
    """级联删除消息/附件/任务/结果/摘要，返回附件目录路径（用于清理文件）。"""
    conv = get_conversation(conn, conversation_id, user_id)
    if conv is None:
        return []
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
    rows = conn.execute("SELECT file_path FROM attachments WHERE conversation_id=?", (conversation_id,)).fetchall()
    paths = [r["file_path"] for r in rows]
    conn.execute("DELETE FROM attachments WHERE conversation_id=?", (conversation_id,))
    conn.execute("DELETE FROM analysis_tasks WHERE conversation_id=?", (conversation_id,))
    conn.execute("DELETE FROM analysis_results WHERE conversation_id=?", (conversation_id,))
    conn.execute("DELETE FROM context_summaries WHERE conversation_id=?", (conversation_id,))
    conn.execute("DELETE FROM websocket_tokens WHERE conversation_id=?", (conversation_id,))
    conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
    return paths


def add_message(conn, conversation_id: int, role: str, message_type: str, content: str, tool_name: str | None = None, tool_status: str | None = None) -> int:
    seq = conn.execute("SELECT COALESCE(MAX(seq_no),0)+1 s FROM messages WHERE conversation_id=?", (conversation_id,)).fetchone()["s"]
    cur = conn.execute(
        "INSERT INTO messages(conversation_id,role,message_type,content,tool_name,tool_status,seq_no,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (conversation_id, role, message_type, content, tool_name, tool_status, seq, now_iso()),
    )
    conn.execute("UPDATE conversations SET last_message_at=? WHERE id=?", (now_iso(), conversation_id))
    return cur.lastrowid


def list_messages(conn, conversation_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY seq_no", (conversation_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def add_attachment(conn, conversation_id: int, file_name: str, file_path: str, file_type: str, file_size: int) -> int:
    cur = conn.execute(
        "INSERT INTO attachments(conversation_id,file_name,file_path,file_type,file_size,parse_status,created_at) VALUES(?,?,?,?,?,?,?)",
        (conversation_id, file_name, file_path, file_type, file_size, "uploaded", now_iso()),
    )
    return cur.lastrowid


def list_attachments(conn, conversation_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM attachments WHERE conversation_id=? ORDER BY id", (conversation_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_attachment(conn, attachment_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM attachments WHERE id=?", (attachment_id,)).fetchone()
    return dict(row) if row else None
