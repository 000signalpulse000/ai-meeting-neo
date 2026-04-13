"""実行計画フェーズ: 承認済み決定から「提案」タスクとプロンプトを生成する（ファイルのみ・非実行）。"""
from __future__ import annotations

from pathlib import Path

from models.meeting_models import (
    ExecutionPlan,
    ExecutionTask,
    MeetingInput,
    MeetingStateFile,
    SupervisorOutput,
)
from storage import repository


def _tasks_from_decision(
    inp: MeetingInput, sup: SupervisorOutput, session_id: str
) -> list[ExecutionTask]:
    opt = sup.adopted_option
    theme = inp.theme[:120]
    goal = inp.goal[:120]

    return [
        ExecutionTask(
            session_id=session_id,
            task_id="exec-cursor-1",
            title="リポジトリ内で採用案を反映する差分の準備",
            description=(
                f"テーマ「{theme}」において案{opt}を主軸とする。"
                f"制約「{inp.constraints[:100]}」を満たすよう変更範囲を最小に抑え、"
                f"MVP としての目標「{goal}」に直結するファイルだけを編集すること。"
            ),
            target="cursor",
            order=1,
            lifecycle="draft",
        ),
        ExecutionTask(
            session_id=session_id,
            task_id="exec-openclaw-1",
            title="ローカル検証・スクリプト実行の手順整理",
            description=(
                f"案{opt}に基づき、手動で安全に実行できる検証コマンドを列挙する。"
                "ネットワークへの書き込み・本番デプロイは含めない（セーフモード）。"
            ),
            target="openclaw",
            order=2,
            lifecycle="draft",
        ),
        ExecutionTask(
            session_id=session_id,
            task_id="exec-chatgpt-1",
            title="ステークホルダ向け説明文のドラフト",
            description=(
                f"採用理由（{sup.vote_summary}）と制約整合（{sup.constraints_aligned}）を踏まえ、"
                f"論点「{inp.question[:150]}」に答える1ページ説明を作成する。"
            ),
            target="chatgpt",
            order=3,
            lifecycle="draft",
        ),
    ]


def _write_prompt_files(
    data_dir: Path,
    inp: MeetingInput,
    sup: SupervisorOutput,
    tasks: list[ExecutionTask],
    session_id: str,
) -> None:
    prompts_dir = (data_dir.parent / "prompts").resolve()
    by_target = {t.target: t for t in tasks}

    def md_cursor() -> str:
        t = by_target["cursor"]
        return f"""# Cursor 向け実行プロンプト（セーフモード・提案のみ）

> 本ファイルは実行命令ではありません。人手によるレビューと承認後に利用してください。
> session_id: `{session_id}`

## コンテキスト
- テーマ: {inp.theme}
- 採用案: 案{sup.adopted_option}（票: {sup.vote_summary}）
- 制約: {inp.constraints}

## 依頼（自動デプロイ・本番変更は禁止）
{t.description}

## 禁止事項
- 秘密情報のコミット、本番 URL への直接変更、確認なしの `rm` / `format` 全消し

## 参照
- `data/supervisor_output.json`
"""

    def md_openclaw() -> str:
        t = by_target["openclaw"]
        return f"""# OpenClaw 向け実行プロンプト（セーフモード・提案のみ）

> ディスパッチ・シェル自動実行は行いません。session_id: `{session_id}`

## コンテキスト
- 状況: {inp.situation[:400]}
- 採用案: 案{sup.adopted_option}

## 依頼
{t.description}

## セーフモード
- 読み取りとローカル検証のみ。外部サービスへの書き込みは手動承認後に限定。
"""

    def md_chatgpt() -> str:
        t = by_target["chatgpt"]
        return f"""# ChatGPT 向け実行プロンプト（文案・整理・提案のみ）

> API 自動送信は行いません。session_id: `{session_id}`

## 入力要約
- 目標: {inp.goal}
- 論点: {inp.question}

## 依頼
{t.description}

## 総監督抜粋
{sup.final_judgment_excerpt[:800]}
"""

    prompts_dir.mkdir(parents=True, exist_ok=True)
    repository.atomic_write_text(prompts_dir / "execution_prompt_cursor.md", md_cursor())
    repository.atomic_write_text(prompts_dir / "execution_prompt_openclaw.md", md_openclaw())
    repository.atomic_write_text(prompts_dir / "execution_prompt_chatgpt.md", md_chatgpt())


