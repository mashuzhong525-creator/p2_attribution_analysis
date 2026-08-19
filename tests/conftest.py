"""pytest 公共配置：确保项目根目录在 sys.path，测试可直接 import app.*。

basetemp 动态分配唯一目录：规避两处本机环境问题——
1) Windows 系统 Temp 下 pytest-of-{user} 目录 ACL 异常导致 tmp_path fixture 失败；
2) WorkBuddy 安全钩子拦截对已存在 basetemp 目录的 rmtree 清理（trash 失败抛错）。
每次运行分配全新短路径目录（如 Temp/biapt-<随机>），pytest 创建即用、无需清理。
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """为本次会话分配唯一 basetemp（在系统 Temp 下，短路径避免长路径前缀问题）。"""
    base = Path(tempfile.gettempdir()) / f"biapt-{uuid.uuid4().hex[:8]}"
    config.option.basetemp = str(base)
