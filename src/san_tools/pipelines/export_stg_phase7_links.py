from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import san_tools.pipelines.export_stage_sidecar_tables as sidecar_tables


def read_tsv_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split("\t")]
        if any(part for part in parts):
            rows.append(parts)
    return rows


def load_history_table(txt_dir: Path) -> dict[str, dict[str, int]]:
    rows = read_tsv_rows(txt_dir / "History.txt")
    result: dict[str, dict[str, int]] = {}
    for cols in rows[1:]:
        if len(cols) < 3:
            continue
        try:
            result[cols[0]] = {
                "general_id": int(cols[1]),
                "history_faction_id": int(cols[2]),
            }
        except ValueError:
            continue
    return result


def load_castle_table(txt_dir: Path) -> dict[str, dict[str, int]]:
    rows = read_tsv_rows(txt_dir / "castle.txt")
    result: dict[str, dict[str, int]] = {}
    for cols in rows[1:]:
        if len(cols) < 16:
            continue
        try:
            result[cols[0]] = {
                "city_id": int(cols[1]),
                "house_type": int(cols[2]),
                "city_size": int(cols[3]),
                "population": int(cols[4]),
                "gold": int(cols[5]),
                "grain": int(cols[6]),
                "dev": int(cols[8]),
                "commerce": int(cols[9]),
                "security": int(cols[10]),
                "x": int(cols[14]),
                "y": int(cols[15]),
            }
        except ValueError:
            continue
    return result


def normalize_words(words: list[int], *, anchor_value: int, anchor_index: int) -> tuple[list[int], int] | None:
    hits = [index for index, value in enumerate(words) if value == anchor_value]
    if not hits:
        return None
    anchor = hits[0]
    shift = (anchor - anchor_index) % len(words)
    rotated = words[shift:] + words[:shift]
    return rotated, anchor


def text_variants(row: dict[str, object]) -> list[str]:
    raw = str(row.get("texts_joined", ""))
    return [part.strip() for part in raw.split(" | ") if part.strip()]


def choose_castle_name(row: dict[str, object], castle_map: dict[str, dict[str, int]]) -> str:
    variants = text_variants(row)
    for name in reversed(variants):
        if name in castle_map:
            return name
    return variants[-1] if variants else ""


def choose_history_name(row: dict[str, object], history_map: dict[str, dict[str, int]]) -> str:
    variants = text_variants(row)
    for name in variants:
        if name in history_map:
            return name
    return variants[0] if variants else ""


