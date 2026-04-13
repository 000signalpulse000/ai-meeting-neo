"""パス・定数の集中管理。"""
from __future__ import annotations

import os
from pathlib import Path

# プロジェクトルート（このファイルから 1 つ上）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

_DEFAULT_DATA = PROJECT_ROOT / "data"


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", _DEFAULT_DATA)).resolve()


def max_turns() -> int:
    return 6


def safe_mode_default() -> bool:
    """永続化される既定。危険な自動実行は行わない（準備モード）。"""
    v = os.environ.get("SAFE_MODE", "").strip().lower()
    if v in ("0", "false", "no"):
        return False
    return True
