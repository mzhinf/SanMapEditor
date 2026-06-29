from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.export_stg_phase7_links import (
    load_castle_table,
    load_history_table,
    normalize_words,
    read_tsv_rows,
)


CITY_FIELD_OFFSETS = {
    "city_id": 0,
    "house_type_or_zero": 2,
    "city_size": 4,
    "population": 6,
    "gold": 8,
    "grain": 10,
    "reserved_after_grain": 12,
    "dev": 14,
    "commerce": 16,
    "security": 18,
    "dev_max": 20,
    "commerce_max": 22,
    "security_max": 24,
    "map_x": 26,
    "map_y": 28,
    "prefect_general_id_candidate": 30,
}

TROOP_TEXT_ALIASES = {
    "步兵": "小步兵",
    "槍兵": "小槍兵",
    "枪兵": "小槍兵",
    "騎兵": "小騎兵",
    "骑兵": "小騎兵",
    "弓箭兵": "小弓箭手",
    "弓箭": "小弓箭手",
    "水兵": "小水軍",
    "投石車": "小投石車",
    "投石车": "小投石車",
}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def raw_words(record: dict[str, object]) -> list[int]:
    return [int(record.get(f"w{index:02d}", 0) or 0) for index in range(38)]


def stream_words(records: list[dict[str, object]], start_index: int, max_records: int = 10) -> list[int]:
    output: list[int] = []
    for record in records[start_index : start_index + max_records]:
        output.extend(raw_words(record))
    return output


def find_city_id_index(words: list[int], city_id: int) -> tuple[int | None, str]:
    if 92 in words:
        anchor = words.index(92)
        candidate = anchor + 12
        if candidate < len(words):
            return candidate, "anchor_92_plus_12"
    for index, value in enumerate(words):
        if value != city_id:
            continue
        if index + 28 >= len(words):
            continue
        size = words[index + CITY_FIELD_OFFSETS["city_size"]]
        pop = words[index + CITY_FIELD_OFFSETS["population"]]
        if 1 <= size <= 5 and 500 <= pop <= 5000:
            return index, "city_id_pattern"
    return None, "not_found"


def get_stream_value(words: list[int], base: int | None, offset: int) -> int | None:
    if base is None:
        return None
    index = base + offset
    if not 0 <= index < len(words):
        return None
    return words[index]


