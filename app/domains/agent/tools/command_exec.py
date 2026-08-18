"""command_exec 工具（§4.7）。白名单命令（python3），subprocess 沙箱 + 超时截断。"""
from __future__ import annotations

import asyncio

from app.core.config import ConfigCache
from app.domains.agent.tools.registry import Tool, ToolContext, ToolResult

_ALLOWED = {"python3", "python"}
_BLACKLIST = ["rm", "shutdown", "reboot", "mkfs", "dd", "curl", "wget", ":()", "sudo"]


class CommandExecTool(Tool):
    name: str = "command_exec"
    description: str = "在会话工作区内执行白名单命令（仅 python3 数据分析），受限超时与输出截断。"
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "命令名，仅允许 python3"},
            "args": {"type": "array", "items": {"type": "string"}, "description": "参数列表"},
        },
        "required": ["command"],
    }
    flag_key: str | None = "flag_tool_command_exec"

    async def execute(self, ctx: ToolContext, command: str, args: list[str] | None = None) -> ToolResult:  # type: ignore[override]
        args = args or []
        if command not in _ALLOWED:
            return ToolResult(success=False, error="仅允许 python3 命令")
        for a in args:
            if any(bad in a for bad in _BLACKLIST):
                return ToolResult(success=False, error="参数包含禁止关键词")
        timeout = ConfigCache().get_int("cmd_timeout_seconds", 60)
        max_bytes = ConfigCache().get_int("cmd_output_max_bytes", 65536)
        try:
            proc = await asyncio.create_subprocess_exec(
                command, *args,
                cwd=ctx.workspace_dir or ".",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3)
                except asyncio.TimeoutError:
                    proc.kill()
                return ToolResult(success=False, error=f"命令超时（>{timeout}s）已终止")
            text = (out or b"").decode("utf-8", "replace")
            if len(text.encode("utf-8")) > max_bytes:
                text = text[:max_bytes] + "\n...[输出已截断]"
            return ToolResult(success=True, summary=f"命令退出码 {proc.returncode}", data=text)
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, error=f"命令执行失败：{e}")
