from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output" / "execution_result"
FILES_DIR = OUTPUT_DIR / "files"
RAW_PATH = OUTPUT_DIR / "raw_response.txt"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

# ★修正ポイント
HEADER_PATTERN = re.compile(
    r"^\s*={2,3}\s*FILE\s*:\s*(?P<path>[^=\n]+?)\s*={2,3}\s*$",
    re.IGNORECASE,
)


@dataclass
class FileBlock:
    declared_path: str
    content: str


def _read_clipboard_text() -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = result.stdout or ""
    if not text.strip():
        raise RuntimeError("クリップボードが空です。")
    return text


def _read_input_text(input_file: str | None) -> tuple[str, str]:
    if input_file:
        path = Path(input_file).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"入力ファイルが見つかりません: {path}")
        text = path.read_text(encoding="utf-8-sig")
        return text, f"file:{path}"

    text = _read_clipboard_text()
    return text, "clipboard"


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.lstrip("\ufeff")
    text = text.lstrip("\n")
    return text


def _parse_blocks(text: str) -> List[FileBlock]:
    lines = _normalize(text).split("\n")

    matches = []
    for idx, line in enumerate(lines):
        m = HEADER_PATTERN.match(line)
        if m:
            matches.append((idx, m.group("path").strip()))

    if not matches:
        raise RuntimeError("FILEヘッダが見つかりません")

    blocks = []

    for i, (start_idx, declared_path) in enumerate(matches):
        content_start = start_idx + 1
        content_end = matches[i + 1][0] if i + 1 < len(matches) else len(lines)

        content = "\n".join(lines[content_start:content_end]).strip("\n")

        blocks.append(FileBlock(declared_path, content))

    return blocks


def _safe_relative_path(path_str: str) -> Path:
    path_str = path_str.replace("\\", "/").strip()
    rel = Path(path_str)

    if rel.is_absolute():
        raise RuntimeError("絶対パス禁止")

    if any(p in ("..", "") for p in rel.parts):
        raise RuntimeError("不正パス")

    return Path(*rel.parts)


def _write_outputs(raw_text: str, source: str, blocks: List[FileBlock]):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)

    RAW_PATH.write_text(_normalize(raw_text), encoding="utf-8")

    written = []

    for block in blocks:
        rel = _safe_relative_path(block.declared_path)
        out = FILES_DIR / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(block.content.strip() + "\n", encoding="utf-8")
        written.append(str(rel).replace("\\", "/"))

    manifest = {
        "source": source,
        "count": len(written),
        "written_files": written,
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file")
    args = parser.parse_args()

    raw, source = _read_input_text(args.input_file)
    blocks = _parse_blocks(raw)
    manifest = _write_outputs(raw, source, blocks)

    print("OK:", manifest["count"])
    for f in manifest["written_files"]:
        print("-", f)


if __name__ == "__main__":
    main()
