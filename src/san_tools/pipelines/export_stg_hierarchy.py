from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from san_tools.pipelines.export_stg_phase7_links import load_castle_table, load_history_table, normalize_words
from san_tools.pipelines.export_stg_raw_chain import build_rows as build_raw_chain


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


def split_texts(texts_joined: object) -> list[str]:
    return [part.strip() for part in str(texts_joined or "").split(" | ") if part.strip()]


def words_from_raw_row(row: dict[str, object]) -> list[int]:
    return [int(row.get(f"w{index:02d}", 0) or 0) for index in range(38)]


def city_name_from_row(row: dict[str, object], castle_by_name: dict[str, dict[str, int]], castle_by_id: dict[int, dict[str, object]]) -> str:
    texts = split_texts(row.get("texts_joined", ""))
    for text in reversed(texts):
        if text in castle_by_name:
            return text
    words = words_from_raw_row(row)
    normalized = normalize_words(words, anchor_value=92, anchor_index=0)
    if normalized:
        rotated, _anchor = normalized
        city = castle_by_id.get(rotated[12])
        if city:
            return str(city["name"])
    return texts[-1] if texts else ""


def general_name_from_row(row: dict[str, object], history_by_name: dict[str, dict[str, int]]) -> str:
    texts = split_texts(row.get("texts_joined", ""))
    for text in texts:
        if text in history_by_name:
            return text
    return texts[0] if texts else ""


def faction_name_from_row(row: dict[str, object]) -> str:
    texts = split_texts(row.get("texts_joined", ""))
    for text in texts:
        if text not in {"禤a", "中立國家"}:
            return text
    return texts[0] if texts else ""


def classify_role(row: dict[str, object], castle_by_name: dict[str, dict[str, int]], history_by_name: dict[str, dict[str, int]]) -> str:
    family = str(row.get("family_guess", ""))
    texts = split_texts(row.get("texts_joined", ""))
    words = words_from_raw_row(row)
    joined = " | ".join(texts)
    has_92 = 92 in words
    has_96 = 96 in words
    has_224 = 224 in words
    has_city_name = any(text in castle_by_name for text in texts)
    has_general_name = any(text in history_by_name for text in texts)

    if family == "scenario_title":
        return "scenario_title"
    # 96 是当前最强的势力块锚点；有些势力记录没有被旧 family 识别出来，例如 劉備、劉表、中立國。
    if family in {"faction_or_ruler", "faction_96_family"} or (has_96 and not has_city_name and ("家" in texts or "禤a" in texts or "中立國" in texts)):
        return "force_start"
    # 92 是当前最强的城池块锚点；少数城池首记录只有城池名，92 落在附近续记录内。
    if family == "city_92_family" or (has_92 and has_city_name) or (has_city_name and not has_96 and not has_224):
        return "city_start"
    if family == "general_entry" or (has_224 and has_general_name):
        return "general"
    if family == "troop_entry":
        return "troop"
    if family in {"city_or_structure"}:
        if "山寨" in joined:
            return "structure"
        return "city_payload"
    if family == "bandit_entry":
        return "structure"
    if family in {"zero_record", "binary_record"}:
        return family
    if texts:
        return "text_record"
    return "unknown_record"


def compact_record(row: dict[str, object], role: str) -> dict[str, object]:
    return {
        "record_index": row["record_index"],
        "file_offset": row["file_offset"],
        "role": role,
        "family_guess": row["family_guess"],
        "texts_joined": row["texts_joined"],
        "nonzero_words": row["nonzero_words"],
    }


def ensure_force(forces: list[dict[str, object]], force_index: int, name: str, source_record: dict[str, object] | None) -> dict[str, object]:
    force = {
        "force_index": force_index,
        "force_name": name,
        "source_record": source_record,
        "cities": [],
        "generals_without_city": [],
        "troops_without_city": [],
        "loose_records": [],
        "role_counts": {},
    }
    forces.append(force)
    return force


def add_role_count(target: dict[str, object], role: str) -> None:
    counts = target.setdefault("role_counts", {})
    counts[role] = int(counts.get(role, 0)) + 1


