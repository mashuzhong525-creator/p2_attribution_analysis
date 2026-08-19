"""结果导出（2.1.13 验收第 6 条）。

导出目录规范（对齐 2.1.8 / PRD 9.4）：
    exports/{user_id}/{conversation_id}/attribution_{result_id}.md

纯文件逻辑，不依赖 DB；路由层负责鉴权与落库。
"""
from __future__ import annotations

from pathlib import Path


def export_filename(result_id: str) -> str:
    return f"attribution_{result_id}.md"


def write_export_markdown(
    root: Path,
    user_id: str,
    conversation_id: str,
    result_id: str,
    markdown: str,
) -> Path:
    """把六段式 Markdown 写入导出目录，返回落盘路径（幂等：同名覆盖）。"""
    dest = (
        Path(root)
        / user_id
        / conversation_id
        / export_filename(result_id)
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(markdown, encoding="utf-8")
    return dest
