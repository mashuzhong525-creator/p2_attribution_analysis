"""工具开关默认集（§4.7 / 决策：command_exec 默认禁用 + 白名单）。

引擎据此计算「当前启用的工具 flag 集合」，传给 registry.schema(enabled_flags)
决定哪些工具对 LLM 可见、可被执行。
运行时若 system_configs 中存在同名 key，则以配置值覆盖默认。
"""
from __future__ import annotations

from app.core.config import ConfigCache

# 工具 flag_key -> 默认是否启用
DEFAULT_FLAGS: dict[str, bool] = {
    "flag_tool_db_query": True,
    "flag_tool_file_read": True,
    "flag_tool_file_write": True,
    "flag_tool_text_search": True,
    # command_exec 默认禁用（云上安全），需配置开启并配合命令白名单
    "flag_tool_command_exec": False,
}


def enabled_tool_flags() -> set[str]:
    """返回当前启用的工具 flag_key 集合。"""
    cfg = ConfigCache()
    return {k for k, d in DEFAULT_FLAGS.items() if cfg.get_bool(k, d)}
