from __future__ import annotations

import argparse
import json
from pathlib import Path

import san_tools.codecs.stage_ini_txt_linkage as linkage


def main() -> int:
    parser = argparse.ArgumentParser(description="分析 uft8-game-txt 与 stage.ini 的文本关联，导出给工作簿使用的 JSON。")
    parser.add_argument("root", nargs="?", default=".", help="包含 stage.ini 与 uft8-game-txt 目录的工作区根目录")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_path = linkage.export_bundle(root)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "json": str(out_path),
                "linked_files": payload["file_summaries"],
                "unlinked_files": payload["unlinked_files"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
