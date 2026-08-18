"""file_read 工具（§4.7）。读取工作区/上传目录文本文件，≤1MB。"""
from __future__ import annotations

from pathlib import Path

from app.domains.agent.tools.paths import safe_resolve
from app.domains.agent.tools.registry import Tool, ToolContext, ToolResult

MAX_BYTES = 1_048_576


class FileReadTool(Tool):
    name: str = "file_read"
    description: str = "读取当前会话工作区或上传目录中的文本文件内容（≤1MB）。"
    parameters: dict = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "相对工作区的文件路径"}},
        "required": ["path"],
    }
    flag_key: str | None = "flag_tool_file_read"

    async def execute(self, ctx: ToolContext, path: str) -> ToolResult:  # type: ignore[override]
        try:
            p: Path = safe_resolve(ctx.user_id, ctx.conversation_id, path)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
        if not p.exists() or not p.is_file():
            return ToolResult(success=False, error="文件不存在")
        if p.stat().st_size > MAX_BYTES:
            return ToolResult(success=False, error="文件超过 1MB 读取上限")
        text = p.read_text(encoding="utf-8", errors="replace")
        return ToolResult(success=True, summary=f"已读取 {len(text)} 字符", data=text)
