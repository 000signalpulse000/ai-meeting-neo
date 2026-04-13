"""data/responses_index.json と output/responses を集約し output/summary/summary.json を生成する。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _resolve_project_relative_path(project_root: Path, rel: str) -> Path:
    normalized = str(rel).replace("\\", "/").strip()
    return (project_root / normalized).resolve()

from core.response_writer import read_text_file_for_ingest


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return default
    return json.loads(text)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


def build_summary(project_root: Path) -> dict[str, Any]:
    index_path = project_root / "data" / "responses_index.json"
    raw = _load_json(
        index_path,
        {"schema_version": 1, "safe_mode": True, "items": []},
    )

    items_in = raw.get("items") if isinstance(raw, dict) else []
    if not isinstance(items_in, list):
        items_in = []

    enriched: list[dict[str, Any]] = []
    for entry in items_in:
        if not isinstance(entry, dict):
            continue
        task_id = entry.get("task_id", "")
        target = entry.get("target", "")
        rel = entry.get("response_path", "")
        row = {
            "task_id": task_id,
            "target": target,
            "response_path": rel,
            "updated_at": entry.get("updated_at"),
            "safe_mode": entry.get("safe_mode"),
            "content": None,
            "content_error": None,
        }
        if rel:
            abs_path = _resolve_project_relative_path(project_root, str(rel))
            try:
                if abs_path.is_file():
                    row["content"] = read_text_file_for_ingest(abs_path)
                else:
                    row["content_error"] = "file_not_found"
            except OSError as e:
                row["content_error"] = str(e)
        enriched.append(row)

    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "source_index": str(index_path.relative_to(project_root)).replace("\\", "/"),
        "safe_mode": bool(raw.get("safe_mode", True)) if isinstance(raw, dict) else True,
        "items": enriched,
    }


def main() -> int:
    root = Path(__file__).resolve().parent
    summary = build_summary(root)
    out = root / "output" / "summary" / "summary.json"
    _save_json(out, summary)
    n = len(summary.get("items", []))
    print(f"Wrote {out.relative_to(root)} ({n} item(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
