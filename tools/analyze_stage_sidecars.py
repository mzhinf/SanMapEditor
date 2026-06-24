from __future__ import annotations

import argparse
import json
import re
import struct
from collections import Counter
from pathlib import Path

SIDECAR_MODELS = {
    "spr": {"header": 12, "stride": 36, "confidence": "medium"},
    "dor": {"header": 16, "stride": 60, "confidence": "low"},
    "evt": {"header": 8, "stride": 72, "confidence": "medium"},
    "stg": {"header": 8, "stride": 76, "confidence": "medium"},
}

ASCII_TOKEN_RE = re.compile(rb"[A-Za-z][A-Za-z0-9_]{2,15}")


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


def decode_cp950_zstr(blob: bytes, start: int, stop: int) -> str | None:
    raw = blob[start:stop].split(b"\x00", 1)[0]
    if not raw:
        return None
    try:
        return raw.decode("cp950")
    except UnicodeDecodeError:
        return None


def extract_ascii_tokens(blob: bytes, limit: int = 16) -> list[str]:
    seen: list[str] = []
    for match in ASCII_TOKEN_RE.finditer(blob):
        token = match.group().decode("ascii")
        if token not in seen:
            seen.append(token)
        if len(seen) >= limit:
            break
    return seen


def decode_text_candidate(raw: bytes) -> str | None:
    if len(raw) >= 4 and all(32 <= byte < 127 for byte in raw):
        return raw.decode("ascii")
    try:
        text = raw.decode("cp950")
    except UnicodeDecodeError:
        return None
    if not any(ord(char) > 127 for char in text):
        return None
    if not all((32 <= byte < 127) or byte >= 0x81 for byte in raw):
        return None
    return text


def extract_text_segments(blob: bytes, limit: int = 24, max_bytes: int = 48) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    seen: set[str] = set()
    start = 0
    for index, byte in enumerate(blob + b"\x00"):
        if byte != 0:
            continue
        raw = blob[start:index]
        offset = start
        start = index + 1
        if not (2 <= len(raw) <= max_bytes):
            continue
        text = decode_text_candidate(raw)
        if not text or text in seen:
            continue
        seen.add(text)
        results.append({"offset": offset, "text": text})
        if len(results) >= limit:
            break
    return results


def build_record_model(blob: bytes, header: int, stride: int, confidence: str) -> dict[str, object]:
    payload = max(0, len(blob) - header)
    return {
        "assumed_header": header,
        "stride": stride,
        "confidence": confidence,
        "record_count_floor": payload // stride,
        "tail_bytes": payload % stride,
        "exact_divisible": payload % stride == 0,
    }


