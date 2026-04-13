"""データディレクトリの単一実行ロック（残存検知用）。外部実行は行わない。"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def lock_path(data_dir: Path) -> Path:
    return data_dir / "run.lock"


@contextmanager
def acquire_run_lock(data_dir: Path) -> Iterator[None]:
    """
    会議・総監督・計画などの処理区間でロックを取得する。
    正常終了時に解除。異常終了時は run.lock が残り、起動時整合性チェックで検出する。
    """
    path = lock_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    # 既存チェックは integrity 側。ここでは作成のみ試みる。
    if path.exists():
        raise RuntimeError(
            f"run.lock が既に存在します: {path}\n"
            "前回の異常終了か並列実行の可能性があります。手動で確認後に削除してください。"
        )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        yield
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
