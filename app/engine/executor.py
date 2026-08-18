"""SQL 执行（只读连接）与失败自愈。"""

import sqlite3

from ..config import settings
from .sql_guard import validate_select


def run_query(sql: str, db_path=None) -> dict:
    validate_select(sql)
    path = db_path or settings.db_path
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = [dict(r) for r in cur.fetchmany(settings.max_result_rows + 1)]
        truncated = len(rows) > settings.max_result_rows
        return {"rows": rows[: settings.max_result_rows], "columns": columns, "truncated": truncated}
    finally:
        conn.close()


def execute_with_retry(sql: str, exec_fn=None, fix_fn=None) -> dict:
    exec_fn = exec_fn or run_query
    try:
        return exec_fn(sql)
    except Exception as e:  # noqa: BLE001
        if fix_fn is None:
            raise
        fixed = fix_fn(str(e), sql)
        return exec_fn(fixed)
