from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.export_stg_city_troop_analysis import build_city_rows, build_troop_rows
from tools.export_stg_hierarchy import build_hierarchy
from tools.export_stg_raw_chain import build_rows as build_raw_chain
from tools.stage_ini_excel_codec import write_workbook


RAW_RECORD_HEADERS = [
    "stage",
    "record_index",
    "file_offset",
    "family_guess",
    "texts_joined",
    "text_layout",
    "ascii_tokens",
    "nonzero_words",
    "has_92",
    "has_96",
    "has_224",
    "city_anchor_raw_index",
    "faction_anchor_raw_index",
    "general_anchor_raw_index",
    "city_subtype_guess",
    "raw_hex",
    *[f"w{index:02d}" for index in range(38)],
]

CITY_STATE_HEADERS = [
    "force_index",
    "force_name",
    "city_index",
    "city_name",
    "source_record_index",
    "city_id_stream_index",
    "city_id_detection_method",
    "anchor_92_stream_index",
    "expected_city_id",
    "expected_city_size",
    "expected_x",
    "expected_y",
    "general_count",
    "troop_count",
    "attached_record_count",
    "general_names",
    "candidate_city_id",
    "candidate_house_type_or_zero",
    "candidate_city_size",
    "candidate_population",
    "candidate_gold",
    "candidate_grain",
    "candidate_reserved_after_grain",
    "candidate_dev",
    "candidate_commerce",
    "candidate_security",
    "candidate_dev_max",
    "candidate_commerce_max",
    "candidate_security_max",
    "candidate_map_x",
    "candidate_map_y",
    "candidate_prefect_general_id_candidate",
    "candidate_prefect_name",
    "prefect_in_city_generals",
    "city_id_match",
    "city_size_match",
    "map_x_match",
    "map_y_match",
]


def row_values(row: dict[str, object], headers: list[str]) -> list[object]:
    return [row.get(header, "") for header in headers]


def dict_rows_to_sheet(name: str, rows: list[dict[str, object]], preferred_headers: list[str] | None = None) -> dict[str, object]:
    # Excel 表头保持稳定，新增字段统一追加到后面，避免导入脚本依赖的列顺序漂移。
    headers = list(preferred_headers or [])
    seen = set(headers)
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                headers.append(key)
    return {
        "name": name,
        "headers": headers,
        "rows": [row_values(row, headers) for row in rows],
    }


def hierarchy_summary_rows(hierarchy: dict[str, object]) -> list[list[object]]:
    rows: list[list[object]] = []
    for force in hierarchy["forces"]:
        if not force["cities"]:
            rows.append(
                [
                    force["force_index"],
                    force["force_name"],
                    "",
                    "",
                    len(force["generals_without_city"]),
                    len(force["troops_without_city"]),
                    len(force["loose_records"]),
                    json.dumps(force["role_counts"], ensure_ascii=False, sort_keys=True),
                ]
            )
            continue
        for city in force["cities"]:
            rows.append(
                [
                    force["force_index"],
                    force["force_name"],
                    city["city_index_in_force"],
                    city["city_name"],
                    len(city["generals"]),
                    len(city["troops"]),
                    len(city["records"]),
                    json.dumps(city["role_counts"], ensure_ascii=False, sort_keys=True),
                ]
            )
    return rows


def build_workbook_sheets(root: Path, stage: str) -> list[dict[str, object]]:
    raw_payload = build_raw_chain(root, stage)
    hierarchy = build_hierarchy(root, stage)
    raw_records = list(raw_payload["records"])
    city_rows = build_city_rows(root, raw_records, hierarchy)
    troop_rows = build_troop_rows(root, raw_records, hierarchy)
    header = dict(raw_payload["header"])

    notes = [
        ["用途", "本工作簿用于 stageNN.stg 与 Excel 的字节级互转，并附带当前已确认的城池状态与士兵候选表。"],
        ["回写基准", "导入脚本优先使用 raw_records.raw_hex 重建每条 76 字节记录；未知字节不重算。"],
        ["可编辑表", "city_state 中的 candidate_* 字段可回写到连续 u16 流；troop_candidates 当前只读。"],
        ["安全原则", "未确认字段不要删除；raw_records、meta、tail_hex 是 round-trip 所需的保底数据。"],
    ]
    meta_rows = [
        ["stage", stage],
        ["source_path", raw_payload["stage_path"]],
        ["file_size", header["file_size"]],
        ["header_size", header["header_size"]],
        ["stride", header["stride"]],
        ["record_count", header["record_count_floor"]],
        ["tail_bytes", header["tail_bytes"]],
        ["header_hex", b"".join(int(value).to_bytes(2, "little") for value in header["header_u16_words"]).hex()],
        ["header_u16_words", json.dumps(header["header_u16_words"], ensure_ascii=False)],
        ["tail_hex", header["tail_hex"]],
    ]

    return [
        {"name": "说明", "headers": ["项目", "内容"], "rows": notes},
        {"name": "meta", "headers": ["key", "value"], "rows": meta_rows},
        dict_rows_to_sheet("raw_records", raw_records, RAW_RECORD_HEADERS),
        dict_rows_to_sheet("hierarchy_records", list(hierarchy["tables"]["record_chain"])),
        {
            "name": "force_city_summary",
            "headers": [
                "force_index",
                "force_name",
                "city_index",
                "city_name",
                "general_count",
                "troop_count",
                "attached_record_count",
                "role_counts",
            ],
            "rows": hierarchy_summary_rows(hierarchy),
        },
        dict_rows_to_sheet("city_state", city_rows, CITY_STATE_HEADERS),
        dict_rows_to_sheet("troop_candidates", troop_rows),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 .stg 字节级互转工作簿，并附带当前可读的层级与城池状态表。")
    parser.add_argument("root", nargs="?", default=".", type=Path, help="项目根目录")
    parser.add_argument("--stage", default="stage01", help="关卡名，例如 stage01")
    parser.add_argument("--out", type=Path, default=Path("outputs/stg_workbooks/stage01_stg.xlsx"), help="输出 xlsx 路径")
    args = parser.parse_args()

    root = args.root.resolve()
    out_path = args.out
    if not out_path.is_absolute():
        out_path = (root / out_path).resolve()
    sheets = build_workbook_sheets(root, args.stage)
    write_workbook(out_path, sheets)
    print(json.dumps({"xlsx": str(out_path), "sheet_count": len(sheets)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
