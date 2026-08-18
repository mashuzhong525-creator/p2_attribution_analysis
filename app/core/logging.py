"""结构化日志 + 任务日志落库（task_logs）。

WARN/ERROR 经 log_task 同步写入 task_logs；普通模块日志走标准 logging。
"""
from __future__ import annotations

import logging
import sys

_LEVEL = logging.INFO
_logger = logging.getLogger("bia")
if not _logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    _logger.addHandler(_h)
    _logger.setLevel(_LEVEL)


def get_logger(module: str) -> logging.Logger:
    return logging.getLogger(f"bia.{module}")


async def log_task(
    task_id: str,
    level: str,
    log_type: str,
    content: str,
    db=None,
) -> None:
    """写入 task_logs 表。db 为 AsyncSession；不传则仅打日志。"""
    lvl = (level or "INFO").upper()
    _logger.log(getattr(logging, lvl, logging.INFO), "[task:%s] %s", task_id, content)
    if db is None:
        return
    try:
        from app.db.base import Base  # noqa
        from app.models.business import TaskLog
        from app.core.uuid import uuid7_str

        db.add(
            TaskLog(
                id=uuid7_str(),
                task_id=task_id,
                log_level=lvl,
                log_type=log_type,
                log_content=content,
            )
        )
        await db.commit()
    except Exception:
        _logger.exception("写入 task_logs 失败 task=%s", task_id)
