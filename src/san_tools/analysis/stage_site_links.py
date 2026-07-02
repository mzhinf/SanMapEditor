from __future__ import annotations

import argparse
import json
from pathlib import Path

from san_tools.analysis.analyze_dor import parse_dor
from san_tools.analysis.analyze_stage_sidecars import find_game_dir
from san_tools.pipelines.export_stg_city_troop_analysis import build_city_rows
from san_tools.pipelines.export_stg_hierarchy import build_hierarchy
from san_tools.pipelines.export_stg_raw_chain import build_rows as build_raw_chain


def normalize_int(value: object) -> int | None:
    """把可能来自 JSON 或表格的坐标值规范成整数。"""

    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    return int(text)


def missing_stage_link_payload(stage: str, reason: str) -> dict[str, object]:
    """返回编辑器可直接消费的“无据点联动数据”占位结构。"""

    return {
        "available": False,
        "stage": stage,
        "reason": reason,
        "cityCount": 0,
        "gateCount": 0,
        "matchedGateCount": 0,
        "unmatchedGateCount": 0,
        "cities": [],
        "gates": [],
        "sources": {},
    }


def build_stage_site_links(root: Path, stage: str) -> dict[str, object]:
    """读取同名 `.dor` / `.stg`，建立“城门 -> 据点”归属表。"""

    game_dir = find_game_dir(root)
    dor_path = game_dir / f"{stage}.dor"
    stg_path = game_dir / f"{stage}.stg"
    if not dor_path.exists():
        return missing_stage_link_payload(stage, f"缺少 {dor_path.name}，无法建立城门归属。")
    if not stg_path.exists():
        return missing_stage_link_payload(stage, f"缺少 {stg_path.name}，无法建立城门归属。")

    dor_groups = parse_dor(dor_path)
    raw_payload = build_raw_chain(root, stage)
    hierarchy = build_hierarchy(root, stage)
    city_rows = build_city_rows(root, list(raw_payload["records"]), hierarchy)

    cities: list[dict[str, object]] = []
    city_by_key: dict[str, dict[str, object]] = {}
    for row in city_rows:
        map_x = normalize_int(row.get("candidate_map_x"))
        map_y = normalize_int(row.get("candidate_map_y"))
        if map_x is None or map_y is None:
            continue
        site_key = f"{map_x},{map_y}"
        city = {
            "siteKey": site_key,
            "cityName": str(row.get("city_name", "")),
            "forceIndex": normalize_int(row.get("force_index")),
            "forceName": str(row.get("force_name", "")),
            "cityIndex": normalize_int(row.get("city_index")),
            "sourceRecordIndex": normalize_int(row.get("source_record_index")),
            "mapX": map_x,
            "mapY": map_y,
            "expectedX": normalize_int(row.get("expected_x")),
            "expectedY": normalize_int(row.get("expected_y")),
            "gateIndices": [],
            "gateCount": 0,
        }
        cities.append(city)
        city_by_key[site_key] = city

    gates: list[dict[str, object]] = []
    for group in dor_groups:
        group_index = int(group["group"])
        for door in group["doors"]:
            site_key = f"{door['site_x']},{door['site_y']}"
            city = city_by_key.get(site_key)
            gate = {
                "gateIndex": len(gates),
                "group": group_index,
                "doorIndex": int(door["index"]),
                "doorX": int(door["door_x"]),
                "doorY": int(door["door_y"]),
                "dir": int(door["dir"]),
                "siteX": int(door["site_x"]),
                "siteY": int(door["site_y"]),
                "siteKey": site_key,
                "cityName": city["cityName"] if city else "",
            }
            gates.append(gate)
            if city is not None:
                city["gateIndices"].append(gate["gateIndex"])

    matched_gate_count = 0
    for city in cities:
        city["gateCount"] = len(city["gateIndices"])
        matched_gate_count += city["gateCount"]

    return {
        "available": bool(cities) and bool(gates),
        "stage": stage,
        "reason": "",
        "cityCount": len(cities),
        "gateCount": len(gates),
        "matchedGateCount": matched_gate_count,
        "unmatchedGateCount": len(gates) - matched_gate_count,
        "cities": cities,
        "gates": gates,
        "sources": {
            "dor": str(dor_path),
            "stg": str(stg_path),
        },
    }


def export_stage_site_links(root: Path, stage: str, out_dir: Path) -> Path:
    """把据点联动结果导出为 JSON，便于单独核对。"""

    payload = build_stage_site_links(root.resolve(), stage)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{stage}_site_links.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="根据 `.dor` / `.stg` 建立城门与据点归属表。")
    parser.add_argument("root", nargs="?", default=".", type=Path, help="仓库根目录")
    parser.add_argument("--stage", default="stage01", help="关卡名，例如 stage01")
    parser.add_argument("--out-dir", type=Path, default=Path("derived/dor_analysis/site_links"), help="输出目录")
    return parser


def main() -> int:
    """命令行入口。"""

    parser = build_parser()
    args = parser.parse_args()
    root = args.root.resolve()
    out_path = export_stage_site_links(root, args.stage, args.out_dir)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "stage": payload["stage"],
                "available": payload["available"],
                "city_count": payload["cityCount"],
                "gate_count": payload["gateCount"],
                "matched_gate_count": payload["matchedGateCount"],
                "json_path": str(out_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
