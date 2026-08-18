"""UUIDv7 生成器。

Python 3.13 stdlib 无 uuid7（3.14 才加），使用 uuid6 包实现时间有序的 UUIDv7。
数据模型约定主键为 VARCHAR(32) 无横线（.hex），可作聚簇索引、防枚举。
"""
from __future__ import annotations

from uuid6 import uuid7


def uuid7_str() -> str:
    """返回 32 位无横线 UUIDv7 字符串。"""
    return uuid7().hex