def run_execution_plan_phase(data_dir: Path) -> ExecutionPlan | None:
    """
    approved_for_execution のときのみ。
    execution_plan.json（tasks 内包）と prompts を先に保存し、最後に meeting_state を更新する。
    """
    state = repository.load_meeting_state(data_dir)
    if state is None:
        print("エラー: meeting_state.json がありません。")
        return None
    if not state.session_id:
        print("エラー: session_id がありません。")
        return None
    if state.status == "completed":
        print("状態は既に completed。実行計画の再生成は data を手動調整後に行ってください。")
        return None

    if state.status != "approved_for_execution":
        print(
            "実行計画フェーズは status=approved_for_execution のときのみ実行できます。"
            f"（現在: {state.status}）"
        )
        return None

    sup = repository.load_supervisor_output(data_dir)
    if sup.session_id and sup.session_id != state.session_id:
        print("エラー: supervisor_output の session_id が meeting_state と一致しません。")
        return None
    if sup.recommendation != "approve":
        print("エラー: supervisor_output が approve ではありません。")
        return None

    inp = repository.load_meeting_input(data_dir)
    tasks = _tasks_from_decision(inp, sup, state.session_id)
    plan = ExecutionPlan(
        session_id=state.session_id,
        artifact_kind="execution_plan",
        proposal_only=True,
        plan_id="plan-local-001",
        summary=(
            f"案{sup.adopted_option} を採用し、タスク {len(tasks)} 件を生成（提案・draft のみ）。"
        ),
        safe_mode=state.safe_mode,
        tasks=tasks,
        based_on_adopted=sup.adopted_option,
    )

    repository.save_execution_plan(data_dir, plan)
    _write_prompt_files(data_dir, inp, sup, tasks, state.session_id)

    new_state = MeetingStateFile(
        schema_version=state.schema_version,
        session_id=state.session_id,
        safe_mode=state.safe_mode,
        meeting_state=state.meeting_state,
        current_turn=state.current_turn,
        max_turns=state.max_turns,
        status="completed",
        supervisor_input=state.supervisor_input,
    )
    repository.save_meeting_state(data_dir, new_state)

    print("実行計画フェーズ完了: execution_plan.json（tasks 統合）と prompts を生成しました。")
    print(
        f"状態を completed に更新。セーフモード永続値: safe_mode={plan.safe_mode} "
        "（危険操作の自動実行はありません）"
    )
    return plan


def run_full_automation_safe(data_dir: Path) -> None:
    """
    会議バッチ（必要時）→ 総監督 → 実行計画の順でファイル生成のみ。
    """
    from core import orchestrator
    from core.supervisor import run_supervisor_phase

    state = repository.load_meeting_state(data_dir)

    if state is None or (
        state.status == "running" and state.current_turn < state.max_turns
    ):
        print("[自動] 会議バッチを実行します…")
        orchestrator.run_batch(data_dir)
        state = repository.load_meeting_state(data_dir)

    if state and state.status == "paused_for_supervisor":
        print("[自動] 総監督フェーズ…")
        run_supervisor_phase(data_dir)
        state = repository.load_meeting_state(data_dir)

    if state and state.status == "approved_for_execution":
        print("[自動] 実行計画フェーズ…")
        run_execution_plan_phase(data_dir)
    elif state and state.status == "needs_revision":
        print(
            "[自動] needs_revision のため実行計画はスキップ。"
            "データ修正後に --supervisor を再実行してください。"
        )
    elif state and state.status == "completed":
        print("[自動] 既に completed。追加の自動処理はありません。")

    print("[自動] 完了（ファイル生成のみ。外部実行・ディスパッチはしていません）")
