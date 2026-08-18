"""通用工具函数。"""

from datetime import datetime


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
