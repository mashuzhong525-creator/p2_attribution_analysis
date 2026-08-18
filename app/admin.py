"""配置热更新与运行日志。"""

from .database import get_connection
from .utils import now_iso

CONFIG_CACHE: dict[str, str] = {}


def load_config() -> dict[str, str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT config_key, config_value FROM system_configs").fetchall()
    CONFIG_CACHE.clear()
    for r in rows:
        CONFIG_CACHE[r["config_key"]] = r["config_value"]
    return dict(CONFIG_CACHE)


def reload_config() -> dict:
    config = load_config()
    return {"status": "ok", "message": "配置已重载", "config": config}


def get_config() -> dict:
    return dict(CONFIG_CACHE) if CONFIG_CACHE else load_config()


def set_config(conn, key: str, value: str, group: str = "general") -> None:
    conn.execute(
        """INSERT INTO system_configs(config_key,config_value,config_group,updated_at)
           VALUES(?,?,?,?)
           ON CONFLICT(config_key) DO UPDATE SET config_value=excluded.config_value, updated_at=excluded.updated_at""",
        (key, value, group, now_iso()),
    )


def list_task_logs(task_id: int | None = None, limit: int = 200) -> list[dict]:
    sql = "SELECT * FROM task_logs"
    params: list = []
    if task_id:
        sql += " WHERE task_id=?"
        params.append(task_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
