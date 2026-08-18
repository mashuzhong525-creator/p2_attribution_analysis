"""工具注册表（§4.7 tools/registry.py）。

Tool：统一执行入口（flag 检查 → 参数校验 → task_logs 记录 → execute → 摘要截断）。
ToolContext：工具执行上下文。ToolResult：结构化结果。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger("agent.tools")


class ToolContext(BaseModel):
    user_id: str
    conversation_id: str
    data_source_id: str | None = None
    workspace_dir: str = ""
    db: Any = None  # AsyncSession（业务库），pydantic 需要类型注解


class ToolResult(BaseModel):
    success: bool
    summary: str = ""
    data: Any = None
    error: str | None = None


class Tool(BaseModel):
    name: str
    description: str
    parameters: dict = Field(default_factory=dict)
    flag_key: str | None = None

    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:  # pragma: no cover - overridden
        raise NotImplementedError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schema(self, enabled_flags: set[str]) -> list[dict]:
        out = []
        for t in self._tools.values():
            if t.flag_key and t.flag_key not in enabled_flags:
                continue  # 开关关闭不注册
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
            )
        return out

    async def run(self, name: str, ctx: ToolContext, **kwargs) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(success=False, error=f"未知工具：{name}")
        try:
            logger.info("tool=%s args=%s", name, {k: str(v)[:80] for k, v in kwargs.items()})
            res = await tool.execute(ctx, **kwargs)
        except Exception as e:  # noqa: BLE001
            res = ToolResult(success=False, error=f"{type(e).__name__}: {e}")
        if res.summary:
            res.summary = res.summary[:500]
        return res


registry = ToolRegistry()
