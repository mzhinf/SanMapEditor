from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path


def find_game_dir(root: Path) -> Path:
    if (root / "Emperor.exe").exists():
        return root
    for child in root.iterdir():
        if child.is_dir() and (child / "Emperor.exe").exists():
            return child
    raise FileNotFoundError("Could not find game directory containing Emperor.exe")


def parse_m(path: Path) -> tuple[int, int, list[bytes]]:
    blob = path.read_bytes()
    if blob[8:16] != b"Hello1.0":
        raise ValueError(f"{path.name} is not a Hello1.0 .m file")
    width, height = struct.unpack_from("<II", blob, 0)
    records = [blob[16 + i * 16 : 16 + (i + 1) * 16] for i in range(width * height)]
    return width, height, records


def top_counts(data: bytes, limit: int = 12) -> list[list[int]]:
    return [[value, count] for value, count in Counter(data).most_common(limit)]


def summarize_sidecar(path: Path) -> dict[str, object]:
    blob = path.read_bytes()
    head = blob[:96]
    dword_count = min(len(head) // 4, 12)
    dwords = [struct.unpack_from("<I", head, i * 4)[0] for i in range(dword_count)]
    ascii_preview = "".join(chr(b) if 32 <= b < 127 else "." for b in head[:32])
    return {
        "name": path.name,
        "size": len(blob),
        "ascii_preview": ascii_preview,
        "dwords": dwords,
    }


def summarize_stage(game_dir: Path, stem: str) -> dict[str, object]:
    width, height, records = parse_m(game_dir / f"{stem}.m")
    final_palette = bytes(record[13] for record in records)
    summary: dict[str, object] = {
        "stage": stem,
        "m": {
            "width": width,
            "height": height,
            "record_count": width * height,
            "final_palette_unique": len(set(final_palette)),
            "final_palette_top": top_counts(final_palette),
        },
    }
    grids = {}
    s_data = None
    x_data = None
    for suffix in ("s", "x"):
        path = game_dir / f"{stem}.{suffix}"
        if not path.exists():
            continue
        data = path.read_bytes()
        grids[suffix] = {
            "size": len(data),
            "unique": len(set(data)),
            "top": top_counts(data),
            "overlap_with_m_final_palette": len(set(data) & set(final_palette)),
        }
        if suffix == "s":
            s_data = data
        else:
            x_data = data
    if s_data is not None and x_data is not None and len(s_data) == len(x_data):
        same = sum(1 for a, b in zip(s_data, x_data) if a == b)
        grids["s_x_similarity"] = {
            "same_bytes": same,
            "different_bytes": len(s_data) - same,
            "same_ratio": round(same / len(s_data), 6),
        }
    summary["grids"] = grids
    sidecars = {}
    for suffix in ("stg", "spr", "dor", "evt"):
        path = game_dir / f"{stem}.{suffix}"
        if path.exists():
            sidecars[suffix] = summarize_sidecar(path)
    summary["sidecars"] = sidecars
    return summary


def summarize_exe_strings(game_dir: Path) -> dict[str, object]:
    blob = (game_dir / "Emperor.exe").read_bytes()
    offsets = {
        ".s": blob.find(b".s\x00"),
        ".x": blob.find(b".x\x00"),
        ".m": blob.find(b".m\x00"),
        ".evt": blob.find(b".evt\x00"),
        ".dor": blob.find(b".dor\x00"),
        ".spr": blob.find(b".spr\x00"),
    }
    contexts = {}
    for name, offset in offsets.items():
        if offset < 0:
            continue
        start = max(0, offset - 24)
        end = min(len(blob), offset + 48)
        chunk = blob[start:end]
        contexts[name] = {
            "offset": offset,
            "ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in chunk),
        }
    return contexts


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize stage sidecar files and fixed grids.")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", action="append", dest="stages", help="Stage stem such as stage11")
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args()

    game_dir = find_game_dir(args.root.resolve())
    stages = args.stages or ["stage11"]
    payload = {
        "game_dir": str(game_dir),
        "stages": [summarize_stage(game_dir, stem) for stem in stages],
        "exe_suffix_contexts": summarize_exe_strings(game_dir),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=args.indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
