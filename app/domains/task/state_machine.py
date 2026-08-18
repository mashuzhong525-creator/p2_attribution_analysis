"""任务状态机（§4.6 state_machine.py）。

queued → running → success/failed/cancelled；终态不可逆。
"""
from __future__ import annotations

from app.core.errors import BizError

VALID_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "failed", "cancelled"},
    "running": {"success", "failed", "cancelled"},
    "success": set(),
    "failed": set(),
    "cancelled": set(),
}

TERMINAL = {"success", "failed", "cancelled"}


def transition(current: str, nxt: str) -> None:
    if nxt == current:
        return
    allowed = VALID_TRANSITIONS.get(current, set())
    if nxt not in allowed:
        raise BizError(
            "INVALID_TRANSITION",
            f"非法状态流转：{current} -> {nxt}",
            409,
        )
