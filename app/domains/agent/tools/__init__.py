"""Agent 工具包（§4.7）。

注册入口：register_all() 将所有工具实例挂载到全局 registry。
引擎通过 registry.schema(enabled_flags) 获取当前可用工具清单，registry.run() 执行。
"""
from __future__ import annotations

from app.domains.agent.tools.registry import registry
from app.domains.agent.tools.db_query import DbQueryTool
from app.domains.agent.tools.file_read import FileReadTool
from app.domains.agent.tools.file_write import FileWriteTool
from app.domains.agent.tools.text_search import TextSearchTool
from app.domains.agent.tools.command_exec import CommandExecTool


def register_all() -> None:
    """将全部工具注册进全局 registry（幂等）。"""
    for t in (
        DbQueryTool(),
        FileReadTool(),
        FileWriteTool(),
        TextSearchTool(),
        CommandExecTool(),
    ):
        if t.name not in registry._tools:  # noqa: SLF001
            registry.register(t)


# 模块导入即注册（main.lifespan 亦会显式调用一次，保证幂等）
register_all()
