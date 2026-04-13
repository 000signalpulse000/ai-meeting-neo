"""
export_to_memory_hub.py

Standalone CLI:
    python scripts/export_to_memory_hub.py idea_0002.json

Importable core:
    from scripts.export_to_memory_hub import export_idea
    export_idea(idea_path, data_dir, output_dir, root)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_JSON_ENCODING = "utf-8"
_JSON_READ_ENCODING = "utf-8-sig"


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    with path.open("r", encoding=_JSON_READ_ENCODING) as f:
        return json.load(f)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=_JSON_ENCODING, newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=_JSON_ENCODING, newline="\n")


def _build_decision(sup: dict, plan: dict) -> dict:
    return {
        "recommendation": sup.get("recommendation", ""),
        "adopted_option": sup.get("adopted_option", ""),
        "vote_summary": sup.get("vote_summary", ""),
        "rationale": sup.get("rationale", ""),
        "constraints_aligned": sup.get("constraints_aligned", False),
        "plan_id": plan.get("plan_id", ""),
        "plan_summary": plan.get("summary", ""),
        "decided_at": datetime.now().isoformat(timespec="seconds"),
    }


def _build_artifact_paths(data_dir: Path, plan: dict) -> list[str]:
    paths = [
        str(data_dir / "supervisor_output.json"),
        str(data_dir / "execution_plan.json"),
    ]
    for task in plan.get("tasks", []):
        task_id = task.get("task_id", "")
        if task_id:
            paths.append(f"output/dispatch/{task_id}/task.json")
            paths.append(f"output/dispatch/{task_id}/prompt_cursor.md")
    return paths


def _update_idea(idea: dict, sup: dict, plan: dict, data_dir: Path) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    idea["status"] = "completed"
    idea["updated_at"] = now
    idea["decision"] = _build_decision(sup, plan)
    idea["artifact_paths"] = _build_artifact_paths(data_dir, plan)
    return idea


def _build_export_text(idea: dict, sup: dict, plan: dict) -> str:
    lines = [
        "# memory_hub export",
        f"idea_id: {idea.get('idea_id', '')}",
        f"exported_at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## raw_input",
        idea.get("raw_input", "(empty)"),
        "",
        "## decision",
        f"recommendation : {sup.get('recommendation', '')}",
        f"adopted_option : {sup.get('adopted_option', '')}",
        f"vote_summary   : {sup.get('vote_summary', '')}",
        f"rationale      : {sup.get('rationale', '')}",
        "",
        "## execution_plan tasks",
    ]
    for task in plan.get("tasks", []):
        lines.append(
            f"- [{task.get('target', '')}] {task.get('task_id', '')}: {task.get('title', '')}"
        )
    lines.append("")
    return "\n".join(lines)


def export_idea(
    idea_path: Path,
    data_dir: Path,
    output_dir: Path,
    root: Path,
) -> dict:
    """
    Core export logic. Importable from main.py or other modules.

    Returns a result dict with keys:
        ok, idea_path, idea_status, export_path, memory_hub_written, skip_reason
    """
    sup_path = data_dir / "supervisor_output.json"
    plan_path = data_dir / "execution_plan.json"

    if not sup_path.exists():
        return {"ok": False, "skip_reason": "supervisor_output.json not found"}
    if not plan_path.exists():
        return {"ok": False, "skip_reason": "execution_plan.json not found"}

    idea = _read_json(idea_path)
    sup = _read_json(sup_path)
    plan = _read_json(plan_path)

    idea = _update_idea(idea, sup, plan, data_dir)

    export_text = _build_export_text(idea, sup, plan)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    idea_id = idea.get("idea_id", "unknown")
    export_path = output_dir / f"{idea_id}_{timestamp}.txt"

    idea["artifact_paths"].append(str(export_path))
    _write_json(idea_path, idea)
    _write_text(export_path, export_text)

    memory_hub_written = False
    memory_hub_warn: str = ""
    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from storage.memory_hub import save_idea  # type: ignore[import]
        save_idea(idea_id, idea)
        memory_hub_written = True
    except Exception as exc:
        memory_hub_warn = str(exc)

    return {
        "ok": True,
        "idea_path": str(idea_path),
        "idea_status": idea["status"],
        "export_path": str(export_path),
        "memory_hub_written": memory_hub_written,
        "memory_hub_warn": memory_hub_warn,
        "skip_reason": "",
    }


def _print_result(result: dict) -> None:
    if not result.get("ok"):
        print(f"[export] skipped: {result.get('skip_reason', 'unknown')}")
        return
    print("export_to_memory_hub completed")
    print(f"  idea_path    : {result['idea_path']}")
    print(f"  idea status  : {result['idea_status']}")
    print(f"  export_path  : {result['export_path']}")
    print(f"  memory_hub   : {'written' if result['memory_hub_written'] else 'skipped'}")
    if result.get("memory_hub_warn"):
        print(f"  [warn] memory_hub: {result['memory_hub_warn']}")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data"
    ideas_dir = data_dir / "ideas"
    output_dir = root / "output" / "memory_hub_export"

    idea_filename = sys.argv[1] if len(sys.argv) > 1 else "idea_0001.json"
    idea_path = ideas_dir / idea_filename

    if not idea_path.exists():
        raise FileNotFoundError(f"idea file not found: {idea_path}")

    result = export_idea(idea_path, data_dir, output_dir, root)
    _print_result(result)


if __name__ == "__main__":
    main()
