from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.stage_ini_codec as codec


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a new stage.ini from exported JSON tables.")
    parser.add_argument(
        "input_json",
        nargs="?",
        default=Path("derived/stage_ini_analysis/stage_ini_tables.json"),
        type=Path,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("derived/stage_ini_analysis/stage.ini"),
    )
    parser.add_argument(
        "--compare-with",
        type=Path,
        default=None,
        help="Optional original stage.ini path; when present, print whether bytes are identical.",
    )
    args = parser.parse_args()

    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    blob = codec.rebuild_stage_ini(payload)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(blob)

    result: dict[str, object] = {
        "output": str(args.out),
        "size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }
    if args.compare_with is not None:
        original = args.compare_with.read_bytes()
        result["compare_with"] = str(args.compare_with)
        result["byte_identical"] = original == blob
        result["original_sha256"] = hashlib.sha256(original).hexdigest()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
