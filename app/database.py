"""SQLite 数据库：业务表 + 演示场景表。"""

import sqlite3
from contextlib import contextmanager

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_user_id TEXT,
    username TEXT UNIQUE NOT NULL,
    password TEXT,
    display_name TEXT,
    role TEXT DEFAULT 'user',
    status TEXT DEFAULT 'active',
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT,
    status TEXT DEFAULT 'active',
    last_message_at TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT,
    message_type TEXT DEFAULT 'text',
    content TEXT,
    tool_name TEXT,
    tool_status TEXT,
    seq_no INTEGER DEFAULT 1,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    message_id INTEGER,
    file_name TEXT,
    file_path TEXT,
    file_type TEXT,
    file_size INTEGER DEFAULT 0,
    parse_status TEXT DEFAULT 'uploaded',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS analysis_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    input_text TEXT,
    task_status TEXT DEFAULT 'queued',
    current_step TEXT DEFAULT '等待执行',
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    conversation_id INTEGER NOT NULL,
    problem_definition TEXT,
    key_metrics_json TEXT DEFAULT '[]',
    evidence_list_json TEXT DEFAULT '[]',
    conclusion_text TEXT,
    missing_data_text TEXT,
    next_action_text TEXT DEFAULT '[]',
    result_markdown TEXT,
    result_file_path TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS context_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    start_seq_no INTEGER,
    end_seq_no INTEGER,
    summary_text TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS websocket_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    conversation_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at INTEGER,
    consumed_at TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS system_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT UNIQUE NOT NULL,
    config_value TEXT,
    config_group TEXT DEFAULT 'general',
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    log_level TEXT DEFAULT 'INFO',
    log_type TEXT,
    log_content TEXT,
    created_at TEXT
);
-- 演示场景一：库存异常分析
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT, warehouse_id TEXT, stock_qty REAL, period TEXT
);
CREATE TABLE IF NOT EXISTS inbound (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT, warehouse_id TEXT, in_qty REAL, in_date TEXT
);
CREATE TABLE IF NOT EXISTS outbound (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT, warehouse_id TEXT, out_qty REAL, out_date TEXT
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT, date TEXT, sales_qty REAL, amount REAL
);
-- 演示场景二：客户行为分析
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT, register_date TEXT, region TEXT, channel TEXT
);
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT, page TEXT, event_time TEXT
);
CREATE TABLE IF NOT EXISTS add_to_cart (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT, sku_id TEXT, event_time TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT, user_id TEXT, sku_id TEXT, order_time TEXT, amount REAL
);
"""


def get_connection() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
