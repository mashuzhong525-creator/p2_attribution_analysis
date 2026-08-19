"""工具路径安全校验（§4.7）：realpath 必须落在会话允许目录内。"""
from __future__ import annotations

from pathlib import Path

from app.core.errors import BizError


def allowed_roots(user_id: str, conv_id: str) -> list[Path]:
    from app.core.config import settings

    base = Path(settings.DATA_ROOT).resolve()
    return [
        (base / "workspace" / user_id / conv_id).resolve(),
        (base / "uploads" / user_id / conv_id).resolve(),
    ]


def safe_resolve(user_id: str, conv_id: str, path: str) -> Path:
    """校验路径落在允许根内，返回绝对 Path；越界抛 BizError。

    支持三种 path 形式（全部转绝对路径再比对，避免 DATA_ROOT 是相对路径时误拼）：
      1) 相对路径 → 当作相对会话工作区（workspace 根）解析
      2) 绝对路径 → 直接 resolve
      3) 形如 "data/uploads/..." 或 "data/workspace/..." → 当作相对 DATA_ROOT 解析
    """
    roots = allowed_roots(user_id, conv_id)
    raw = Path(path)
    if raw.is_absolute():
        p = raw.resolve()
    else:
        s = str(path).replace("\\", "/")
        # 文件路径以 "data/uploads/..." 或 "data/workspace/..." 开头：相对 DATA_ROOT 解析
        from app.core.config import settings
        base = Path(settings.DATA_ROOT).resolve()
        if s.startswith("data/") or s.startswith("./data/"):
            p = (base / s.removeprefix("./data/").removeprefix("data/")).resolve()
        else:
            # 否则按工作区根解析
            p = (roots[0] / s).resolve()
    if not any(str(p).startswith(str(r)) for r in roots):
        raise BizError("PATH_TRAVERSAL", f"路径越界访问被拒绝 ({p} 不在允许根内)", 400)
    return p
