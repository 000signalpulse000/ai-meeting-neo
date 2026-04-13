from __future__ import annotations

import json
import re
from pathlib import Path

from models.meeting_models import (
    MeetingInput,
    MeetingStateFile,
    SupervisorInputPayload,
    SupervisorOutput,
    SupervisorRecommendation,
)
from storage import memory_hub, repository


def build_supervisor_input(
    inp: MeetingInput,
    current_turn: int,
    max_turns: int,
    session_id: str,
) -> SupervisorInputPayload:
    return SupervisorInputPayload(
        session_id=session_id,
        theme=inp.theme,
        situation=inp.situation,
        goal=inp.goal,
        constraints=inp.constraints,
        question=inp.question,
        turns_completed=current_turn,
        max_turns=max_turns,
        note="snapshot only. final decision is stored in supervisor_output.json (proposal_only).",
    )


def _parse_final_judgment(integrated: str) -> tuple[str, str, bool, str]:
    text = integrated.strip()

    adopted = "unknown"
    patterns = [
        r"案\s*([ABC])",
        r"採用案\s*[:：]?\s*案?\s*([ABC])",
        r"最終結論\s*[:：]?\s*案?\s*([ABC])",
        r"option\s*([ABC])",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            adopted = m.group(1).upper()
            break

    vote = "0/0"
    vm = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if vm:
        vote = f"{vm.group(1)}/{vm.group(2)}"

    text_lower = text.lower()
    aligned = (
        ("制約" in text or "constraint" in text_lower)
        and ("整合" in text or "適合" in text or "aligned" in text_lower)
    )

    excerpt = text[:500] + ("..." if len(text) > 500 else "")
    return adopted, vote, aligned, excerpt


def _build_rationale(adopted: str, vote: str, aligned: bool, inp: MeetingInput) -> str:
    parts = [
        f"採用案: {adopted}" if adopted != "unknown" else "採用案: 未特定",
        f"得票: {vote}",
        f"制約との整合: {'あり' if aligned else '未確認'}",
        f"目標: {inp.goal[:80]}",
    ]
    return " / ".join(parts)


def _should_approve(integrated: str, adopted: str, aligned: bool) -> bool:
    if adopted == "unknown":
        return False
    compact = integrated.replace(" ", "").replace("　", "")
    has_3_of_3 = bool(re.search(r"3\s*/\s*3", integrated)) or "3AI中3/3" in compact
    if not has_3_of_3:
        return False
    return aligned or ("整合" in integrated)


def _resolve_idea_id(data_dir: Path, session_id: str) -> str:
    input_path = data_dir / "input.json"
    if input_path.exists():
        try:
            raw = json.loads(input_path.read_text(encoding="utf-8-sig"))
            if isinstance(raw, dict):
                value = raw.get("idea_id")
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except Exception:
            pass

    if session_id and session_id.strip():
        return session_id.strip()

    return "idea_latest"


def run_supervisor_phase(data_dir: Path) -> SupervisorOutput | None:
    """
    paused_for_supervisor のときのみ実行する。
    supervisor_output.json を先に保存し、最後に meeting_state を更新する。
    さらに memory_hub/{idea_id}.json に同内容を自動保存する。
    """
    state = repository.load_meeting_state(data_dir)
    if state is None:
        print("エラー: meeting_state.json がありません。")
        return None
    if not state.session_id:
        print("エラー: meeting_state に session_id がありません。")
        return None
    if state.status != "paused_for_supervisor":
        print(
            "総監督フェーズは status=paused_for_supervisor のときのみ実行できます。"
            f" 現在: {state.status}"
        )
        return None

    turns = repository.load_turns(data_dir)
    if not turns:
        print("エラー: turns.json が空です。")
        return None

    last = max(turns, key=lambda tr: tr.turn)
    integrated = last.chair_summary.integrated_result
    adopted, vote, aligned, excerpt = _parse_final_judgment(integrated)
    inp = repository.load_meeting_input(data_dir)

    rationale = _build_rationale(adopted, vote, aligned, inp)

    if _should_approve(integrated, adopted, aligned):
        rec: SupervisorRecommendation = "approve"
    else:
        rec = "needs_revision"

    out = SupervisorOutput(
        session_id=state.session_id,
        artifact_kind="supervisor_output",
        proposal_only=True,
        adopted_option=adopted,
        vote_summary=vote,
        rationale=rationale,
        constraints_aligned=aligned,
        final_judgment_excerpt=excerpt,
        recommendation=rec,
        source_turn=last.turn,
    )

    repository.save_supervisor_output(data_dir, out)

    idea_id = _resolve_idea_id(data_dir, state.session_id)
    memory_hub.save_idea(
        idea_id=idea_id,
        idea_json=out.__dict__,
    )

    new_state = MeetingStateFile(
        schema_version=state.schema_version,
        session_id=state.session_id,
        safe_mode=state.safe_mode,
        meeting_state=state.meeting_state,
        current_turn=state.current_turn,
        max_turns=state.max_turns,
        status="approved_for_execution" if rec == "approve" else "needs_revision",
        supervisor_input=state.supervisor_input,
    )
    repository.save_meeting_state(data_dir, new_state)

    print(
        f"総監督フェーズ完了: recommendation={rec}, 案={adopted}, 票={vote} -> "
        f"status={new_state.status}"
    )
    print(f"memory_hub 保存: {idea_id}.json")
    print(f"出力: {data_dir / 'supervisor_output.json'}")
    return out
