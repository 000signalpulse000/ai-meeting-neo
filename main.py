"""
ai-meeting-neo entry point.
File-only phases only. No external execution.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_summary import build_summary  # noqa: E402
from config.settings import data_dir  # noqa: E402
from core import execution_planner  # noqa: E402
from core import orchestrator  # noqa: E402
from core.ai_dispatcher import generate_dispatch_from_execution_plan  # noqa: E402
from core.chairperson import write_decision  # noqa: E402
from core.integrity import check_startup_integrity  # noqa: E402
from core.response_writer import write_response_from_file  # noqa: E402
from core.run_lock import acquire_run_lock  # noqa: E402
from core.supervisor import run_supervisor_phase  # noqa: E402
from scripts.export_to_memory_hub import export_idea, _print_result  # noqa: E402

_SUPERVISOR_ELIGIBLE_STATUS = "paused_for_supervisor"


def _read_meeting_status(d: Path) -> str:
    """Return the current status from data/meeting_state.json, or '' on any failure."""
    state_path = d / "meeting_state.json"
    if not state_path.exists():
        return ""
    try:
        raw = state_path.read_text(encoding="utf-8-sig")
        return json.loads(raw).get("status", "")
    except Exception:
        return ""


def _get_target_idea_from_input(d: Path) -> Path | None:
    """
    Read data/input.json, extract idea_id, return the resolved idea file path.
    Returns None with a printed reason on any failure.
    """
    input_path = d / "input.json"

    if not input_path.exists():
        print("[export] skipped: data/input.json not found")
        return None

    try:
        raw = input_path.read_text(encoding="utf-8-sig")
        payload = json.loads(raw)
    except Exception as exc:
        print(f"[export] skipped: could not read data/input.json ({exc})")
        return None

    idea_id = payload.get("idea_id", "").strip()
    if not idea_id:
        print("[export] skipped: idea_id is missing in data/input.json")
        return None

    idea_path = d / "ideas" / f"{idea_id}.json"
    if not idea_path.exists():
        print(f"[export] skipped: idea file not found: {idea_path}")
        return None

    return idea_path


def _run_auto_export(d: Path) -> None:
    """Run export_idea if supervisor approved and execution_plan exists."""
    sup_path = d / "supervisor_output.json"
    plan_path = d / "execution_plan.json"

    if not sup_path.exists() or not plan_path.exists():
        print("[export] skipped: supervisor_output.json or execution_plan.json not found")
        return

    try:
        sup = json.loads(sup_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"[export] skipped: could not read supervisor_output.json ({exc})")
        return

    if sup.get("recommendation") != "approve":
        print(f"[export] skipped: recommendation={sup.get('recommendation')} (not approve)")
        return

    idea_path = _get_target_idea_from_input(d)
    if idea_path is None:
        return

    print(f"[export] target idea: {idea_path}")
    output_dir = ROOT / "output" / "memory_hub_export"
    result = export_idea(idea_path, d, output_dir, ROOT)
    _print_result(result)


def _run_dispatch_phase() -> None:
    print("[AUTO] dispatch phase...")
    result = generate_dispatch_from_execution_plan(
        project_root=ROOT,
        safe_mode=True,
    )

    if result.get("ok"):
        print(
            "dispatch done:",
            f"task_id={result.get('task_id')}",
            f"output_dir={result.get('output_dir')}",
        )
    else:
        print("dispatch stopped:", result.get("message"))


def _run_ingest_response_phase(task_id: str, target: str, response_file: str) -> None:
    print("[MANUAL] ingest response phase...")
    result = write_response_from_file(
        project_root=ROOT,
        task_id=task_id,
        target=target,
        source_file=Path(response_file),
        safe_mode=True,
    )

    if result.get("ok"):
        print(
            "ingest done:",
            f"task_id={result.get('task_id')}",
            f"target={result.get('target')}",
            f"response_path={result.get('response_path')}",
        )
    else:
        print("ingest stopped:", result.get("message"))


def _run_build_summary_phase() -> None:
    print("[MANUAL] build summary phase...")
    result = build_summary(project_root=ROOT)
    item_count = len(result.get("items", []))
    print(
        "summary done:",
        "summary_path=output/summary/summary.json",
        f"items={item_count}",
        "safe_mode=True",
    )


def _run_chairperson_phase() -> None:
    print("[MANUAL] chairperson phase...")
    result = write_decision(project_root=ROOT)
    action_count = len(result.get("next_actions", []))
    print(
        "chairperson done:",
        "decision_path=output/chairperson/decision.json",
        f"actions={action_count}",
        "safe_mode=True",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Meeting engine. File-only flow."
    )
    parser.add_argument(
        "--skip-integrity-warnings",
        action="store_true",
        help="Hide WARN lines. ERROR still stops execution.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run supervisor, plan, and dispatch in order.",
    )
    parser.add_argument(
        "--supervisor",
        action="store_true",
        help="Run supervisor phase.",
    )
    parser.add_argument(
        "--plan-execution",
        action="store_true",
        help="Run execution plan phase.",
    )
    parser.add_argument(
        "--dispatch",
        action="store_true",
        help="Generate dispatch files from execution plan.",
    )
    parser.add_argument(
        "--ingest-response",
        action="store_true",
        help="Save response file into output/responses and responses_index.json.",
    )
    parser.add_argument(
        "--build-summary",
        action="store_true",
        help="Build output/summary/summary.json from responses_index.json and output/responses.",
    )
    parser.add_argument(
        "--chairperson",
        action="store_true",
        help="Build output/chairperson/decision.json from output/summary/summary.json.",
    )
    parser.add_argument(
        "--task-id",
        default="",
        help="Target task id for ingest.",
    )
    parser.add_argument(
        "--target",
        default="",
        help="Response source AI.",
    )
    parser.add_argument(
        "--response-file",
        default="",
        help="Path to response text file.",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run one turn.",
    )
    parser.add_argument(
        "--run-batch",
        action="store_true",
        help="Run until max_turns.",
    )

    args = parser.parse_args()
    d = data_dir()

    errs, warns = check_startup_integrity(d)
    if not args.skip_integrity_warnings:
        for w in warns:
            print(w)
    if errs:
        for e in errs:
            print(e)
        sys.exit(1)

    def _go() -> None:
        if args.auto:
            execution_planner.run_full_automation_safe(d)
            _run_dispatch_phase()
            _run_auto_export(d)
        elif args.supervisor:
            current_status = _read_meeting_status(d)
            if current_status != _SUPERVISOR_ELIGIBLE_STATUS:
                print(
                    f"総監督フェーズは status={_SUPERVISOR_ELIGIBLE_STATUS} のときのみ実行できます。"
                    f" 現在: {current_status}"
                )
                return
            run_supervisor_phase(d)
            _run_auto_export(d)
        elif args.plan_execution:
            execution_planner.run_execution_plan_phase(d)
        elif args.dispatch:
            _run_dispatch_phase()
        elif args.ingest_response:
            _run_ingest_response_phase(
                task_id=args.task_id,
                target=args.target,
                response_file=args.response_file,
            )
        elif args.build_summary:
            _run_build_summary_phase()
        elif args.chairperson:
            _run_chairperson_phase()
        elif args.run_batch:
            orchestrator.run_batch(d)
        else:
            orchestrator.run_once(d)

    with acquire_run_lock(d):
        _go()


if __name__ == "__main__":
    main()
