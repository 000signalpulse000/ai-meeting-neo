from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


DANGEROUS_KEYWORDS = {
    "delete",
    "remove",
    "shutdown",
    "reboot",
    "format",
    "rm ",
    "rm -",
    "del ",
    "rmdir",
    "exec(",
    "subprocess",
    "os.system",
}

DISPATCH_ENCODING = "utf-8-sig"


@dataclass
class DispatchItem:
    dispatch_id: str
    task_id: str
    task_title: str
    task_status: str
    created_at: str
    output_dir: str
    targets: list[str]


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
        encoding=DISPATCH_ENCODING,
        newline="\n",
    )


def _task_text_for_safety(task: dict[str, Any]) -> str:
    parts = [
        str(task.get("task_id", "")),
        str(task.get("id", "")),
        str(task.get("title", "")),
        str(task.get("goal", "")),
        str(task.get("constraints", "")),
        str(task.get("description", "")),
    ]
    return "\n".join(parts).lower()


def _contains_dangerous_text(task: dict[str, Any]) -> bool:
    text = _task_text_for_safety(task)
    return any(word in text for word in DANGEROUS_KEYWORDS)


def _pick_first_safe_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for task in tasks:
        status = str(task.get("status", "")).lower()
        if status == "completed":
            continue
        if _contains_dangerous_text(task):
            continue
        return task
    return None


def _get_plan_goal(execution_plan: dict[str, Any]) -> str:
    summary = str(execution_plan.get("summary", "")).strip()
    if summary:
        return summary
    return ""


def _get_plan_constraints(task: dict[str, Any]) -> str:
    desc = str(task.get("description", "")).strip()
    if not desc:
        return ""
    marker = "制約"
    if marker in desc:
        return desc.split(marker, 1)[1].strip()
    return desc


def _extract_theme(task: dict[str, Any]) -> str:
    text = "\n".join(
        [
            str(task.get("title", "")).strip(),
            str(task.get("description", "")).strip(),
        ]
    )
    m = re.search(r'テーマ[「"]([^」"\n]+)[」"]', text)
    if m:
        return m.group(1).strip()
    return ""


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _build_cursor_files_to_edit(task: dict[str, Any]) -> list[str]:
    theme = _extract_theme(task)
    files: list[str] = []

    if theme and re.fullmatch(r"idea_[0-9A-Za-z_-]+", theme):
        files.append(f"data/ideas/{theme}.json")

    files.extend(
        [
            "scripts/prepare_idea_run.py",
            "scripts/export_to_memory_hub.py",
        ]
    )

    return _dedupe_keep_order(files)


def _build_cursor_change_plan(task: dict[str, Any], files_to_edit: list[str]) -> list[str]:
    steps: list[str] = []

    if any(path.startswith("data/ideas/") for path in files_to_edit):
        steps.append("Freeze the idea JSON as the single source of truth and keep it valid UTF-8 JSON.")

    steps.extend(
        [
            "Implement prepare_idea_run.py to map the idea JSON into data/input.json without changing the existing meeting flow.",
            "Implement export_to_memory_hub.py to read supervisor_output.json and execution_plan.json, update the idea JSON, and write a memory-hub inbox text.",
            "Keep change scope minimal and local to the files listed below.",
        ]
    )
    return steps


def _build_cursor_completion_criteria(files_to_edit: list[str]) -> list[str]:
    criteria: list[str] = []

    idea_files = [path for path in files_to_edit if path.startswith("data/ideas/")]
    if idea_files:
        criteria.append(f"{idea_files[0]} remains valid UTF-8 JSON after the workflow.")

    criteria.extend(
        [
            "scripts/prepare_idea_run.py can generate data/input.json from the idea JSON.",
            "scripts/export_to_memory_hub.py can read data/supervisor_output.json and data/execution_plan.json and produce a memory-hub inbox text.",
            "task.json and prompt_cursor.md are readable as UTF-8 on Windows.",
            "No network calls, shell execution, or destructive operations are introduced.",
        ]
    )
    return criteria


def _build_cursor_constraints(
    safe_mode: bool,
    plan_constraints: str,
) -> list[str]:
    constraints = [
        f"safe_mode is {'true' if safe_mode else 'false'}",
        "do not execute anything",
        "do not call external tools",
        "do not use network",
        "do not run shell / powershell / subprocess",
        "keep changes minimal and local",
    ]
    if plan_constraints:
        constraints.append(plan_constraints)
    return constraints


def _build_cursor_task(
    task: dict[str, Any],
    safe_mode: bool,
    plan_goal: str,
    plan_constraints: str,
) -> dict[str, Any]:
    files_to_edit = _build_cursor_files_to_edit(task)
    change_plan = _build_cursor_change_plan(task, files_to_edit)
    completion_criteria = _build_cursor_completion_criteria(files_to_edit)
    constraints = _build_cursor_constraints(safe_mode, plan_constraints)

    enriched = dict(task)
    enriched["goal"] = plan_goal
    enriched["files_to_edit"] = files_to_edit
    enriched["change_plan"] = change_plan
    enriched["completion_criteria"] = completion_criteria
    enriched["constraints"] = constraints
    return enriched


