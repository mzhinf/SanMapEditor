from __future__ import annotations

from pathlib import Path

from san_tools.text.encode_convert import process_folder


GAME_DIR_NAME = "三国霸业"


def main() -> int:
    """把原始游戏文本批量转成 UTF-8 目录，方便比对与导表。"""

    root = Path(__file__).resolve().parents[3]
    process_folder(root / GAME_DIR_NAME, root / "uft8-game-txt", "big5_to_utf8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
