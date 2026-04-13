"""1ターン実行と連続実行のオーケストレーション。"""
from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path

from agents import chatgpt_agent, gemini_agent, grok_agent
from config import settings
from core import chairperson, supervisor, turn_manager
from models.meeting_models import SCHEMA_VERSION, MeetingInput, MeetingStateFile, TurnRecord
from storage import repository


def build_agenda(turn: int, inp: MeetingInput) -> str:
    return (
        f"Turn {turn} 議題\n"
        f"- theme: {inp.theme}\n"
        f"- question: {inp.question}\n"
        f"(situation/goal/constraints はコンテキストとして参照)"
    )


def initial_state(inp: MeetingInput) -> MeetingStateFile:
    return MeetingStateFile(
        schema_version=SCHEMA_VERSION,
        session_id=uuid.uuid4().hex,
        safe_mode=settings.safe_mode_default(),
        meeting_state="initialized",
        current_turn=0,
        max_turns=settings.max_turns(),
        status="running",
        supervisor_input=None,
    )


def _ensure_session_meta(state: MeetingStateFile) -> MeetingStateFile:
    """旧形式の state をメモリ上だけ補完（保存は各フェーズの最後の meeting_state 更新で行う）。"""
    sid = state.session_id or uuid.uuid4().hex
    sv = state.schema_version or SCHEMA_VERSION
    if sv != SCHEMA_VERSION:
        sv = SCHEMA_VERSION
    return replace(state, session_id=sid, schema_version=sv)


def run_single_turn(
    data_dir: Path,
    inp: MeetingInput,
    turns: list[TurnRecord],
    state: MeetingStateFile,
) -> tuple[list[TurnRecord], MeetingStateFile]:
    """次のターンを組み立てて1回実行。詳細アーティファクトを先に、meeting_state は最後。"""
    state = _ensure_session_meta(state)
    next_turn = state.current_turn + 1
    if next_turn > state.max_turns:
        raise RuntimeError(
            f"これ以上ターンを進められません (max_turns={state.max_turns})"
        )

    agenda = build_agenda(next_turn, inp)
    cg = chatgpt_agent.respond(next_turn, agenda, inp)
    gm = gemini_agent.respond(next_turn, agenda, inp)
    gr = grok_agent.respond(next_turn, agenda, inp)
    chair_in = chairperson.build_chairperson_input(inp, next_turn, cg, gm, gr)
    summary = chairperson.summarize_round(chair_in)

    new_turn = TurnRecord(
        turn=next_turn,
        chatgpt=cg,
        gemini=gm,
        grok=gr,
        chair_summary=summary,
    )
    turns = list(turns) + [new_turn]

    new_state = MeetingStateFile(
        schema_version=state.schema_version,
        session_id=state.session_id,
        safe_mode=state.safe_mode,
        meeting_state=state.meeting_state,
        current_turn=next_turn,
        max_turns=state.max_turns,
        status="running",
        supervisor_input=state.supervisor_input,
    )

    if turn_manager.is_at_supervisor_pause(new_state.current_turn):
        new_state.status = "paused_for_supervisor"
        new_state.supervisor_input = supervisor.build_supervisor_input(
            inp, new_state.current_turn, new_state.max_turns, state.session_id
        )
        repository.save_supervisor_input(data_dir, new_state.supervisor_input)

    repository.save_turns(data_dir, turns, state.session_id)
    repository.save_meeting_state(data_dir, new_state)
    return turns, new_state


def run_once(data_dir: Path) -> None:
    inp = repository.load_meeting_input(data_dir)
    state = repository.load_meeting_state(data_dir)
    turns = repository.load_turns(data_dir)

    if state is None:
        state = initial_state(inp)
        turns = []
    else:
        state = _ensure_session_meta(state)
    if state.status == "paused_for_supervisor":
        print(
            "状態: paused_for_supervisor - 会議ターンは終了。"
            "総監督は python main.py --supervisor"
        )
        return
    if state.status == "approved_for_execution":
        print(
            "状態: approved_for_execution - 実行計画は python main.py --plan-execution"
        )
        return
    if state.status == "needs_revision":
        print("状態: needs_revision - 入力・会議結果の見直し後、必要なら会議をやり直してください。")
        return
    if state.status == "completed":
        print("状態: completed - 処理は完了済み。")
        return

    if state.current_turn >= state.max_turns:
        print("最大ターンに達しています。")
        return

    _, new_state = run_single_turn(data_dir, inp, turns, state)
    print(f"ターン {new_state.current_turn} を保存しました。status={new_state.status}")


def run_batch(data_dir: Path) -> None:
    inp = repository.load_meeting_input(data_dir)
    state = repository.load_meeting_state(data_dir)
    turns = repository.load_turns(data_dir)

    if state is None:
        state = initial_state(inp)
        turns = []
    else:
        state = _ensure_session_meta(state)

    if state.status == "paused_for_supervisor":
        print("既に paused_for_supervisor です。--supervisor で総監督フェーズへ。")
        return
    if state.status == "approved_for_execution":
        print("既に approved_for_execution です。--plan-execution で実行計画を生成。")
        return
    if state.status == "needs_revision":
        print("needs_revision のためバッチをスキップ。修正後に状態をリセットしてください。")
        return
    if state.status == "completed":
        print("既に completed です。")
        return

    while state.current_turn < state.max_turns:
        turns, state = run_single_turn(data_dir, inp, turns, state)
        print(f"  ターン {state.current_turn} 保存 status={state.status}")
        if state.status == "paused_for_supervisor":
            break

    print(f"バッチ終了 current_turn={state.current_turn} status={state.status}")
