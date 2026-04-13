"""最大ターン数の固定と到達判定。"""
from __future__ import annotations

from config import settings


def get_max_turns() -> int:
    return settings.max_turns()


def can_run_another_turn(current_turn: int) -> bool:
    """current_turn は「完了済みターン数」。max_turns 到達なら False。"""
    return current_turn < get_max_turns()


def is_at_supervisor_pause(current_turn: int) -> bool:
    return current_turn >= get_max_turns()