def first_slot_after(rows: list[dict[str, object]], start_index: int) -> int | None:
    for row in rows[start_index + 1 :]:
        slot = row.get("slot_candidate")
        if isinstance(slot, int) and slot > 0:
            return slot
    return None


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_stage_links(root: Path, stage: str) -> dict[str, object]:
    txt_dir = root / "uft8-game-txt"
    history_map = load_history_table(txt_dir)
    castle_map = load_castle_table(txt_dir)

    payload = sidecar_tables.build_tables(root, stages=[stage])
    stage_rows = [
        row
        for row in payload["tables"]["stg_records"]
        if str(row["stage"]) == stage
    ]

    normalized_rows: list[dict[str, object]] = []
    for row in stage_rows:
        words = [int(row[f"w{index:02d}"]) for index in range(38)]
        family = str(row["family_guess"])
        entry: dict[str, object] = {
            "stage": stage,
            "record_index": int(row["record_index"]),
            "family_guess": family,
            "texts_joined": str(row["texts_joined"]),
        }
        normalized_rows.append(entry)

        if family == "general_entry":
            normalized = normalize_words(words, anchor_value=224, anchor_index=4)
            if normalized is None:
                continue
            rotated, anchor_index = normalized
            history_name = choose_history_name(row, history_map)
            history_info = history_map.get(history_name, {})
            entry.update(
                {
                    "anchor_hit": anchor_index,
                    "slot_candidate": rotated[2],
                    "general_id_candidate": rotated[16],
                    "general_extra_candidate": rotated[18],
                    "history_name": history_name,
                    "history_general_id": history_info.get("general_id"),
                    "history_faction_id": history_info.get("history_faction_id"),
                    "general_id_match": rotated[16] == history_info.get("general_id"),
                }
            )
        elif family == "faction_or_ruler":
            normalized = normalize_words(words, anchor_value=96, anchor_index=0)
            if normalized is None:
                continue
            rotated, anchor_index = normalized
            entry.update(
                {
                    "anchor_hit": anchor_index,
                    "slot_candidate": rotated[12],
                    "ruler_general_id_candidate": rotated[14],
                    "faction_flag_candidate_a": rotated[16],
                    "faction_flag_candidate_b": rotated[20],
                    "faction_flag_candidate_c": rotated[22],
                }
            )
        elif family == "city_92_family":
            normalized = normalize_words(words, anchor_value=92, anchor_index=0)
            if normalized is None:
                continue
            rotated, anchor_index = normalized
            castle_name = choose_castle_name(row, castle_map)
            castle_info = castle_map.get(castle_name, {})
            entry.update(
                {
                    "anchor_hit": anchor_index,
                    "city_name": castle_name,
                    "slot_candidate": None,
                    "city_id_candidate": rotated[12],
                    "city_size_candidate": rotated[16],
                    "population_candidate": rotated[18],
                    "gold_candidate": rotated[20],
                    "grain_candidate": rotated[22],
                    "value24_candidate": rotated[24],
                    "dev_candidate": rotated[26],
                    "commerce_candidate": rotated[28],
                    "security_candidate": rotated[30],
                    "castle_city_id": castle_info.get("city_id"),
                    "castle_city_size": castle_info.get("city_size"),
                    "castle_x": castle_info.get("x"),
                    "castle_y": castle_info.get("y"),
                    "city_id_match": rotated[12] == castle_info.get("city_id"),
                    "city_size_match": rotated[16] == castle_info.get("city_size"),
                }
            )

    # 给城市记录追加前后邻接槽位，用于继续追 owner 字段。
    for index, row in enumerate(normalized_rows):
        if row["family_guess"] != "city_92_family":
            continue
        prev_slot = None
        for prev in reversed(normalized_rows[:index]):
            slot = prev.get("slot_candidate")
            if isinstance(slot, int) and slot > 0:
                prev_slot = slot
                break
        next_slot = first_slot_after(normalized_rows, index)
        consensus = prev_slot if prev_slot and prev_slot == next_slot else None
        row["context_prev_slot"] = prev_slot
        row["context_next_slot"] = next_slot
        row["context_owner_slot_consensus"] = consensus

    general_rows = [
        row
        for row in normalized_rows
        if row["family_guess"] == "general_entry"
    ]
    faction_rows = [
        row
        for row in normalized_rows
        if row["family_guess"] == "faction_or_ruler"
    ]
    city_rows = [
        row
        for row in normalized_rows
        if row["family_guess"] == "city_92_family"
    ]

    general_id_checked = [row for row in general_rows if row.get("history_general_id") is not None]
    general_id_matches = [row for row in general_id_checked if row.get("general_id_match")]
    city_id_checked = [row for row in city_rows if row.get("castle_city_id") is not None]
    city_id_matches = [row for row in city_id_checked if row.get("city_id_match")]
    city_size_matches = [row for row in city_id_checked if row.get("city_size_match")]

    return {
        "stage": stage,
        "history_source": str(txt_dir / "History.txt"),
        "castle_source": str(txt_dir / "castle.txt"),
        "summary": {
            "general_rows": len(general_rows),
            "faction_rows": len(faction_rows),
            "city_rows": len(city_rows),
            "general_id_checked": len(general_id_checked),
            "general_id_matches": len(general_id_matches),
            "city_id_checked": len(city_id_checked),
            "city_id_matches": len(city_id_matches),
            "city_size_matches": len(city_size_matches),
        },
        "tables": {
            "general_rows": general_rows,
            "faction_rows": faction_rows,
            "city_rows": city_rows,
            "all_rows": normalized_rows,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Phase 7 .stg linkage tables for one stage.")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", default="stage01", help="Stage stem such as stage01")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("derived/sidecar_analysis/phase7"),
        help="Output directory for JSON and CSV tables",
    )
    args = parser.parse_args()

    payload = build_stage_links(args.root.resolve(), args.stage)
    out_dir = args.out_dir / args.stage
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "stg_phase7_links.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_dir / "general_rows.csv", payload["tables"]["general_rows"])
    write_csv(out_dir / "faction_rows.csv", payload["tables"]["faction_rows"])
    write_csv(out_dir / "city_rows.csv", payload["tables"]["city_rows"])
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
