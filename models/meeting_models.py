"""会議入力・ターン・状態のデータ構造（将来API接続を想定したフラットな形）。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

# 正規アーティファクトのスキーマ識別子（整合性チェック用）
SCHEMA_VERSION = "1"

MeetingStatus = Literal[
    "running",
    "paused_for_supervisor",
    "approved_for_execution",
    "needs_revision",
    "completed",
    "on_hold",
]

SupervisorRecommendation = Literal["approve", "needs_revision"]

TaskLifecycle = Literal["draft", "approved"]


@dataclass
class MeetingInput:
    theme: str
    situation: str
    goal: str
    constraints: str
    question: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MeetingInput:
        required = ("theme", "situation", "goal", "constraints", "question")
        missing = [k for k in required if k not in d]
        if missing:
            raise ValueError(f"input.json に不足キー: {missing}")
        return cls(
            theme=str(d["theme"]),
            situation=str(d["situation"]),
            goal=str(d["goal"]),
            constraints=str(d["constraints"]),
            question=str(d["question"]),
        )


@dataclass
class ChairpersonInput:
    """議長統合の入力（API版・ルール版で共通）。"""

    meeting_input: MeetingInput
    current_turn: int
    chatgpt_response: str
    gemini_response: str
    grok_response: str


@dataclass
class ChairSummary:
    agreements: str
    conflicts: str
    missing_points: str
    next_candidates: str
    integrated_result: str


@dataclass
class TurnRecord:
    turn: int
    chatgpt: str
    gemini: str
    grok: str
    chair_summary: ChairSummary


@dataclass
class SupervisorInputPayload:
    """総監督へ渡す入力（スナップショット）。実行指示ではない。"""

    session_id: str
    theme: str
    situation: str
    goal: str
    constraints: str
    question: str
    turns_completed: int
    max_turns: int
    note: str = ""


@dataclass
class SupervisorOutput:
    """総監督フェーズの提案出力（ファイル永続。実行命令ではない）。"""

    session_id: str
    artifact_kind: str  # 固定: supervisor_output
    proposal_only: bool
    adopted_option: str
    vote_summary: str
    rationale: str
    constraints_aligned: bool
    final_judgment_excerpt: str
    recommendation: SupervisorRecommendation
    source_turn: int


@dataclass
class ExecutionTask:
    """プランナーが生成するタスク提案（draft）。実行エンジンではない。"""

    session_id: str
    task_id: str
    title: str
    description: str
    target: Literal["cursor", "openclaw", "chatgpt"]
    order: int
    lifecycle: TaskLifecycle


@dataclass
class ExecutionPlan:
    """実行「準備」用の計画案。自動実行・ディスパッチは行わない。tasks は同一 JSON に内包。"""

    session_id: str
    artifact_kind: str  # 固定: execution_plan
    proposal_only: bool
    plan_id: str
    summary: str
    safe_mode: bool
    tasks: list[ExecutionTask]
    based_on_adopted: str


@dataclass
class MeetingStateFile:
    """
    正規の最新状態へのライトウェイトなポインタ（完全マニフェストではない）。
    詳細アーティファクトを先に保存し、本ファイルは最後に更新する。
    """

    schema_version: str
    session_id: str
    safe_mode: bool
    meeting_state: str
    current_turn: int
    max_turns: int
    status: MeetingStatus
    supervisor_input: SupervisorInputPayload | None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.supervisor_input is not None:
            d["supervisor_input"] = asdict(self.supervisor_input)
        else:
            d["supervisor_input"] = None
        return d


def chair_summary_to_dict(cs: ChairSummary) -> dict[str, str]:
    return asdict(cs)


def turn_record_to_dict(tr: TurnRecord) -> dict[str, Any]:
    return {
        "turn": tr.turn,
        "chatgpt": tr.chatgpt,
        "gemini": tr.gemini,
        "grok": tr.grok,
        "chair_summary": asdict(tr.chair_summary),
    }
