import json
import shutil
import sys
from pathlib import Path
from datetime import datetime


ROOT = Path(r"C:\Users\taroh\ai-meeting-neo")
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
IDEAS_DIR = DATA_DIR / "ideas"
CONTEXT_DIR = Path(r"C:\Users\taroh\context")


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_context_text(context_dir: Path) -> str:
    if not context_dir.exists():
        return ""

    parts = []
    for md_file in sorted(context_dir.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8").strip()
        except Exception:
            text = ""
        if text:
            parts.append(f"## {md_file.name}\n{text}")

    return "\n\n".join(parts)


def reset_runtime_files() -> None:
    files_to_reset = [
        DATA_DIR / "meeting_state.json",
        DATA_DIR / "turns.json",
        DATA_DIR / "supervisor_input.json",
        DATA_DIR / "supervisor_output.json",
        DATA_DIR / "execution_plan.json",
        DATA_DIR / "dispatch_queue.json",
        DATA_DIR / "input.json",
    ]

    for path in files_to_reset:
        if path.exists():
            path.unlink()

    dirs_to_reset = [
        OUTPUT_DIR / "dispatch",
    ]

    for path in dirs_to_reset:
        if path.exists():
            shutil.rmtree(path)

    files_to_delete_if_exist = [
        OUTPUT_DIR / "summary" / "summary.json",
        OUTPUT_DIR / "chairperson" / "decision.json",
    ]

    for path in files_to_delete_if_exist:
        if path.exists():
            path.unlink()


def build_input_payload(idea: dict, context_text: str) -> dict:
    raw_input = idea.get("raw_input", "").strip()
    idea_id = idea.get("idea_id", "")

    background_parts = []
    if context_text:
        background_parts.append(context_text)

    if idea.get("context_refs"):
        background_parts.append("## context_refs\n" + "\n".join(idea["context_refs"]))

    background_context = "\n\n".join(background_parts).strip()

    return {
        "idea_id": idea_id,
        "theme": raw_input if raw_input else idea_id,
        "situation": background_context,
        "goal": "アイデアを要約・分析・統合して、実行可能な形に整理する",
        "constraints": [
            "既存資産を再利用する",
            "MVPとして最小構成で進める",
            "抽象ではなく実行可能な案にする"
        ],
        "question": "このアイデアを実行可能な形に整理し、次にやる1手まで示してください。"
    }


def update_idea_status(idea_path: Path, idea: dict) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    idea["status"] = "running"
    idea["updated_at"] = now
    write_json(idea_path, idea)


def main() -> None:
    idea_filename = sys.argv[1] if len(sys.argv) > 1 else "idea_0001.json"
    idea_path = IDEAS_DIR / idea_filename

    if not idea_path.exists():
        raise FileNotFoundError(f"idea file not found: {idea_path}")

    idea = read_json(idea_path)

    raw_input = idea.get("raw_input", "").strip()
    if not raw_input:
        raise ValueError(
            f"[BLOCKED] raw_input is empty in {idea_path.name}.\n"
            f"  → Edit raw_input before running prepare."
        )

    context_text = load_context_text(CONTEXT_DIR)

    reset_runtime_files()

    payload = build_input_payload(idea, context_text)
    write_json(DATA_DIR / "input.json", payload)

    update_idea_status(idea_path, idea)

    print("prepare_idea_run.py completed")
    print(f"idea_path:  {idea_path}")
    print(f"input_path: {DATA_DIR / 'input.json'}")
    print(f"theme:      {payload['theme'][:80]}")


if __name__ == "__main__":
    main()
