from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import san_tools.analysis.analyze_stage_sidecars as sidecars

STG_HEADER_SIZE = 8
STG_STRIDE = 76


def find_stage_file(root: Path, stage: str) -> Path:
    game_dir = sidecars.find_game_dir(root)
    path = game_dir / f"{stage}.stg"
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_words(words: list[int], anchor_value: int, anchor_index: int) -> tuple[list[int], int] | None:
    hits = [index for index, value in enumerate(words) if value == anchor_value]
    if not hits:
        return None
    anchor = hits[0]
    shift = (anchor - anchor_index) % len(words)
    return words[shift:] + words[:shift], anchor


def text_variants(texts: list[str]) -> list[str]:
    return [text.strip() for text in texts if text.strip()]


def city_or_structure_subtype(texts: list[str], normalized_words: list[int] | None) -> str:
    joined = " | ".join(texts)
    if joined == "城市":
        return "generic_city_payload"
    if "山寨" in joined:
        return "bandit_structure"
    if "W城市" in joined or "W城市3" in joined:
        if normalized_words and any(normalized_words[index] for index in (14, 18, 20, 22, 24, 34, 36)):
            return "named_city_payload"
        return "named_city_label"
    return "other"


def summarize_nonzero_words(words: list[int], limit: int = 24) -> str:
    parts = [f"w{index:02d}={value}" for index, value in enumerate(words) if value]
    return ", ".join(parts[:limit])


def build_rows(root: Path, stage: str) -> dict[str, object]:
    stage_path = find_stage_file(root, stage)
    blob = stage_path.read_bytes()
    if len(blob) < STG_HEADER_SIZE:
        raise ValueError(f"{stage_path} is too small")

    header_words = sidecars.read_u16_words(blob[:STG_HEADER_SIZE])
    payload = blob[STG_HEADER_SIZE:]
    record_count = len(payload) // STG_STRIDE
    tail = payload[record_count * STG_STRIDE :]

    rows: list[dict[str, object]] = []
    for record_index in range(record_count):
        file_offset = STG_HEADER_SIZE + record_index * STG_STRIDE
        record = blob[file_offset : file_offset + STG_STRIDE]
        text_items = sidecars.extract_text_segments(record, limit=8, max_bytes=24)
        texts = [str(item["text"]) for item in text_items]
        words = sidecars.read_u16_words(record)
        ascii_tokens = sidecars.extract_ascii_tokens(record)
        family_guess = sidecars.guess_record_family("stg", record_index, texts, words, ascii_tokens)
        if not texts and not any(words):
            family_guess = "zero_record"
        elif not texts and any(words):
            family_guess = "binary_record"

        city_norm = normalize_words(words, 92, 2)
        faction_norm = normalize_words(words, 96, 0)
        general_norm = normalize_words(words, 224, 4)

        entry: dict[str, object] = {
            "stage": stage,
            "record_index": record_index,
            "file_offset": file_offset,
            "family_guess": family_guess,
            "texts_joined": " | ".join(text_variants(texts)),
            "text_layout": " | ".join(f"{int(item['offset'])}:{item['text']}" for item in text_items),
            "ascii_tokens": " | ".join(ascii_tokens),
            "nonzero_words": summarize_nonzero_words(words),
            "has_92": int(92 in words),
            "has_96": int(96 in words),
            "has_224": int(224 in words),
            "city_anchor_raw_index": city_norm[1] if city_norm else None,
            "faction_anchor_raw_index": faction_norm[1] if faction_norm else None,
            "general_anchor_raw_index": general_norm[1] if general_norm else None,
            "raw_hex": record.hex(),
        }
        for index, value in enumerate(words):
            entry[f"w{index:02d}"] = value

        if city_norm:
            rotated = city_norm[0]
            entry["city_subtype_guess"] = city_or_structure_subtype(texts, rotated)
            for index, value in enumerate(rotated):
                entry[f"c{index:02d}"] = value
        else:
            entry["city_subtype_guess"] = ""

        if faction_norm:
            rotated = faction_norm[0]
            for index, value in enumerate(rotated):
                entry[f"f{index:02d}"] = value

        if general_norm:
            rotated = general_norm[0]
            for index, value in enumerate(rotated):
                entry[f"g{index:02d}"] = value

        rows.append(entry)

    return {
        "stage": stage,
        "stage_path": str(stage_path),
        "header": {
            "header_size": STG_HEADER_SIZE,
            "stride": STG_STRIDE,
            "file_size": len(blob),
            "header_u16_words": header_words,
            "record_count_floor": record_count,
            "tail_bytes": len(tail),
            "tail_hex": tail.hex(),
        },
        "records": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="按原始 76 字节 stride 导出单个 .stg 的完整记录链。")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", default="stage01")
    parser.add_argument("--out-dir", type=Path, default=Path("derived/sidecar_analysis/raw_chain"))
    args = parser.parse_args()

    payload = build_rows(args.root.resolve(), args.stage)
    out_dir = args.out_dir / args.stage
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "stg_raw_chain.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_dir / "stg_raw_chain.csv", payload["records"])
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
