from __future__ import annotations

from models.meeting_models import MeetingInput


def respond(turn: int, agenda: str, meeting_input: MeetingInput) -> str:
    return f"""ChatGPT提案（ターン{turn}）:
議題: {meeting_input.theme}

前提整理:
{meeting_input.situation}

結論:
案Cを第一候補とする判断は妥当。

理由:
- 工数とAPI制約に最も適合
- 4週間で完遂できる現実性が高い
- 最低限の構築で価値検証が可能

リスク:
- 手動運用に依存しすぎるとスケール検証が弱い

対案検討:
- 案A: 学習価値が不足
- 案B: 工数過多で失敗リスク高

次アクション:
案Cを前提に「どこまで手動で許容するか」を定義する
"""
