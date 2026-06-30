from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import san_tools.pipelines.export_stage_sidecar_tables as tables


FAMILY_CONFIGS: dict[str, dict[str, int]] = {
    "general_entry": {"anchor_value": 224, "anchor_index": 4},
    "troop_entry": {"anchor_value": 224, "anchor_index": 0},
    "faction_or_ruler": {"anchor_value": 96, "anchor_index": 0},
    "city_or_structure": {"anchor_value": 92, "anchor_index": 2},
}


def normalize_family_words(words: list[int], *, anchor_value: int, anchor_index: int) -> tuple[list[int], int] | None:
    hits = [index for index, value in enumerate(words) if value == anchor_value]
    if not hits:
        return None
    anchor = hits[0]
    shift = (anchor - anchor_index) % len(words)
    rotated = words[shift:] + words[:shift]
    return rotated, anchor


def summarize_family_rows(rows: list[dict[str, object]], family_name: str) -> dict[str, object]:
    config = FAMILY_CONFIGS[family_name]
    anchor_positions: Counter[int] = Counter()
    column_counters = [Counter() for _ in range(38)]
    sample_rows: list[dict[str, object]] = []
    text_layouts: Counter[str] = Counter()
    normalized_count = 0
    skipped_count = 0

    for row in rows:
        words = [int(row[f"w{index:02d}"]) for index in range(38)]
        normalized = normalize_family_words(
            words,
            anchor_value=config["anchor_value"],
            anchor_index=config["anchor_index"],
        )
        if normalized is None:
            skipped_count += 1
            continue
        rotated, anchor = normalized
        normalized_count += 1
        anchor_positions[anchor] += 1
        text_layout = str(row["text_layout"])
        text_layouts[text_layout] += 1
        for index, value in enumerate(rotated):
            column_counters[index][value] += 1
        if len(sample_rows) < 12:
            sample_rows.append(
                {
                    "stage": row["stage"],
                    "record_index": row["record_index"],
                    "text_layout": text_layout,
                    "texts_joined": row["texts_joined"],
                    "normalized_nonzero_words": [
                        f"w{index:02d}={value}"
                        for index, value in enumerate(rotated)
                        if value
                    ],
                }
            )

    # 只保留在家族内部足够稳定的列，减少输出噪音。
    stable_columns: list[dict[str, object]] = []
    threshold = max(8, normalized_count // 8)
    for index, counter in enumerate(column_counters):
        common = counter.most_common(6)
        if not common:
            continue
        top_value, top_count = common[0]
        if top_count < threshold:
            continue
        stable_columns.append(
            {
                "word_index": index,
                "top_values": [
                    {"value": value, "count": count}
                    for value, count in common
                ],
            }
        )

    return {
        "family_name": family_name,
        "anchor_value": config["anchor_value"],
        "anchor_index": config["anchor_index"],
        "row_count": len(rows),
        "normalized_count": normalized_count,
        "skipped_count": skipped_count,
        "anchor_positions": [
            {"word_index": word_index, "count": count}
            for word_index, count in anchor_positions.most_common()
        ],
        "top_text_layouts": [
            {"text_layout": text_layout, "count": count}
            for text_layout, count in text_layouts.most_common(12)
        ],
        "stable_columns": stable_columns,
        "sample_rows": sample_rows,
    }


def build_alignment_payload(root: Path) -> dict[str, object]:
    payload = tables.build_tables(root)
    stg_rows = payload["tables"]["stg_records"]
    results: list[dict[str, object]] = []
    for family_name in FAMILY_CONFIGS:
        family_rows = [
            row
            for row in stg_rows
            if row["family_guess"] == family_name
        ]
        results.append(summarize_family_rows(family_rows, family_name))
    return {
        "game_dir": payload["game_dir"],
        "families": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze aligned .stg family record layouts.")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("derived/sidecar_analysis/stg_family_alignment.json"),
    )
    args = parser.parse_args()

    payload = build_alignment_payload(args.root)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
