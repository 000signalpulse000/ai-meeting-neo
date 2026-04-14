import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT_DIR = ROOT / "output" / "execution_result"

RUN_CURSOR_EXECUTION = SCRIPTS_DIR / "run_cursor_execution.py"
SAVE_CURSOR_RESPONSE = SCRIPTS_DIR / "save_cursor_response.py"

REPLY_PATH = OUTPUT_DIR / "cursor_reply.txt"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"


def _run_python(script_path: Path, args: list[str] | None = None) -> int:
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd)
    return result.returncode


def _print_start_guide() -> None:
    print()
    print("=== NEXT ACTION ===")
    print("1. Paste the copied prompt into Cursor")
    print(f"2. Paste the full Cursor response into:")
    print(f"   {REPLY_PATH}")
    print("3. Then run:")
    print(r"   python .\scripts\run_cursor_roundtrip.py finish")
    print()


def _print_finish_summary() -> int:
    if not MANIFEST_PATH.exists():
        print(f"[ERROR] manifest not found: {MANIFEST_PATH}")
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    count = int(manifest.get("count", 0))
    written_files = manifest.get("written_files", [])

    print()
    print("=== SAVE RESULT ===")
    print(f"count: {count}")
    for path in written_files:
        print(f"- {path}")
    print()
    return 0


def start() -> int:
    if not RUN_CURSOR_EXECUTION.exists():
        print(f"[ERROR] script not found: {RUN_CURSOR_EXECUTION}")
        return 1

    code = _run_python(RUN_CURSOR_EXECUTION)
    if code != 0:
        print(f"[ERROR] run_cursor_execution failed: exit_code={code}")
        return code

    _print_start_guide()
    return 0


def finish() -> int:
    if not SAVE_CURSOR_RESPONSE.exists():
        print(f"[ERROR] script not found: {SAVE_CURSOR_RESPONSE}")
        return 1

    if not REPLY_PATH.exists():
        print(f"[ERROR] reply file not found: {REPLY_PATH}")
        return 1

    code = _run_python(
        SAVE_CURSOR_RESPONSE,
        ["--input-file", str(REPLY_PATH)],
    )
    if code != 0:
        print(f"[ERROR] save_cursor_response failed: exit_code={code}")
        return code

    return _print_finish_summary()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        nargs="?",
        default="start",
        choices=["start", "finish"],
    )
    args = parser.parse_args()

    if args.mode == "start":
        return start()
    return finish()


if __name__ == "__main__":
    raise SystemExit(main())
