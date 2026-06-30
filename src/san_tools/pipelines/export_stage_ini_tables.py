from __future__ import annotations

import argparse
from pathlib import Path

import san_tools.codecs.stage_ini_codec as codec


def main() -> int:
    parser = argparse.ArgumentParser(description="Export stage.ini into readable JSON tables.")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("derived/stage_ini_analysis/stage_ini_tables.json"),
    )
    args = parser.parse_args()

    payload = codec.build_payload(args.root)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(codec.payload_to_json(payload), encoding="utf-8")
    print(args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