def _bullets(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _build_generic_prompt(
    target: str,
    task: dict[str, Any],
    safe_mode: bool,
    plan_goal: str,
    plan_constraints: str,
) -> str:
    task_title = str(task.get("title", "(untitled task)")).strip()
    description = str(task.get("description", "")).strip()
    goal = str(task.get("goal", "")).strip() or plan_goal

    return f"""# AI Dispatch Task

## Target
{target}

## Rule
- safe_mode is {"true" if safe_mode else "false"}
- do not execute anything
- do not call external tools
- do not use network
- do not run shell / powershell / subprocess
- output text only

## Task
{task_title}

## Description
{description}

## Goal
{goal}

## Constraints
{plan_constraints or "(none)"}

## Required Output
- short implementation proposal
- risks
- exact next step
- no code execution
"""


def _build_cursor_prompt(
    task: dict[str, Any],
    safe_mode: bool,
) -> str:
    task_title = str(task.get("title", "(untitled task)")).strip()
    description = str(task.get("description", "")).strip()
    goal = str(task.get("goal", "")).strip()
    files_to_edit = [str(x) for x in task.get("files_to_edit", [])]
    change_plan = [str(x) for x in task.get("change_plan", [])]
    completion_criteria = [str(x) for x in task.get("completion_criteria", [])]
    constraints = [str(x) for x in task.get("constraints", [])]

    return f"""# AI Dispatch Task

## Target
cursor

## Rule
- safe_mode is {"true" if safe_mode else "false"}
- do not execute anything
- do not call external tools
- do not use network
- do not run shell / powershell / subprocess
- output text only

## Task
{task_title}

## Description
{description}

## Goal
{goal}

## Files to Edit
{_bullets(files_to_edit)}

## Change Plan
{_bullets(change_plan)}

## Completion Criteria
{_bullets(completion_criteria)}

## Constraints
{_bullets(constraints)}

## Required Output
- exact file-by-file implementation proposal
- risks
- exact next step
- no code execution
"""


def generate_dispatch_from_execution_plan(project_root: Path, safe_mode: bool = True) -> dict[str, Any]:
    data_dir = project_root / "data"
    output_dir = project_root / "output" / "dispatch"

    execution_plan_path = data_dir / "execution_plan.json"
    dispatch_queue_path = data_dir / "dispatch_queue.json"

    execution_plan = _load_json(execution_plan_path, {})
    tasks = execution_plan.get("tasks", [])

    if not isinstance(tasks, list):
        return {
            "ok": False,
            "message": "execution_plan.tasks_not_found",
            "dispatch_queue_path": str(dispatch_queue_path),
        }

    task = _pick_first_safe_task(tasks)
    if not task:
        result = {
            "schema_version": 1,
            "safe_mode": True,
            "status": "no_safe_task",
            "items": [],
        }
        _save_json(dispatch_queue_path, result)
        return {
            "ok": False,
            "message": "no_safe_task",
            "dispatch_queue_path": str(dispatch_queue_path),
        }

    task_id = str(task.get("task_id") or task.get("id") or "task_001")
    task_title = str(task.get("title") or "Untitled Task")
    task_output_dir = output_dir / task_id
    task_output_dir.mkdir(parents=True, exist_ok=True)

    targets = ["chatgpt", "gemini", "grok", "openclaw", "cursor"]

    dispatch_item = DispatchItem(
        dispatch_id="dispatch_001",
        task_id=task_id,
        task_title=task_title,
        task_status="ready",
        created_at=_now_iso(),
        output_dir=str(task_output_dir.relative_to(project_root)),
        targets=targets,
    )

    plan_goal = _get_plan_goal(execution_plan)
    plan_constraints = _get_plan_constraints(task)

    task_for_output = dict(task)
    if str(task.get("target", "")).lower() == "cursor":
        task_for_output = _build_cursor_task(
            task=task,
            safe_mode=safe_mode,
            plan_goal=plan_goal,
            plan_constraints=plan_constraints,
        )

    _save_json(task_output_dir / "task.json", task_for_output)

    for target in targets:
        prompt_path = task_output_dir / f"prompt_{target}.md"

        if target == "cursor":
            prompt_text = _build_cursor_prompt(
                task=task_for_output,
                safe_mode=safe_mode,
            )
        else:
            prompt_text = _build_generic_prompt(
                target=target,
                task=task,
                safe_mode=safe_mode,
                plan_goal=plan_goal,
                plan_constraints=plan_constraints,
            )

        prompt_path.write_text(
            prompt_text,
            encoding=DISPATCH_ENCODING,
            newline="\n",
        )

    dispatch_queue = {
        "schema_version": 1,
        "safe_mode": True,
        "status": "ready",
        "items": [asdict(dispatch_item)],
    }
    _save_json(dispatch_queue_path, dispatch_queue)

    return {
        "ok": True,
        "message": "dispatch_generated",
        "task_id": task_id,
        "task_title": task_title,
        "dispatch_queue_path": str(dispatch_queue_path),
        "output_dir": str(task_output_dir),
        "targets": targets,
    }
