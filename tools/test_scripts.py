from __future__ import annotations

from pathlib import Path

from tools.encode_convert import process_folder


def main() -> int:
    """把原始文本目录批量转成 UTF-8 版本，便于后续比对。"""

    root = Path(__file__).resolve().parents[1]
    process_folder(root / "三国霸业", root / "uft8-game-txt", "big5_to_utf8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())