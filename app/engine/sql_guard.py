"""SQL 只读安全校验。"""

import re

BLOCKED_KEYWORDS = (
    "delete",
    "update",
    "insert",
    "drop",
    "alter",
    "attach",
    "detach",
    "pragma",
    "vacuum",
    "reindex",
    "create",
    "replace",
    "rollback",
    "begin",
    "commit",
    "transaction",
    "grant",
    "revoke",
)


def validate_select(sql: str) -> str:
    raw = sql or ""
    if not re.match(r"^\s*select\b", raw.lower()):
        raise ValueError("只允许 SELECT 查询")
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", raw.lower()):
            raise ValueError(f"检测到写操作关键字：{kw}")
    cleaned = re.sub(r"--[^\n]*", "", raw)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.S)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) > 1:
        raise ValueError("只允许单条语句")
    return statements[0]
