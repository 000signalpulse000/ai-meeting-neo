from __future__ import annotations

from models.meeting_models import MeetingInput


def respond(turn: int, agenda: str, meeting_input: MeetingInput) -> str:
    return f"""Gemini提案（ターン{turn}）:
議題: {meeting_input.theme}

前提整理:
{meeting_input.situation}

結論:
案Cは有力。ただし、学習価値の設計が甘いなら案Bを再検討すべき。

理由:
- 案Cは4週間・2名体制でも前進しやすい
- 低コストで仮説検証を回せる
- ただし、何を学ぶかを定義しないと「手動で回しただけ」で終わる

評価:
- 案A: 最速だが、継続利用や運用課題の学習が弱い
- 案B: 学習価値は高いが、期限内に中途半端になる危険がある
- 案C: 実現性と学習価値のバランスが最も良い

懸念:
- 検証指標が曖昧だと案Cの価値が下がる

次アクション:
案Cで検証する指標を3つに絞る
- ユーザー反応
- 運用負荷
- 継続利用の兆候
"""
