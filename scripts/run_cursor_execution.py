import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT / "output" / "dispatch" / "exec-cursor-1" / "prompt_cursor.md"
OUTPUT_DIR = ROOT / "output" / "execution_result"
REPLY_PATH = OUTPUT_DIR / "cursor_reply.txt"
GUIDE_PATH = OUTPUT_DIR / "README_cursor_flow.txt"


def main() -> int:
    if not PROMPT_PATH.exists():
        print(f"[ERROR] prompt not found: {PROMPT_PATH}")
        return 1

    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    REPLY_PATH.write_text(
        "=== FILE: models/meeting_models.py ===\n"
        "# paste Cursor response here\n\n"
        "=== FILE: core/execution_planner.py ===\n\n"
        "=== FILE: core/ai_dispatcher.py ===\n",
        encoding="utf-8",
        newline="\n",
    )

    guide_text = (
        "Cursor execution flow\n"
        "=====================\n\n"
        f"1. Prompt source\n{PROMPT_PATH}\n\n"
        "2. prompt_cursor.md has been copied to clipboard\n\n"
        "3. Paste into Cursor and run\n\n"
        "4. Paste full Cursor response into this file\n"
        f"{REPLY_PATH}\n\n"
        "5. Then run this command\n"
        "python .\\scripts\\save_cursor_response.py --input-file .\\output\\execution_result\\cursor_reply.txt\n"
    )
    GUIDE_PATH.write_text(guide_text, encoding="utf-8", newline="\n")

    subprocess.run("clip", input=prompt_text.encode("utf-16-le"), check=True)

    print(f"source prompt : {PROMPT_PATH}")
    print(f"reply file    : {REPLY_PATH}")
    print(f"guide file    : {GUIDE_PATH}")
    print()
    print("prompt_cursor.md copied to clipboard.")
    print("1. Paste into Cursor")
    print("2. Paste full Cursor response into cursor_reply.txt")
    print("3. Run:")
    print(r"   python .\scripts\save_cursor_response.py --input-file .\output\execution_result\cursor_reply.txt")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
