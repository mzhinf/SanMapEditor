from __future__ import annotations

import re
from pathlib import Path

SECTION_PATTERN = re.compile(r"^#(\d{3})(.*)$")


def decode_game_text_bytes(data: bytes) -> str:
    """按游戏常见编码读取文本，失败时退回宽松解码。"""

    for encoding in ("cp950", "big5", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("cp950", errors="replace")


def classify_text_blob(data: bytes) -> dict[str, object]:
    """判断一个 `.txt` 更像可读脚本，还是误用 `.txt` 后缀的二进制。"""

    sample = data[:65536]
    if not sample:
        return {
            "byte_length": 0,
            "zero_bytes": 0,
            "zero_ratio": 0.0,
            "replacement_ratio": 0.0,
            "printable_ratio": 0.0,
            "likely_text": False,
        }
    text = decode_game_text_bytes(sample)
    zero_bytes = sample.count(0)
    replacement_count = text.count("\ufffd")
    printable_count = sum(1 for char in text if char.isprintable() or char in "\r\n\t")
    zero_ratio = zero_bytes / len(sample)
    replacement_ratio = replacement_count / max(1, len(text))
    printable_ratio = printable_count / max(1, len(text))
    likely_text = zero_ratio <= 0.02 and replacement_ratio <= 0.1 and printable_ratio >= 0.85
    return {
        "byte_length": len(data),
        "zero_bytes": zero_bytes,
        "zero_ratio": round(zero_ratio, 6),
        "replacement_ratio": round(replacement_ratio, 6),
        "printable_ratio": round(printable_ratio, 6),
        "likely_text": likely_text,
    }


def parse_numbered_sections(text: str) -> list[dict[str, object]]:
    """解析 `#000` 这类编号段落。"""

    sections: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        match = SECTION_PATTERN.match(line)
        if match:
            current = {
                "id": int(match.group(1)),
                "header": match.group(2).strip(),
                "lines": [],
            }
            sections.append(current)
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped == "#":
            continue
        if stripped:
            current["lines"].append(stripped)
    for section in sections:
        lines = list(section["lines"])
        section["text"] = "\n".join(lines)
    return sections


def parse_loose_script_blocks(text: str) -> list[dict[str, object]]:
    """解析 `stage17.txt` 这类靠空行分段的脚本文本。"""

    blocks: list[dict[str, object]] = []
    current_lines: list[str] = []

    def flush() -> None:
        if not current_lines:
            return
        lines = [line.strip() for line in current_lines if line.strip()]
        current_lines.clear()
        if not lines:
            return
        speaker = ""
        body_lines = lines
        if len(lines) >= 2 and len(lines[0]) <= 6 and len(lines[1]) >= len(lines[0]):
            speaker = lines[0]
            body_lines = lines[1:]
        blocks.append(
            {
                "speaker": speaker,
                "lines": body_lines,
                "text": "\n".join(body_lines),
            }
        )

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if line.strip():
            current_lines.append(line)
            continue
        flush()
    flush()
    return blocks


def find_case_insensitive_file(game_dir: Path, name: str) -> Path | None:
    """按大小写不敏感方式查找游戏目录内的资源。"""

    lower_name = name.lower()
    for path in game_dir.iterdir():
        if path.is_file() and path.name.lower() == lower_name:
            return path
    return None
