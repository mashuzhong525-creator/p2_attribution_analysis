"""text_search 工具（§4.7）。检索本会话已解析附件摘要/预览 + 工作区文本文件。"""
from __future__ import annotations

from sqlalchemy import select

from app.domains.agent.tools.registry import Tool, ToolContext, ToolResult
from app.models.business import Attachment


class TextSearchTool(Tool):
    name: str = "text_search"
    description: str = "在本会话已解析附件与上传文本中按关键词检索片段，返回来源与片段。"
    parameters: dict = {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "检索关键词"},
            "limit": {"type": "integer", "description": "返回条数上限（≤20）", "default": 10},
        },
        "required": ["keyword"],
    }
    flag_key: str | None = "flag_tool_text_search"

    async def execute(self, ctx: ToolContext, keyword: str, limit: int = 10) -> ToolResult:  # type: ignore[override]
        limit = min(20, max(1, limit))
        kw = keyword.lower()
        hits: list[dict] = []
        # ctx.db 是引擎复用会话，直接用（不要 async with 关闭）
        db = ctx.db
        atts = (await db.execute(
            select(Attachment).where(
                Attachment.conversation_id == ctx.conversation_id,
                Attachment.parse_status == "parsed",
            )
        )).scalars().all()
        for a in atts:
            pr = a.parse_result_json or {}
            blob = " ".join([
                str(pr.get("summary", "")),
                " ".join(" ".join(map(str, r)) for r in pr.get("preview_rows", [])),
            ]).lower()
            if kw in blob:
                hits.append({
                    "source": f"attachment:{a.file_name}",
                    "snippet": str(pr.get("summary", ""))[:200],
                })
        return ToolResult(
            success=True,
            summary=f"命中 {len(hits)} 处",
            data=hits[:limit],
        )
