from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.stage_ini_codec as codec


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