def city_source_rows(hierarchy: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for force in hierarchy["forces"]:
        for city in force["cities"]:
            rows.append(
                {
                    "force_index": force["force_index"],
                    "force_name": force["force_name"],
                    "city_index": city["city_index_in_force"],
                    "city_name": city["city_name"],
                    "source_record_index": city["source_record"]["record_index"],
                    "general_count": len(city["generals"]),
                    "troop_count": len(city["troops"]),
                    "attached_record_count": len(city["records"]),
                    "general_names": " | ".join(
                        str(general.get("general_name", ""))
                        for general in city["generals"]
                        if general.get("general_name")
                    ),
                }
            )
    return rows


def load_soldier_table(txt_dir: Path) -> dict[str, dict[str, int]]:
    rows = read_tsv_rows(txt_dir / "soldier.txt")
    result: dict[str, dict[str, int]] = {}
    for cols in rows[1:]:
        if len(cols) < 2:
            continue
        try:
            result[cols[0]] = {"soldier_id": int(cols[1])}
        except ValueError:
            continue
    return result


def normalize_troop_text(text: str) -> str:
    raw = str(text or "").strip()
    if raw in TROOP_TEXT_ALIASES:
        return TROOP_TEXT_ALIASES[raw]
    for key, normalized in TROOP_TEXT_ALIASES.items():
        if key in raw:
            return normalized
    return raw


def rotate_words(words: list[int], anchor: int, anchor_index: int = 0) -> list[int]:
    shift = (anchor - anchor_index) % len(words)
    return words[shift:] + words[:shift]


def score_troop_rotation(rotated: list[int], expected_soldier_id: int | None) -> int:
    score = 0
    if rotated and rotated[0] == 224:
        score += 4
    if expected_soldier_id is not None:
        if len(rotated) > 22 and rotated[22] == expected_soldier_id:
            score += 6
        if len(rotated) > 12 and rotated[12] == expected_soldier_id + 200:
            score += 5
        if len(rotated) > 14 and rotated[14] == expected_soldier_id + 97:
            score += 5
    if len(rotated) > 24 and rotated[24] in {0, 1}:
        score += 1
    if len(rotated) > 26 and rotated[26] in {0, 50}:
        score += 1
    if len(rotated) > 32 and rotated[32] in {0, 50}:
        score += 1
    return score


def choose_troop_rotation(
    words: list[int],
    troop_text: str,
    soldier_by_name: dict[str, dict[str, int]],
) -> tuple[list[int], int | None, str, int]:
    normalized_text = normalize_troop_text(troop_text)
    expected_soldier_id = soldier_by_name.get(normalized_text, {}).get("soldier_id")
    hits = [index for index, value in enumerate(words) if value == 224]
    if hits:
        scored: list[tuple[int, int, list[int]]] = []
        # 有些记录里不止一个 224；这里按兵种文本和已知编码簇选择最像“真锚点”的那个。
        for anchor in hits:
            rotated = rotate_words(words, anchor, anchor_index=0)
            scored.append((score_troop_rotation(rotated, expected_soldier_id), anchor, rotated))
        scored.sort(key=lambda item: (item[0], item[2][0] == 224, -item[1]), reverse=True)
        best_score, best_anchor, best_rotated = scored[0]
        method = "best_224_match" if len(hits) > 1 else "single_224"
        return best_rotated, best_anchor, method, best_score

    normalized = normalize_words(words, anchor_value=224, anchor_index=0)
    if normalized is None:
        return words[:], None, "no_224_found", 0
    rotated, anchor = normalized
    return rotated, anchor, "fallback_first_224", score_troop_rotation(rotated, expected_soldier_id)


def build_city_rows(root: Path, raw_records: list[dict[str, object]], hierarchy: dict[str, object]) -> list[dict[str, object]]:
    txt_dir = root / "uft8-game-txt"
    castle_by_name = load_castle_table(txt_dir)
    history_by_name = load_history_table(txt_dir)
    history_by_id = {int(info["general_id"]): name for name, info in history_by_name.items()}
    rows: list[dict[str, object]] = []
    for city in city_source_rows(hierarchy):
        city_name = str(city["city_name"])
        castle_info = castle_by_name.get(city_name, {})
        expected_city_id = int(castle_info.get("city_id", 0) or 0)
        start = int(city["source_record_index"])
        words = stream_words(raw_records, start, max_records=10)
        city_id_index, method = find_city_id_index(words, expected_city_id)
        anchor_index = words.index(92) if 92 in words else None

        row: dict[str, object] = {
            **city,
            "expected_city_id": expected_city_id or None,
            "expected_city_size": castle_info.get("city_size"),
            "expected_x": castle_info.get("x"),
            "expected_y": castle_info.get("y"),
            "anchor_92_stream_index": anchor_index,
            "city_id_stream_index": city_id_index,
            "city_id_detection_method": method,
        }
        for name, offset in CITY_FIELD_OFFSETS.items():
            row[f"candidate_{name}"] = get_stream_value(words, city_id_index, offset)

        prefect_id = row.get("candidate_prefect_general_id_candidate")
        if isinstance(prefect_id, int) and prefect_id > 0:
            row["candidate_prefect_name"] = history_by_id.get(prefect_id, "")
        else:
            row["candidate_prefect_name"] = ""
        row["prefect_in_city_generals"] = bool(
            row["candidate_prefect_name"] and row["candidate_prefect_name"] in str(city.get("general_names", ""))
        )
        row["city_id_match"] = row["candidate_city_id"] == row["expected_city_id"]
        row["city_size_match"] = row["candidate_city_size"] == row["expected_city_size"]
        row["map_x_match"] = row["candidate_map_x"] == row["expected_x"]
        row["map_y_match"] = row["candidate_map_y"] == row["expected_y"]
        row["header_stream_preview"] = " ".join(str(value) for value in words[:90])
        rows.append(row)
    return rows


def build_troop_rows(root: Path, raw_records: list[dict[str, object]], hierarchy: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    raw_by_index = {int(record["record_index"]): record for record in raw_records}
    soldier_by_name = load_soldier_table(root / "uft8-game-txt")
    for force in hierarchy["forces"]:
        for city in force["cities"]:
            for troop_order, troop in enumerate(city["troops"], start=1):
                record_index = int(troop["record_index"])
                raw = raw_by_index[record_index]
                words = raw_words(raw)
                troop_text = str(troop.get("texts_joined", ""))
                normalized_text = normalize_troop_text(troop_text)
                expected_soldier_id = soldier_by_name.get(normalized_text, {}).get("soldier_id")
                rotated, anchor, anchor_method, anchor_score = choose_troop_rotation(words, troop_text, soldier_by_name)
                candidate_soldier_code_plus200_t12 = rotated[12] if len(rotated) > 12 else None
                candidate_soldier_code_plus97_t14 = rotated[14] if len(rotated) > 14 else None
                candidate_soldier_id_t22 = rotated[22] if len(rotated) > 22 else None
                row: dict[str, object] = {
                    "force_index": force["force_index"],
                    "force_name": force["force_name"],
                    "city_index": city["city_index_in_force"],
                    "city_name": city["city_name"],
                    "troop_order_in_city": troop_order,
                    "record_index": record_index,
                    "troop_text": troop_text,
                    "troop_text_normalized": normalized_text,
                    "anchor_224_raw_index": anchor,
                    "troop_anchor_method": anchor_method,
                    "troop_anchor_score": anchor_score,
                    "expected_soldier_id_from_text": expected_soldier_id,
                    "candidate_soldier_code_plus200_t12": candidate_soldier_code_plus200_t12,
                    "candidate_soldier_code_plus97_t14": candidate_soldier_code_plus97_t14,
                    "candidate_soldier_id_t22": candidate_soldier_id_t22,
                    "candidate_troop_code_t12": candidate_soldier_code_plus200_t12,
                    "candidate_param_t14": candidate_soldier_code_plus97_t14,
                    "candidate_param_t22": candidate_soldier_id_t22,
                    "candidate_param_t24": rotated[24] if len(rotated) > 24 else None,
                    "candidate_param_t26": rotated[26] if len(rotated) > 26 else None,
                    "candidate_param_t32": rotated[32] if len(rotated) > 32 else None,
                    "candidate_force_or_block_t36": rotated[36] if len(rotated) > 36 else None,
                }
                row["candidate_soldier_id_matches_text"] = (
                    expected_soldier_id is not None and candidate_soldier_id_t22 == expected_soldier_id
                )
                row["candidate_soldier_code_cluster_consistent"] = (
                    expected_soldier_id is not None
                    and candidate_soldier_code_plus200_t12 == expected_soldier_id + 200
                    and candidate_soldier_code_plus97_t14 == expected_soldier_id + 97
                )
                for index, value in enumerate(rotated):
                    row[f"t{index:02d}"] = value
                rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 .stg 城池状态字段和士兵记录候选表。")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", default="stage01")
    parser.add_argument("--raw-dir", type=Path, default=Path("derived/sidecar_analysis/raw_chain"))
    parser.add_argument("--hierarchy-dir", type=Path, default=Path("derived/sidecar_analysis/hierarchy"))
    parser.add_argument("--out-dir", type=Path, default=Path("derived/sidecar_analysis/city_troop"))
    args = parser.parse_args()

    root = args.root.resolve()
    raw_payload = load_json(root / args.raw_dir / args.stage / "stg_raw_chain.json")
    hierarchy = load_json(root / args.hierarchy_dir / args.stage / "stg_hierarchy.json")
    raw_records = list(raw_payload["records"])

    city_rows = build_city_rows(root, raw_records, hierarchy)
    troop_rows = build_troop_rows(root, raw_records, hierarchy)

    out_dir = root / args.out_dir / args.stage
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": args.stage,
        "notes": [
            "city_state_candidates 以 city_id 位置为基准展开字段；有 92 锚时使用 anchor+12，没有 92 锚时按 city_id/size/population 组合定位。",
            "troop_candidates 现在会结合 soldier.txt 与兵种文本，在多个 224 命中里选择最像真实锚点的旋转结果。",
            "兵种 id 相关字段已经拆出 t12(+200)、t14(+97)、t22(原始 soldier_id) 三个编码簇；数量/等级字段仍需继续确认。",
        ],
        "summary": {
            "city_rows": len(city_rows),
            "city_id_matches": sum(1 for row in city_rows if row.get("city_id_match")),
            "city_size_matches": sum(1 for row in city_rows if row.get("city_size_match")),
            "map_x_matches": sum(1 for row in city_rows if row.get("map_x_match")),
            "map_y_matches": sum(1 for row in city_rows if row.get("map_y_match")),
            "prefect_name_candidates": sum(1 for row in city_rows if row.get("candidate_prefect_name")),
            "prefect_in_city_generals": sum(1 for row in city_rows if row.get("prefect_in_city_generals")),
            "troop_rows": len(troop_rows),
            "troop_rows_with_text_id": sum(1 for row in troop_rows if row.get("expected_soldier_id_from_text") is not None),
            "troop_rows_id_match_t22": sum(1 for row in troop_rows if row.get("candidate_soldier_id_matches_text")),
            "troop_rows_code_cluster_consistent": sum(
                1 for row in troop_rows if row.get("candidate_soldier_code_cluster_consistent")
            ),
        },
        "tables": {
            "city_state_candidates": city_rows,
            "troop_candidates": troop_rows,
        },
    }
    json_path = out_dir / "stg_city_troop_candidates.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_dir / "city_state_candidates.csv", city_rows)
    write_csv(out_dir / "troop_candidates.csv", troop_rows)
    print(json_path)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

