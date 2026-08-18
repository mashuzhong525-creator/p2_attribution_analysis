"""file_write 工具（§4.7）。仅工作区内写入，≤5MB。"""
from __future__ import annotations

from pathlib import Path

from app.domains.agent.tools.paths import safe_resolve
from app.domains.agent.tools.registry import Tool, ToolContext, ToolResult

MAX_BYTES = 5_242_880


class FileWriteTool(Tool):
    name: str = "file_write"
    description: str = "在工作区目录内写入文本文件（仅 workspace 根，≤5MB），用于保存中间分析。"
    parameters: dict = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对工作区的文件路径"},
            "content": {"type": "string", "description": "写入内容"},
        },
        "required": ["path", "content"],
    }
    flag_key: str | None = "flag_tool_file_write"

    async def execute(self, ctx: ToolContext, path: str, content: str) -> ToolResult:  # type: ignore[override]
        try:
            p: Path = safe_resolve(ctx.user_id, ctx.conversation_id, path)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
        # 仅允许 workspace 根（非 uploads）
        if "uploads" in str(p):
            return ToolResult(success=False, error="禁止写入上传目录")
        if len(content.encode("utf-8")) > MAX_BYTES:
            return ToolResult(success=False, error="内容超过 5MB 上限")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(success=True, summary=f"已写入 {len(content)} 字符到 {path}")
