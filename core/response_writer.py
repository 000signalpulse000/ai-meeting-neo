from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ALLOWED_TARGETS = {"chatgpt", "gemini", "grok", "openclaw", "cursor"}

# 返答・インデックスの JSON は UTF-8（BOM なし）。ingest 元は OS 依存のため下記で判別する。


def read_text_file_for_ingest(path: Path) -> str:
    """
    手動で置かれた返答テキストを読む。
    UTF-16 (BOM) / UTF-8（BOM あり・なし）/ Windows 日本語 ANSI (cp932) を判別する。
    書き出し側は常に UTF-8（BOM なし）で統一する（write_response）。
    """
    raw = path.read_bytes()
    if not raw:
        return ""

    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be")

    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    try:
        return raw.decode("cp932")
    except UnicodeDecodeError:
        pass

    return raw.decode("utf-8", errors="replace")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
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


def write_response(
    project_root: Path,
    task_id: str,
    target: str,
    response_text: str,
    safe_mode: bool = True,
) -> dict[str, Any]:
    task_id = str(task_id).strip()
    target = str(target).strip().lower()

    if not task_id:
        return {"ok": False, "message": "task_id_required"}
    if target not in ALLOWED_TARGETS:
        return {"ok": False, "message": "invalid_target"}
    if not str(response_text).strip():
        return {"ok": False, "message": "empty_response_text"}

    responses_dir = project_root / "output" / "responses" / task_id
    response_path = responses_dir / f"response_{target}.md"
    index_path = project_root / "data" / "responses_index.json"

    responses_dir.mkdir(parents=True, exist_ok=True)
    # UTF-8 BOM なし（リポジトリ・差分・他ツールと整合）
    response_path.write_text(
        str(response_text).strip() + "\n",
        encoding="utf-8",
        newline="\n",
    )

    index = _load_json(
        index_path,
        {
            "schema_version": 1,
            "safe_mode": True,
            "items": [],
        },
    )

    items = index.get("items", [])
    if not isinstance(items, list):
        items = []

    item = {
        "task_id": task_id,
        "target": target,
        "response_path": str(response_path.relative_to(project_root)),
        "updated_at": _now_iso(),
        "safe_mode": bool(safe_mode),
    }

    replaced = False
    for i, old in enumerate(items):
        if old.get("task_id") == task_id and old.get("target") == target:
            items[i] = item
            replaced = True
            break
    if not replaced:
        items.append(item)

    index["schema_version"] = 1
    index["safe_mode"] = True
    index["items"] = items
    _save_json(index_path, index)

    return {
        "ok": True,
        "message": "response_saved",
        "task_id": task_id,
        "target": target,
        "response_path": str(response_path),
        "index_path": str(index_path),
    }


def write_response_from_file(
    project_root: Path,
    task_id: str,
    target: str,
    source_file: Path,
    safe_mode: bool = True,
) -> dict[str, Any]:
    if not source_file.exists():
        return {"ok": False, "message": "source_file_not_found"}
    text = read_text_file_for_ingest(source_file)
    return write_response(
        project_root=project_root,
        task_id=task_id,
        target=target,
        response_text=text,
        safe_mode=safe_mode,
    )
