from __future__ import annotations

import argparse
from pathlib import Path

from san_tools.project_paths import PROJECT_ROOT, find_game_data_dir
from san_tools.text.encode_convert import process_folder


def main() -> int:
    """把原始游戏文本批量转成 UTF-8 目录，方便比对与导表。"""

    parser = argparse.ArgumentParser(description="把游戏文本批量转换为 UTF-8。")
    parser.add_argument("--game-dir", type=Path, help="游戏数据目录；默认自动查找 data/game。")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "data" / "text", help="UTF-8 文本输出目录。")
    args = parser.parse_args()
    game_dir = args.game_dir.resolve() if args.game_dir else find_game_data_dir()
    process_folder(game_dir, args.out.resolve(), "big5_to_utf8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
