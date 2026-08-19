"""db_query 工具（§4.7 tools/db_query.py）。

连接会话绑定的数据源（解密密码，只读账号）；SQL 校验链（仅 SELECT、禁多语句/
写操作）→ 强制 LIMIT 500 → asyncio 超时 → 返回 {columns, rows}。
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal

import asyncmy

from app.core.config import ConfigCache
from app.core.errors import data_source_unavailable
from app.core.security import decrypt_secret
from app.domains.agent.tools.registry import Tool, ToolContext, ToolResult

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|"
    r"INTO\s+OUTFILE|LOAD_FILE|LOCK\s+TABLES|UNLOCK\s+TABLES)\b",
    re.IGNORECASE,
)
_MULTI = re.compile(r";\s*\S")


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql.strip()


def _validate(sql: str) -> str:
    s = _strip_comments(sql)
    if not s:
        raise ValueError("空 SQL")
    if not re.match(r"^select\b", s, re.IGNORECASE):
        raise ValueError("仅允许 SELECT 查询")
    if _MULTI.search(s):
        raise ValueError("禁止多语句")
    if _FORBIDDEN.search(s):
        raise ValueError("包含禁止的操作/关键字")
    # 强制 LIMIT 500（无 LIMIT 时追加）
    if not re.search(r"\blimit\b", s, re.IGNORECASE):
        s = f"{s} LIMIT {ConfigCache().get_int('sql_max_rows', 500)}"
    else:
        # 限制上限不超过 sql_max_rows
        m = re.search(r"\blimit\s+(\d+)", s, re.IGNORECASE)
        if m and int(m.group(1)) > ConfigCache().get_int("sql_max_rows", 500):
            s = re.sub(r"\blimit\s+\d+", f"LIMIT {ConfigCache().get_int('sql_max_rows', 500)}", s, flags=re.IGNORECASE)
    return s


async def _connect(ds) -> "asyncmy.Connection":
    try:
        pw = decrypt_secret(ds.password_encrypted)
        conn = await asyncmy.connect(
            host=ds.host,
            port=ds.port,
            user=ds.username,
            password=pw,
            database=ds.database,
            charset="utf8mb4",
        )
        return conn
    except Exception as e:  # noqa: BLE001
        raise data_source_unavailable(f"数据源连接失败：{e}")


class DbQueryTool(Tool):
    name: str = "db_query"
    description: str = (
        "对当前会话绑定的数据源执行只读 SQL 查询，返回行列数据。"
        "SQL 必须以 SELECT 开头、单语句、可含 LIMIT。用于获取业务指标与证据。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "SELECT 查询语句（单表或多表 JOIN 均可）"}
        },
        "required": ["sql"],
    }
    flag_key: str | None = "flag_tool_db_query"

    async def execute(self, ctx: ToolContext, sql: str) -> ToolResult:  # type: ignore[override]
        from sqlalchemy import select

        from app.models.business import DataSource

        if not ctx.data_source_id:
            return ToolResult(success=False, error="当前会话未绑定数据源")
        # 注意：ctx.db 是引擎传入的复用会话，禁止 `async with ctx.db` 否则会提前关闭
        db = ctx.db
        ds = (await db.execute(select(DataSource).where(DataSource.id == ctx.data_source_id))).scalar_one_or_none()
        if ds is None or not ds.is_enabled:
            return ToolResult(success=False, error="数据源不可用")

        try:
            safe_sql = _validate(sql)
        except ValueError as e:
            return ToolResult(success=False, error=f"SQL 校验失败：{e}")

        timeout = ConfigCache().get_int("sql_timeout_seconds", 30)
        conn = None
        try:
            conn = await _connect(ds)
            cur = conn.cursor()
            await cur.execute(safe_sql)
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            # JSON 安全化：datetime/date/time → isoformat 字符串，Decimal → float（否则 WS 推送 TypeError）
            data_rows = [
                [
                    None if v is None
                    else (v.isoformat() if isinstance(v, (datetime, date, time))
                          else (float(v) if isinstance(v, Decimal) else v))
                    for v in r
                ]
                for r in rows
            ]
            summary = f"查询返回 {len(data_rows)} 行，{len(cols)} 列"
            return ToolResult(success=True, summary=summary, data={"columns": cols, "rows": data_rows})
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, error=f"查询执行失败：{e}")
        finally:
            if conn:
                # asyncmy 0.2.x close() 为同步方法（await 会 TypeError）
                conn.close()
