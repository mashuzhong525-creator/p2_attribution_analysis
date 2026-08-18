"""分析任务状态机与日志。"""

from .utils import now_iso

ALLOWED = {
    "queued": {"running", "cancelled"},
    "running": {"success", "failed", "cancelled"},
    "success": set(),
    "failed": set(),
    "cancelled": set(),
}
STEP_TEXT = {"running": "执行中", "success": "已完成", "failed": "失败", "cancelled": "已取消"}


def log_task(conn, task_id: int, level: str, log_type: str, content: str) -> None:
    conn.execute(
        "INSERT INTO task_logs(task_id,log_level,log_type,log_content,created_at) VALUES(?,?,?,?,?)",
        (task_id, level, log_type, content, now_iso()),
    )


def create_task(conn, conversation_id: int, user_id: int, input_text: str) -> int:
    running = conn.execute(
        "SELECT COUNT(*) c FROM analysis_tasks WHERE conversation_id=? AND task_status IN ('queued','running')",
        (conversation_id,),
    ).fetchone()["c"]
    if running:
        raise ValueError("同一会话已有运行中的任务")
    cur = conn.execute(
        "INSERT INTO analysis_tasks(conversation_id,user_id,input_text,task_status,current_step,created_at) VALUES(?,?,?,?,?,?)",
        (conversation_id, user_id, input_text, "queued", "等待执行", now_iso()),
    )
    log_task(conn, cur.lastrowid, "INFO", "task", "任务创建")
    return cur.lastrowid


def transition(conn, task_id: int, new_status: str) -> None:
    row = conn.execute("SELECT task_status FROM analysis_tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        raise ValueError("任务不存在")
    if new_status not in ALLOWED.get(row["task_status"], set()):
        raise ValueError(f"非法状态迁移: {row['task_status']} -> {new_status}")
    now = now_iso()
    conn.execute(
        "UPDATE analysis_tasks SET task_status=?, current_step=?, started_at=COALESCE(started_at,?), finished_at=?, updated_at=? WHERE id=?",
        (new_status, STEP_TEXT.get(new_status, new_status), now if new_status == "running" else None, now if new_status in ("success", "failed", "cancelled") else None, now, task_id),
    )
    log_task(conn, task_id, "INFO", "task", f"状态变更为 {new_status}")


def mark_failed(conn, task_id: int, error: str) -> None:
    conn.execute(
        "UPDATE analysis_tasks SET task_status='failed', current_step='失败', finished_at=?, error_message=? WHERE id=?",
        (now_iso(), str(error)[:500], task_id),
    )
    log_task(conn, task_id, "ERROR", "task", str(error)[:500])


def list_tasks(conn, task_id: int | None = None, conversation_id: int | None = None) -> list[dict]:
    sql = "SELECT * FROM analysis_tasks WHERE 1=1"
    params: list = []
    if task_id:
        sql += " AND id=?"
        params.append(task_id)
    if conversation_id:
        sql += " AND conversation_id=?"
        params.append(conversation_id)
    sql += " ORDER BY id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
