from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

from extract_kingdom import find_game_dir

FIELD_LAYOUT: dict[str, tuple[int, str, int, int]] = {
    "acwx": (0x00, "h", -32768, 32767),
    "acwy": (0x02, "h", -32768, 32767),
    "acwz": (0x04, "h", -32768, 32767),
    "word06": (0x06, "h", -32768, 32767),
    "byte08": (0x08, "B", 0, 255),
    "byte09": (0x09, "B", 0, 255),
    "byte10": (0x0A, "B", 0, 255),
    "byte11": (0x0B, "B", 0, 255),
    "byte12": (0x0C, "B", 0, 255),
    "final_palette": (0x0D, "B", 0, 255),
    "byte14": (0x0E, "B", 0, 255),
    "byte15": (0x0F, "B", 0, 255),
}


def read_stage_header(blob: bytes, path: Path) -> tuple[int, int]:
    if len(blob) < 16:
        raise ValueError(f"{path} is too small to be a .m file")
    width, height = struct.unpack_from("<II", blob, 0)
    if blob[8:16] != b"Hello1.0":
        raise ValueError(f"{path} is not a Hello1.0 .m file")
    expected = 16 + width * height * 16
    if len(blob) < expected:
        raise ValueError(f"{path} is truncated: expected at least {expected} bytes, got {len(blob)}")
    return width, height


def read_field(blob: bytes | bytearray, offset: int, fmt: str) -> int:
    if fmt == "h":
        return struct.unpack_from("<h", blob, offset)[0]
    return blob[offset]


def write_field(blob: bytearray, offset: int, fmt: str, value: int) -> None:
    if fmt == "h":
        struct.pack_into("<h", blob, offset, value)
    else:
        blob[offset] = value


def require_int(change: dict[str, Any], key: str) -> int:
    value = change.get(key)
    if not isinstance(value, int):
        raise ValueError(f"change missing integer {key}: {change!r}")
    return value


def resolve_source(root: Path, patch: dict[str, Any], source: Path | None) -> Path:
    if source is not None:
        return source.resolve()
    stage = patch.get("stage")
    if not isinstance(stage, str) or not stage:
        raise ValueError("patch has no stage; pass --source explicitly")
    return find_game_dir(root) / f"{stage}.m"


def resolve_output(root: Path, patch: dict[str, Any], out: Path) -> Path:
    stage = patch.get("stage")
    stage_name = Path(stage if isinstance(stage, str) and stage else "edited_stage").stem
    out_path = out if out.is_absolute() else root / out
    if out_path.suffix.lower() == ".m":
        return out_path
    return out_path / f"{stage_name}.m"


def validate_and_collect(blob: bytes, width: int, height: int, patch: dict[str, Any], force: bool) -> list[tuple[int, str, int, int, int, int]]:
    changes = patch.get("changes")
    if not isinstance(changes, list):
        raise ValueError("patch changes must be a list")
    edits: list[tuple[int, str, int, int, int, int]] = []
    mismatches: list[str] = []
    for n, change in enumerate(changes):
        if not isinstance(change, dict):
            raise ValueError(f"change {n} is not an object")
        x = require_int(change, "x")
        y = require_int(change, "y")
        field = change.get("field")
        if not isinstance(field, str) or field not in FIELD_LAYOUT:
            raise ValueError(f"change {n} has unsupported field {field!r}")
        before = require_int(change, "before")
        after = require_int(change, "after")
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"change {n} cell out of range: {x},{y} for {width}x{height}")
        field_offset, fmt, min_value, max_value = FIELD_LAYOUT[field]
        if not (min_value <= after <= max_value):
            raise ValueError(f"change {n} value {after} out of range for {field}")
        if not (min_value <= before <= max_value):
            raise ValueError(f"change {n} before value {before} out of range for {field}")
        record_offset = 16 + (y * width + x) * 16
        absolute_offset = record_offset + field_offset
        current = read_field(blob, absolute_offset, fmt)
        if current != before and not force:
            mismatches.append(f"#{n} {x},{y} {field}: source has {current}, patch before is {before}")
        edits.append((absolute_offset, fmt, current, before, after, n))
    if mismatches:
        sample = "\n".join(mismatches[:12])
        extra = "" if len(mismatches) <= 12 else f"\n... {len(mismatches) - 12} more"
        raise ValueError(f"patch/source mismatch; refusing to write without --force:\n{sample}{extra}")
    return edits


def apply_patch_file(root: Path, patch_path: Path, out: Path, source: Path | None, force: bool, dry_run: bool) -> dict[str, Any]:
    patch = json.loads(patch_path.read_text(encoding="utf-8"))
    if patch.get("format") != "san-editor-patch-v1":
        raise ValueError(f"unsupported patch format: {patch.get('format')!r}")
    source_path = resolve_source(root, patch, source)
    blob = bytearray(source_path.read_bytes())
    width, height = read_stage_header(blob, source_path)
    edits = validate_and_collect(blob, width, height, patch, force)
    output_path = resolve_output(root, patch, out)
    if not dry_run:
        for absolute_offset, fmt, _current, _before, after, _n in edits:
            write_field(blob, absolute_offset, fmt, after)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(blob)
    return {
        "source": str(source_path),
        "output": str(output_path),
        "stage": patch.get("stage"),
        "width": width,
        "height": height,
        "changes": len(edits),
        "dry_run": dry_run,
        "forced": force,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a San map editor JSON patch to a copied .m file.")
    parser.add_argument("patch", type=Path, help="Path to a san-editor-patch-v1 JSON file")
    parser.add_argument("root", nargs="?", default=".", type=Path, help="Project root containing the game directory")
    parser.add_argument("--source", type=Path, help="Source .m file; defaults to <game_dir>/<patch stage>.m")
    parser.add_argument("--out", default=Path("derived/edited"), type=Path, help="Output .m file or output directory")
    parser.add_argument("--force", action="store_true", help="Apply even when patch before values do not match the source .m")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing")
    args = parser.parse_args()

    try:
        result = apply_patch_file(args.root.resolve(), args.patch.resolve(), args.out, args.source, args.force, args.dry_run)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