def build_hierarchy(root: Path, stage: str) -> dict[str, object]:
    raw_payload = build_raw_chain(root, stage)
    records = list(raw_payload["records"])
    txt_dir = root / "uft8-game-txt"
    castle_by_name = load_castle_table(txt_dir)
    history_by_name = load_history_table(txt_dir)
    castle_by_id = {int(info["city_id"]): {"name": name, **info} for name, info in castle_by_name.items()}

    forces: list[dict[str, object]] = []
    flat_rows: list[dict[str, object]] = []
    scenario_records: list[dict[str, object]] = []
    current_force: dict[str, object] | None = None
    current_city: dict[str, object] | None = None

    # 当前层级规则：原始顺序优先。势力记录开新势力，城市记录开新城池，后续武将/士兵挂到当前城池。
    for row in records:
        role = classify_role(row, castle_by_name, history_by_name)
        record = compact_record(row, role)

        if role == "scenario_title":
            scenario_records.append(record)
            flat_rows.append({**record, "force_index": None, "force_name": "", "city_index": None, "city_name": ""})
            continue

        if role == "force_start":
            current_force = ensure_force(forces, len(forces) + 1, faction_name_from_row(row), record)
            current_city = None
            add_role_count(current_force, role)
            flat_rows.append({**record, "force_index": current_force["force_index"], "force_name": current_force["force_name"], "city_index": None, "city_name": ""})
            continue

        if current_force is None:
            current_force = ensure_force(forces, len(forces) + 1, "未命名前置势力块", None)

        if role == "city_start":
            city_name = city_name_from_row(row, castle_by_name, castle_by_id)
            current_city = {
                "city_index_in_force": len(current_force["cities"]) + 1,
                "city_name": city_name,
                "source_record": record,
                "generals": [],
                "troops": [],
                "records": [],
                "role_counts": {},
            }
            current_force["cities"].append(current_city)
            add_role_count(current_force, role)
            add_role_count(current_city, role)
            flat_rows.append({**record, "force_index": current_force["force_index"], "force_name": current_force["force_name"], "city_index": current_city["city_index_in_force"], "city_name": current_city["city_name"]})
            continue

        add_role_count(current_force, role)
        if current_city is not None:
            add_role_count(current_city, role)

        if role == "general":
            general = {**record, "general_name": general_name_from_row(row, history_by_name)}
            if current_city is not None:
                current_city["generals"].append(general)
            else:
                current_force["generals_without_city"].append(general)
        elif role == "troop":
            if current_city is not None:
                current_city["troops"].append(record)
            else:
                current_force["troops_without_city"].append(record)
        elif current_city is not None:
            current_city["records"].append(record)
        else:
            current_force["loose_records"].append(record)

        flat_rows.append({**record, "force_index": current_force["force_index"], "force_name": current_force["force_name"], "city_index": current_city["city_index_in_force"] if current_city else None, "city_name": current_city["city_name"] if current_city else ""})

    summary_rows: list[dict[str, object]] = []
    for force in forces:
        if not force["cities"]:
            summary_rows.append({
                "force_index": force["force_index"],
                "force_name": force["force_name"],
                "city_index": None,
                "city_name": "",
                "general_count": len(force["generals_without_city"]),
                "troop_count": len(force["troops_without_city"]),
                "attached_record_count": len(force["loose_records"]),
                "role_counts": json.dumps(force["role_counts"], ensure_ascii=False, sort_keys=True),
            })
        for city in force["cities"]:
            summary_rows.append({
                "force_index": force["force_index"],
                "force_name": force["force_name"],
                "city_index": city["city_index_in_force"],
                "city_name": city["city_name"],
                "general_count": len(city["generals"]),
                "troop_count": len(city["troops"]),
                "attached_record_count": len(city["records"]),
                "role_counts": json.dumps(city["role_counts"], ensure_ascii=False, sort_keys=True),
            })

    return {
        "stage": stage,
        "raw_header": raw_payload["header"],
        "notes": [
            "本导出按 .stg 原始记录顺序恢复层级，force/city 只是当前可验证的块边界推断，不是已确认字段名。",
            "遇到 faction_or_ruler 开始新势力块；遇到城市名或 city_92_family 开始新城池块；随后 general/troop 先挂到当前城池。",
            "slot/context_owner_slot_consensus 已降级为旧脚本的临时线索，不在本层级导出中作为 owner 结论使用。",
        ],
        "summary": {
            "record_count": len(records),
            "force_count": len(forces),
            "city_block_count": sum(len(force["cities"]) for force in forces),
            "role_counts": dict(Counter(str(row["role"]) for row in flat_rows)),
            "family_counts": dict(Counter(str(row["family_guess"]) for row in flat_rows)),
        },
        "scenario_records": scenario_records,
        "forces": forces,
        "tables": {
            "record_chain": flat_rows,
            "force_city_summary": summary_rows,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="把单个 .stg 导出为剧本/势力/城池/武将/士兵层级。")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", default="stage01")
    parser.add_argument("--out-dir", type=Path, default=Path("derived/sidecar_analysis/hierarchy"))
    args = parser.parse_args()

    payload = build_hierarchy(args.root.resolve(), args.stage)
    out_dir = args.out_dir / args.stage
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "stg_hierarchy.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_dir / "stg_hierarchy_records.csv", payload["tables"]["record_chain"])
    write_csv(out_dir / "stg_force_city_summary.csv", payload["tables"]["force_city_summary"])
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
