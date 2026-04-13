from __future__ import annotations

from models.meeting_models import MeetingInput


def respond(turn: int, agenda: str, meeting_input: MeetingInput) -> str:
    return f"""Grok提案（ターン{turn}）:
議題: {meeting_input.theme}

前提整理:
{meeting_input.situation}

結論:
案Cを先にやるのが安全。派手さはないが、事故りにくい。

理由:
- 案Bは4週間で地雷化しやすい
- 案Aは軽すぎて学びが浅い
- 案Cは小さく始めて、中身のある失敗や改善点を拾いやすい

リスク:
- 手動運用の人件負荷が想定より重いと回らなくなる
- 疑似プロダクトのため、自動化後に別物になる可能性がある

対案比較:
- 案A: 安全寄りだが情報不足で終わりやすい
- 案B: 夢はあるが今の体制では重い
- 案C: 地味だが一番壊れにくい

次アクション:
案Cを採るなら、手動工程を一覧化して「後で自動化しやすい順」に並べる
"""