def extract_record_string_previews(
    blob: bytes,
    header: int,
    stride: int,
    *,
    limit: int = 12,
    max_strings_per_record: int = 4,
) -> list[dict[str, object]]:
    previews: list[dict[str, object]] = []
    record_count = max(0, (len(blob) - header) // stride)
    for record_index in range(record_count):
        start = header + record_index * stride
        record = blob[start : start + stride]
        strings = extract_text_segments(record, limit=max_strings_per_record, max_bytes=24)
        if not strings:
            continue
        u32_head = [
            struct.unpack_from("<I", record, offset)[0]
            for offset in range(0, min(24, len(record) - 3), 4)
        ]
        previews.append(
            {
                "record_index": record_index,
                "strings": strings,
                "u32_head": u32_head,
            }
        )
        if len(previews) >= limit:
            break
    return previews


def summarize_sidecar(path: Path) -> dict[str, object]:
    suffix = path.suffix.lower().lstrip(".")
    blob = path.read_bytes()
    head = blob[:96]
    dword_count = min(len(head) // 4, 12)
    dwords = [struct.unpack_from("<I", head, i * 4)[0] for i in range(dword_count)]
    ascii_preview = "".join(chr(b) if 32 <= b < 127 else "." for b in head[:32])
    summary: dict[str, object] = {
        "name": path.name,
        "size": len(blob),
        "ascii_preview": ascii_preview,
        "dwords": dwords,
    }
    model = SIDECAR_MODELS.get(suffix)
    if model:
        header = model["header"]
        stride = model["stride"]
        summary["record_model"] = build_record_model(blob, header, stride, model["confidence"])
    if suffix == "stg":
        summary["title_cp950"] = decode_cp950_zstr(blob, 8, 40)
        if len(blob) >= 0x2C:
            summary["year_start_candidate"] = struct.unpack_from("<I", blob, 0x24)[0]
            summary["year_end_candidate"] = struct.unpack_from("<I", blob, 0x28)[0]
        summary["decoded_strings_preview"] = extract_text_segments(blob)
        summary["record_string_previews"] = extract_record_string_previews(blob, 8, 76)
    elif suffix == "evt":
        summary["ascii_tokens"] = extract_ascii_tokens(blob)
        summary["decoded_strings_preview"] = extract_text_segments(blob)
        summary["record_string_previews"] = extract_record_string_previews(blob, 8, 72)
    elif suffix == "spr":
        meta: dict[str, object] = {}
        if blob.startswith(b"Soldier Data"):
            meta["ascii_magic"] = "Soldier Data"
            meta["magic_len"] = 12
        if len(blob) >= 20:
            meta["meta_dwords"] = [struct.unpack_from("<I", blob, 12)[0], struct.unpack_from("<I", blob, 16)[0]]
            payload = blob[20:]
            meta["post_meta_nonzero_bytes"] = sum(1 for byte in payload if byte)
            meta["post_meta_all_zero"] = not any(payload)
            meta["record_model_after_meta20"] = build_record_model(blob[20:], 0, 36, "low")
            record_count = len(payload) // 36
            meta["active_records_after_meta20"] = sum(
                1
                for index in range(record_count)
                if any(payload[index * 36 : (index + 1) * 36])
            )
        summary["meta_prefix"] = meta
    elif suffix == "dor":
        meta = {}
        if blob.startswith(b"Door    Data"):
            meta["ascii_magic"] = "Door    Data"
            meta["magic_len"] = 12
        if len(blob) >= 16:
            meta["meta_dword"] = struct.unpack_from("<I", blob, 12)[0]
            payload = blob[16:]
            meta["post_header_nonzero_bytes"] = sum(1 for byte in payload if byte)
            meta["post_header_all_zero"] = not any(payload)
        summary["meta_prefix"] = meta
    return summary


def summarize_grid_relationship(s_data: bytes | None, x_data: bytes | None) -> dict[str, object] | None:
    if s_data is None or x_data is None or len(s_data) != len(x_data):
        return None
    both_non240 = 0
    s_only = 0
    x_only = 0
    both_240 = 0
    same_non240 = 0
    for s_byte, x_byte in zip(s_data, x_data):
        s_non240 = s_byte != 240
        x_non240 = x_byte != 240
        if s_non240 and x_non240:
            both_non240 += 1
            if s_byte == x_byte:
                same_non240 += 1
        elif s_non240:
            s_only += 1
        elif x_non240:
            x_only += 1
        else:
            both_240 += 1
    return {
        "both_non240": both_non240,
        "s_only": s_only,
        "x_only": x_only,
        "both_240": both_240,
        "same_non240": same_non240,
        "same_non240_ratio": round(same_non240 / both_non240, 6) if both_non240 else 0.0,
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
    grids: dict[str, object] = {}
    s_data = None
    x_data = None
    for suffix in ("s", "x"):
        side_path = game_dir / f"{stem}.{suffix}"
        if not side_path.exists():
            continue
        data = side_path.read_bytes()
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
        grids["s_x_mask_relationship"] = summarize_grid_relationship(s_data, x_data)
    summary["grids"] = grids
    sidecars = {}
    for suffix in ("stg", "spr", "dor", "evt"):
        side_path = game_dir / f"{stem}.{suffix}"
        if side_path.exists():
            sidecars[suffix] = summarize_sidecar(side_path)
    summary["sidecars"] = sidecars
    return summary


def summarize_exe_strings(game_dir: Path) -> dict[str, object]:
    blob = (game_dir / "Emperor.exe").read_bytes()
    imagebase = 0x400000
    names = {
        ".s": b".s\x00",
        ".x": b".x\x00",
        ".m": b".m\x00",
        ".evt": b".evt\x00",
        ".dor": b".dor\x00",
        ".spr": b".spr\x00",
    }
    contexts = {}
    for name, pat in names.items():
        offset = blob.find(pat)
        if offset < 0:
            continue
        va = imagebase + offset
        start = max(0, offset - 24)
        end = min(len(blob), offset + 48)
        chunk = blob[start:end]
        ref_pattern = struct.pack("<I", va)
        refs: list[int] = []
        search_from = 0
        while True:
            hit = blob.find(ref_pattern, search_from)
            if hit < 0:
                break
            refs.append(hit)
            search_from = hit + 1
        contexts[name] = {
            "offset": offset,
            "va": va,
            "xref_offsets": refs,
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
