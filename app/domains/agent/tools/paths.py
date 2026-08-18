"""工具路径安全校验（§4.7）：realpath 必须落在会话允许目录内。"""
from __future__ import annotations

from pathlib import Path

from app.core.errors import BizError


def allowed_roots(user_id: str, conv_id: str) -> list[Path]:
    from app.core.config import settings

    base = Path(settings.DATA_ROOT)
    return [
        base / "workspace" / user_id / conv_id,
        base / "uploads" / user_id / conv_id,
    ]


def safe_resolve(user_id: str, conv_id: str, path: str) -> Path:
    """校验相对路径落在允许根内，返回绝对 Path；越界抛 BizError。"""
    roots = allowed_roots(user_id, conv_id)
    p = (roots[0] / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if not any(str(p).startswith(str(r)) for r in roots):
        raise BizError("PATH_TRAVERSAL", "路径越界访问被拒绝", 400)
    return p
