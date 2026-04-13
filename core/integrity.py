"""起動時整合性チェック（残存ロック・temp・session_id・スキーマ）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models.meeting_models import SCHEMA_VERSION

_JSON_ENC = "utf-8-sig"

_EXECUTION_TASK_TARGETS = frozenset({"cursor", "openclaw", "chatgpt"})


def _read_json_loose(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding=_JSON_ENC) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def check_startup_integrity(data_dir: Path) -> tuple[list[str], list[str]]:
    """
    (errors, warnings) を返す。
    errors が空でなければ起動を止める想定。自動リカバリ・temp からの再開は行わない。
    """
    errors: list[str] = []
    warnings: list[str] = []

    data_dir = data_dir.resolve()

    lock = data_dir / "run.lock"
    if lock.is_file():
        errors.append(
            f"[ERROR] run.lock が残存: {lock} "
            "(異常終了または並列実行の可能性。確認後に手動削除してください。)"
        )

    for p in data_dir.glob("*.tmp*"):
        if p.is_file():
            errors.append(
                f"[ERROR] 一時ファイルが残存: {p} (自動削除・自動再開はしません。)"
            )

    ms = _read_json_loose(data_dir / "meeting_state.json")
    sid_state: str | None = None
    if ms is not None:
        if not isinstance(ms, dict):
            errors.append("[ERROR] meeting_state.json がオブジェクト形式ではありません。")
        else:
            for k in ("status", "current_turn", "max_turns"):
                if k not in ms:
                    errors.append(f"[ERROR] meeting_state.json に必須キーがありません: {k}")
            sv = ms.get("schema_version")
            if sv is None:
                warnings.append(
                    "[WARN] meeting_state.json に schema_version がありません（旧形式）。"
                    "次回保存時に更新されます。"
                )
            elif sv != SCHEMA_VERSION:
                warnings.append(
                    f"[WARN] meeting_state.json の schema_version が {sv!r}（期待={SCHEMA_VERSION}）。"
                )
            sid_state = ms.get("session_id")
            if not sid_state:
                warnings.append(
                    "[WARN] meeting_state.json に session_id がありません（旧形式）。"
                    "次回会議実行時に付与されます。"
                )

    if sid_state:
        tp = data_dir / "turns.json"
        tr = _read_json_loose(tp)
        if tr is not None:
            if isinstance(tr, list):
                warnings.append("[WARN] turns.json が旧形式（配列のみ）です。")
            elif isinstance(tr, dict):
                tsid = tr.get("session_id")
                if tsid and tsid != sid_state:
                    errors.append(
                        f"[ERROR] turns.json の session_id が meeting_state と不一致 "
                        f"({tsid!r} vs {sid_state!r})。"
                    )
                tsv = tr.get("schema_version")
                if tsv and tsv != SCHEMA_VERSION:
                    warnings.append(
                        f"[WARN] turns.json の schema_version が {tsv!r}。"
                    )

        for name in ("supervisor_input.json", "supervisor_output.json", "execution_plan.json"):
            p = data_dir / name
            d = _read_json_loose(p)
            if isinstance(d, dict) and d.get("session_id") and d.get("session_id") != sid_state:
                errors.append(
                    f"[ERROR] {name} の session_id が meeting_state と不一致。"
                )
            # execution_plan 内 tasks 全要素（session_id / task_id / target / lifecycle）
            if name == "execution_plan.json" and isinstance(d, dict):
                tlist = d.get("tasks")
                if isinstance(tlist, list) and tlist:
                    for i, t in enumerate(tlist):
                        if not isinstance(t, dict):
                            errors.append(
                                f"[ERROR] execution_plan.json tasks[{i}] がオブジェクトではありません。"
                            )
                            continue
                        tsid = t.get("session_id")
                        if sid_state and str(tsid or "") != str(sid_state):
                            errors.append(
                                f"[ERROR] execution_plan.json tasks[{i}].session_id が meeting_state と不一致。"
                            )
                        tid = t.get("task_id")
                        if tid is None or not str(tid).strip():
                            errors.append(
                                f"[ERROR] execution_plan.json tasks[{i}].task_id が空です。"
                            )
                        tgt = t.get("target")
                        if tgt not in _EXECUTION_TASK_TARGETS:
                            errors.append(
                                f"[ERROR] execution_plan.json tasks[{i}].target が不正です: {tgt!r}"
                            )
                        lc = t.get("lifecycle")
                        if lc not in ("draft", "approved"):
                            errors.append(
                                f"[ERROR] execution_plan.json tasks[{i}].lifecycle が不正です: {lc!r}"
                            )

    return errors, warnings
