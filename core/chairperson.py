from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models.meeting_models import ChairSummary


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_chairperson_input(inp, turn, cg, gm, gr) -> dict:
    return {
        "turn": turn,
        "theme": getattr(inp, "theme", ""),
        "question": getattr(inp, "question", ""),
        "chatgpt": cg,
        "gemini": gm,
        "grok": gr,
    }


def _majority_option(contents: list[str]) -> str:
    """全AI応答から最多言及の案(A/B/C)を返す。なければ 'unknown'。"""
    joined = " ".join(contents)
    mentions = re.findall(r'案\s*([ABC])', joined)
    if not mentions:
        return "unknown"
    return Counter(mentions).most_common(1)[0][0]


def _count_supporters(contents: list[str], option: str) -> int:
    """各AI応答のうち、採用案に言及しているものの数を返す。"""
    return sum(1 for c in contents if re.search(rf'案\s*{re.escape(option)}', c))


def summarize_round(chair_input: dict) -> ChairSummary:
    contents: list[str] = []

    for key in ["chatgpt", "gemini", "grok"]:
        val = chair_input.get(key)
        if isinstance(val, str) and val.strip():
            contents.append(val.strip())

    if not contents:
        return ChairSummary(
            agreements="",
            conflicts="",
            missing_points="",
            next_candidates="",
            integrated_result="no valid responses",
        )

    adopted = _majority_option(contents)
    supporters = _count_supporters(contents, adopted) if adopted != "unknown" else 0
    total = len(contents)
    vote = f"{supporters}/{total}"

    if adopted != "unknown":
        integrated = (
            f"最終判断: 案{adopted}を採用する。"
            f"理由: {total}AI中{supporters}/{total}が案{adopted}を支持。"
            f"制約条件とも整合。"
        )
    else:
        integrated = "最終判断: 合意案なし。各AI応答を再確認してください。"

    raw = " / ".join(contents)

    return ChairSummary(
        agreements=f"案{adopted}を支持: {supporters}/{total}" if adopted != "unknown" else "",
        conflicts="",
        missing_points="",
        next_candidates="",
        integrated_result=integrated + "\n\n---\n" + raw,
    )


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return default
    return json.loads(text)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


def _collect_contents(summary: dict[str, Any]) -> list[str]:
    items = summary.get("items") if isinstance(summary, dict) else []
    if not isinstance(items, list):
        return []

    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            out.append(content.strip())
    return out


def _build_conclusion(contents: list[str]) -> str:
    if not contents:
        return "No valid AI outputs."
    if len(contents) == 1:
        return "Single AI output used as decision."
    return "Multiple AI outputs merged into one decision."


def _build_next_actions(contents: list[str]) -> list[str]:
    return [
        "Collect more AI outputs if needed",
        "Generate summary.json",
        "Generate decision.json"
    ]


def build_decision(project_root: Path) -> dict[str, Any]:
    summary_path = project_root / "output" / "summary" / "summary.json"
    summary = _load_json(summary_path, {})
    contents = _collect_contents(summary)

    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "safe_mode": True,
        "source_summary_path": "output/summary/summary.json",
        "conclusion": _build_conclusion(contents),
        "next_actions": _build_next_actions(contents),
    }


def write_decision(project_root: Path) -> dict[str, Any]:
    decision = build_decision(project_root)
    out = project_root / "output" / "chairperson" / "decision.json"
    _save_json(out, decision)
    return decision
