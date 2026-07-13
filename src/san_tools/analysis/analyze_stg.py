#!/usr/bin/env python3
"""
Convert 《三国霸业》 .stg scenario files to structured JSON/CSV/Markdown.

Usage:
    python stg_to_structured.py --tables stage_ini_conversion_tables.xlsx --out out stage01.stg stage02.stg stage03.stg stage04.stg

Design notes:
- Uses only Python standard library. No pandas/openpyxl dependency.
- Text inside .stg is decoded as Big5.
- Main binary layout inferred from the four supplied scenario files:
  Header(0x4C) -> ForceRecord(0xF0) -> SiteRecord(0x318) -> EntityRecord(0x11C) -> UnknownTail -> Trailer(0xA0)
"""
from __future__ import annotations

import argparse
import csv
import json
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile

HEADER_SIZE = 0x4C
FORCE_SIZE = 0xF0
SITE_SIZE = 0x318
ENTITY_SIZE = 0x11C
TRAILER_SIZE = 0xA0

# EntityRecord: fields confirmed by matching with sheet `general`.
ENTITY_GENERAL_FIELD_MAP: list[tuple[int, str]] = [
    (0x94, "人物編號"),
    (0x98, "頭像編號"),
    (0x9C, "所屬君主"),  # usually 0/1; runtime ownership is better represented by +0x78 and parent Force.
    (0xA0, "所在地"),    # usually 0 in supplied STG files; parent Site is the reliable location.
    (0xA4, "統御力"),
    (0xA8, "兵種號"),
    (0xAC, "等級"),
    (0xB0, "帶兵數"),
    (0xB4, "武力"),
    (0xB8, "智力"),
    (0xBC, "忠誠值"),
    (0xC0, "經驗值"),
    (0xC4, "火花技1"),
    (0xC8, "火炎技2"),
    (0xCC, "火龍技3"),
    (0xD0, "落石技1"),
    (0xD4, "崩石技2"),
    (0xD8, "隕石技3"),
    (0xDC, "落雷技1"),
    (0xE0, "狂雷技2"),
    (0xE4, "爆雷技3"),
    (0xE8, "一氣斬1"),
    (0xEC, "月氣斬2"),
    (0xF0, "爆發斬3"),
    (0xF4, "槍1"),
    (0xF8, "槍2"),
    (0xFC, "槍3"),
    (0x100, "穿心箭技1"),
    (0x104, "亂矢箭2"),
    (0x108, "萬箭技3"),
    (0x10C, "說服技"),
    (0x110, "鼓舞技"),
    (0x114, "大喝技"),
    (0x118, "迷惑技"),
]

SKILL_COLUMNS = [name for off, name in ENTITY_GENERAL_FIELD_MAP if 0xC4 <= off <= 0x118]

# SiteRecord: fields confirmed/partially confirmed by matching with sheet `castle`.
SITE_FIELD_HINTS = {
    "city_index": 0x5C,          # equals castle.都市索引 for 38 in-file cities
    "city_scale": 0x64,          # equals castle.城規模
    "population_or_current_pop": 0x68,
    "resource_6c": 0x6C,
    "resource_70": 0x70,
    "x": 0x90,                   # equals castle.座標X
    "y": 0x94,                   # equals castle.座標Y
    "site_state_98": 0x98,
}

# Common generic unit display names used in STG. +0xA8 maps to `soldier.人物編號`.
GENERIC_SOLDIER_DISPLAY = {
    "步兵", "槍兵", "騎兵", "弓箭兵", "小賊", "搶匪", "賊頭目"
}

XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
XLSX_REL_ATTR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def i32(data: bytes, off: int) -> int:
    return struct.unpack_from("<i", data, off)[0]


def hex_at(off: int) -> str:
    return f"0x{off:X}"


def big5_cstr(data: bytes, off: int, max_len: int = 32) -> str:
    raw = data[off: off + max_len].split(b"\0", 1)[0]
    return raw.decode("big5", errors="replace")


def int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except Exception:
        return None


def excel_cell_to_row_col(ref: str) -> tuple[int, int]:
    col_part = "".join(ch for ch in ref if ch.isalpha())
    row_part = "".join(ch for ch in ref if ch.isdigit())
    col = 0
    for ch in col_part.upper():
        col = col * 26 + ord(ch) - 64
    return int(row_part), col


def read_xlsx_tables(path: Path) -> dict[str, list[dict[str, str]]]:
    """Read a simple .xlsx workbook using only zipfile + ElementTree.

    Supports the uploaded workbook style: inline strings/numeric cells, first row as header.
    """
    tables: dict[str, list[dict[str, str]]] = {}
    with ZipFile(path) as zf:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"].lstrip("/") for rel in rels}

        sheets_el = workbook.find("a:sheets", XLSX_NS)
        if sheets_el is None:
            return tables

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.findall("a:si", XLSX_NS):
                shared_strings.append("".join(t.text or "" for t in si.findall(".//a:t", XLSX_NS)))

        for sheet_el in sheets_el:
            sheet_name = sheet_el.attrib["name"]
            target = relmap[sheet_el.attrib[XLSX_REL_ATTR]]
            root = ET.fromstring(zf.read(target))
            cells: dict[tuple[int, int], str] = {}
            max_row = 0
            max_col = 0
            for cell in root.findall(".//a:c", XLSX_NS):
                ref = cell.attrib.get("r")
                if not ref:
                    continue
                row, col = excel_cell_to_row_col(ref)
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//a:t", XLSX_NS))
                else:
                    v = cell.find("a:v", XLSX_NS)
                    value = v.text if v is not None and v.text is not None else ""
                    if cell_type == "s" and value != "" and shared_strings:
                        value = shared_strings[int(value)]
                cells[(row, col)] = value
                max_row = max(max_row, row)
                max_col = max(max_col, col)

            headers = [cells.get((1, c), "") for c in range(1, max_col + 1)]
            rows: list[dict[str, str]] = []
            for r in range(2, max_row + 1):
                row_dict = {h: cells.get((r, c), "") for c, h in enumerate(headers, start=1) if h}
                if any(v != "" for v in row_dict.values()):
                    rows.append(row_dict)
            tables[sheet_name] = rows
    return tables


@dataclass
class RecordMarker:
    start: int
    pre_value: int
    name: str


def find_named_records(data: bytes, signature: int) -> list[RecordMarker]:
    """Find records by the observed marker pair: +0x44 == signature and +0x48 is Big5 name."""
    out: list[RecordMarker] = []
    for marker_off in range(0, len(data) - 16, 4):
        if u32(data, marker_off + 4) != signature:
            continue
        name = big5_cstr(data, marker_off + 8, 20)
        if name and any("\u4e00" <= ch <= "\u9fff" for ch in name):
            out.append(RecordMarker(start=marker_off - 0x40, pre_value=u32(data, marker_off), name=name))
    return sorted(out, key=lambda r: r.start)


def classify_entity(record: bytes, name: str, general_by_id: dict[int, dict[str, str]], soldier_by_person_id: dict[int, dict[str, str]]) -> tuple[str, dict[str, Any]]:
    person_or_template_id = i32(record, 0x94)
    portrait_or_sub_id = i32(record, 0x98)
    unit_person_id = i32(record, 0xA8)

    # Generic troops also appear in the `general` sheet as entity templates
    # (e.g. 步兵 id=219), but semantically they are soldier/unit entities.
    soldier_row = soldier_by_person_id.get(unit_person_id)
    if name in GENERIC_SOLDIER_DISPLAY:
        return "soldier", {"soldier_table": soldier_row}

    general_row = general_by_id.get(person_or_template_id)
    if general_row and general_row.get("title") == name:
        return "general", {"general_table": general_row}

    if soldier_row:
        return "soldier", {"soldier_table": soldier_row}

    return "unknown", {}


def parse_entity(data: bytes, start: int, slot: int, parent_force_index: int, parent_force_name: str, parent_site_name: str,
                 general_by_id: dict[int, dict[str, str]], soldier_by_person_id: dict[int, dict[str, str]], magic_rows: list[dict[str, str]]) -> dict[str, Any]:
    rec = data[start: start + ENTITY_SIZE]
    name = big5_cstr(rec, 0x80, 16)
    kind, refs = classify_entity(rec, name, general_by_id, soldier_by_person_id)

    fields_by_offset = {hex_at(off): i32(rec, off) for off, _ in ENTITY_GENERAL_FIELD_MAP}
    named_fields = {field: i32(rec, off) for off, field in ENTITY_GENERAL_FIELD_MAP}
    skills: list[dict[str, Any]] = []
    if kind == "general":
        for idx, col in enumerate(SKILL_COLUMNS):
            off = 0xC4 + idx * 4
            val = i32(rec, off)
            if val:
                skill_meta = magic_rows[idx] if idx < len(magic_rows) else {}
                skills.append({
                    "field": col,
                    "offset": hex_at(off),
                    "value": val,
                    "magic_table_title": skill_meta.get("title", ""),
                    "magic_row_id": int_or_none(skill_meta.get("row_id", "")),
                })

    out = {
        "slot": slot,
        "offset": hex_at(start),
        "signature_7c": u32(rec, 0x7C),
        "name": name,
        "kind": kind,
        "parent_force_index": parent_force_index,
        "parent_force_name": parent_force_name,
        "parent_site_name": parent_site_name,
        "owner_index_78": u32(rec, 0x78),
        "person_or_template_id_94": i32(rec, 0x94),
        "portrait_or_sub_id_98": i32(rec, 0x98),
        "unit_person_id_a8": i32(rec, 0xA8),
        "troops_b0": i32(rec, 0xB0),
        "force_b4": i32(rec, 0xB4),
        "intellect_b8": i32(rec, 0xB8),
        "loyalty_bc": i32(rec, 0xBC),
        "general_like_fields": named_fields,
        "general_like_fields_by_offset": fields_by_offset,
        "skills_nonzero": skills,
    }
    if refs.get("general_table"):
        g = refs["general_table"]
        out["matched_general"] = {
            "row_id": int_or_none(g.get("row_id")),
            "title": g.get("title"),
            "人物編號": int_or_none(g.get("人物編號")),
            "頭像編號": int_or_none(g.get("頭像編號")),
            "統御力": int_or_none(g.get("統御力")),
            "兵種號": int_or_none(g.get("兵種號")),
            "武力": int_or_none(g.get("武力")),
            "智力": int_or_none(g.get("智力")),
        }
    if refs.get("soldier_table"):
        so = refs["soldier_table"]
        out["matched_soldier"] = {
            "row_id": int_or_none(so.get("row_id")),
            "title": so.get("title"),
            "人物編號": int_or_none(so.get("人物編號")),
            "攻擊力": int_or_none(so.get("攻擊力")),
            "防禦力": int_or_none(so.get("防禦力")),
            "行動速度": int_or_none(so.get("行動速度")),
            "範圍開始": int_or_none(so.get("範圍開始")),
            "範圍結束": int_or_none(so.get("範圍結束")),
            "兵種屬性": int_or_none(so.get("兵種屬性")),
        }
    return out


def parse_site(data: bytes, start: int, index_in_force: int, end: int, parent_force_index: int, parent_force_name: str,
               castle_by_name: dict[str, dict[str, str]], general_by_id: dict[int, dict[str, str]],
               soldier_by_person_id: dict[int, dict[str, str]], magic_rows: list[dict[str, str]], last_site_in_file: bool = False) -> tuple[dict[str, Any], int]:
    name = big5_cstr(data, start + 0x48, 16)
    city_static = castle_by_name.get(name)
    site_kind = "city" if city_static else ("bandit_camp" if name == "山寨" else "unknown")

    site_values = {key: i32(data, start + off) for key, off in SITE_FIELD_HINTS.items()}
    entity_start = start + SITE_SIZE
    entity_end = end
    entities: list[dict[str, Any]] = []
    unknown_tail_start = end

    max_possible = max(0, (entity_end - entity_start) // ENTITY_SIZE)
    for slot in range(1, max_possible + 1):
        e_start = entity_start + (slot - 1) * ENTITY_SIZE
        if e_start + ENTITY_SIZE > len(data):
            break
        signature = u32(data, e_start + 0x7C)
        if signature != 0xE0:
            # The supplied files have non-entity scenario-tail data after the last bandit camp.
            # Stop parsing entities at the first broken EntityRecord signature.
            unknown_tail_start = e_start
            break
        entities.append(parse_entity(data, e_start, slot, parent_force_index, parent_force_name, name,
                                     general_by_id, soldier_by_person_id, magic_rows))
    else:
        unknown_tail_start = entity_start + len(entities) * ENTITY_SIZE

    site = {
        "index_in_force": index_in_force,
        "offset": hex_at(start),
        "name": name,
        "kind": site_kind,
        "signature_44": u32(data, start + 0x44),
        "site_count_if_first_40": u32(data, start + 0x40),
        "city_index_5c": i32(data, start + 0x5C),
        "city_scale_64": i32(data, start + 0x64),
        "population_or_current_pop_68": i32(data, start + 0x68),
        "resource_6c": i32(data, start + 0x6C),
        "resource_70": i32(data, start + 0x70),
        "x_90": i32(data, start + 0x90),
        "y_94": i32(data, start + 0x94),
        "site_state_98": i32(data, start + 0x98),
        "site_values_by_hint": site_values,
        "entity_count": len(entities),
        "entities": entities,
    }
    if city_static:
        site["matched_castle"] = {k: int_or_none(v) if k not in ("title",) else v for k, v in city_static.items()}
    return site, unknown_tail_start


def parse_stg(path: Path, tables: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    data = path.read_bytes()
    castle_by_name = {row.get("title", ""): row for row in tables.get("castle", []) if row.get("title")}
    general_by_id = {int_or_none(row.get("人物編號")): row for row in tables.get("general", []) if int_or_none(row.get("人物編號")) is not None}
    soldier_by_person_id = {int_or_none(row.get("人物編號")): row for row in tables.get("soldier", []) if int_or_none(row.get("人物編號")) is not None}
    magic_rows = tables.get("magic", [])

    force_markers = find_named_records(data, 0x60)
    site_markers = find_named_records(data, 0x5C)
    if not force_markers:
        raise ValueError(f"No ForceRecord marker found in {path}")

    force_count = u32(data, force_markers[0].start + 0x40)
    selected_forces = force_markers[:force_count]
    forces: list[dict[str, Any]] = []
    unknown_tail_ranges: list[dict[str, Any]] = []

    for force_idx, marker in enumerate(selected_forces, start=1):
        force_start = marker.start
        force_end = selected_forces[force_idx].start if force_idx < len(selected_forces) else len(data) - TRAILER_SIZE
        force_site_markers = [m for m in site_markers if force_start + FORCE_SIZE <= m.start < force_end]
        site_count = u32(data, force_site_markers[0].start + 0x40) if force_site_markers else 0
        selected_sites = force_site_markers[:site_count]

        force = {
            "index": force_idx,
            "offset": hex_at(force_start),
            "name": marker.name,
            "signature_44": u32(data, force_start + 0x44),
            "force_count_if_first_40": u32(data, force_start + 0x40),
            "site_count": site_count,
            "sites": [],
        }

        for site_idx, site_marker in enumerate(selected_sites, start=1):
            next_boundary = selected_sites[site_idx].start if site_idx < len(selected_sites) else force_end
            site, parsed_until = parse_site(
                data=data,
                start=site_marker.start,
                index_in_force=site_idx,
                end=next_boundary,
                parent_force_index=force_idx,
                parent_force_name=marker.name,
                castle_by_name=castle_by_name,
                general_by_id=general_by_id,
                soldier_by_person_id=soldier_by_person_id,
                magic_rows=magic_rows,
                last_site_in_file=(force_idx == len(selected_forces) and site_idx == len(selected_sites)),
            )
            force["sites"].append(site)
            if parsed_until < next_boundary:
                unknown_tail_ranges.append({
                    "after_force": marker.name,
                    "after_site": site["name"],
                    "offset_start": hex_at(parsed_until),
                    "offset_end": hex_at(next_boundary),
                    "size": next_boundary - parsed_until,
                    "note": "non-EntityRecord data after first invalid +0x7C signature; keep as unknown_tail",
                })
        forces.append(force)

    city_names_in_stg = []
    for force in forces:
        for site in force["sites"]:
            if site["kind"] == "city":
                city_names_in_stg.append(site["name"])
    city_names_in_table = [r.get("title", "") for r in tables.get("castle", []) if r.get("title")]

    return {
        "file": path.name,
        "file_size": len(data),
        "header": {
            "version_00": u32(data, 0x00),
            "header_size_04": u32(data, 0x04),
            "title_08": big5_cstr(data, 0x08, 8),
            "value_10": u32(data, 0x10),
            "value_24": u32(data, 0x24),
            "max_entity_or_general_28": u32(data, 0x28),
            "scenario_id_38": u32(data, 0x38),
        },
        "layout": {
            "header_size": HEADER_SIZE,
            "force_record_size": FORCE_SIZE,
            "site_record_size": SITE_SIZE,
            "entity_record_size": ENTITY_SIZE,
            "trailer_size": TRAILER_SIZE,
        },
        "summary": {
            "force_count": len(forces),
            "site_count": sum(len(f["sites"]) for f in forces),
            "city_count": sum(1 for f in forces for s in f["sites"] if s["kind"] == "city"),
            "bandit_camp_count": sum(1 for f in forces for s in f["sites"] if s["kind"] == "bandit_camp"),
            "entity_count": sum(s["entity_count"] for f in forces for s in f["sites"]),
            "general_entity_count": sum(1 for f in forces for s in f["sites"] for e in s["entities"] if e["kind"] == "general"),
            "soldier_entity_count": sum(1 for f in forces for s in f["sites"] for e in s["entities"] if e["kind"] == "soldier"),
            "unknown_entity_count": sum(1 for f in forces for s in f["sites"] for e in s["entities"] if e["kind"] == "unknown"),
            "cities_in_castle_table_but_absent_from_stg": sorted(set(city_names_in_table) - set(city_names_in_stg)),
        },
        "forces": forces,
        "unknown_tail_ranges": unknown_tail_ranges,
        "trailer": {
            "offset": hex_at(len(data) - TRAILER_SIZE),
            "size": TRAILER_SIZE,
        },
    }


def write_csvs(scenarios: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "forces.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "scenario", "force_index", "force_name", "offset", "site_count", "entity_count"])
        writer.writeheader()
        for sc in scenarios:
            for force in sc["forces"]:
                writer.writerow({
                    "file": sc["file"],
                    "scenario": sc["header"]["title_08"],
                    "force_index": force["index"],
                    "force_name": force["name"],
                    "offset": force["offset"],
                    "site_count": force["site_count"],
                    "entity_count": sum(site["entity_count"] for site in force["sites"]),
                })

    site_fields = [
        "file", "scenario", "force_index", "force_name", "site_index", "site_name", "kind", "offset",
        "city_index_5c", "city_scale_64", "population_or_current_pop_68", "resource_6c", "resource_70",
        "x_90", "y_94", "site_state_98", "entity_count",
        "castle_都市索引", "castle_城規模", "castle_人口", "castle_金", "castle_糧", "castle_座標X", "castle_座標Y",
    ]
    with (out_dir / "sites.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=site_fields)
        writer.writeheader()
        for sc in scenarios:
            for force in sc["forces"]:
                for site in force["sites"]:
                    c = site.get("matched_castle", {})
                    writer.writerow({
                        "file": sc["file"],
                        "scenario": sc["header"]["title_08"],
                        "force_index": force["index"],
                        "force_name": force["name"],
                        "site_index": site["index_in_force"],
                        "site_name": site["name"],
                        "kind": site["kind"],
                        "offset": site["offset"],
                        "city_index_5c": site["city_index_5c"],
                        "city_scale_64": site["city_scale_64"],
                        "population_or_current_pop_68": site["population_or_current_pop_68"],
                        "resource_6c": site["resource_6c"],
                        "resource_70": site["resource_70"],
                        "x_90": site["x_90"],
                        "y_94": site["y_94"],
                        "site_state_98": site["site_state_98"],
                        "entity_count": site["entity_count"],
                        "castle_都市索引": c.get("都市索引"),
                        "castle_城規模": c.get("城規模"),
                        "castle_人口": c.get("人口"),
                        "castle_金": c.get("金"),
                        "castle_糧": c.get("糧"),
                        "castle_座標X": c.get("座標X"),
                        "castle_座標Y": c.get("座標Y"),
                    })

    entity_fields = [
        "file", "scenario", "force_index", "force_name", "site_name", "site_kind", "slot", "offset", "name", "kind",
        "owner_index_78", "person_or_template_id_94", "portrait_or_sub_id_98", "unit_person_id_a8",
        "troops_b0", "force_b4", "intellect_b8", "loyalty_bc",
        "matched_general_id", "matched_general_name", "matched_soldier_id", "matched_soldier_name", "skills_nonzero",
    ]
    with (out_dir / "entities.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=entity_fields)
        writer.writeheader()
        for sc in scenarios:
            for force in sc["forces"]:
                for site in force["sites"]:
                    for ent in site["entities"]:
                        mg = ent.get("matched_general", {})
                        ms = ent.get("matched_soldier", {})
                        writer.writerow({
                            "file": sc["file"],
                            "scenario": sc["header"]["title_08"],
                            "force_index": force["index"],
                            "force_name": force["name"],
                            "site_name": site["name"],
                            "site_kind": site["kind"],
                            "slot": ent["slot"],
                            "offset": ent["offset"],
                            "name": ent["name"],
                            "kind": ent["kind"],
                            "owner_index_78": ent["owner_index_78"],
                            "person_or_template_id_94": ent["person_or_template_id_94"],
                            "portrait_or_sub_id_98": ent["portrait_or_sub_id_98"],
                            "unit_person_id_a8": ent["unit_person_id_a8"],
                            "troops_b0": ent["troops_b0"],
                            "force_b4": ent["force_b4"],
                            "intellect_b8": ent["intellect_b8"],
                            "loyalty_bc": ent["loyalty_bc"],
                            "matched_general_id": mg.get("人物編號"),
                            "matched_general_name": mg.get("title"),
                            "matched_soldier_id": ms.get("人物編號"),
                            "matched_soldier_name": ms.get("title"),
                            "skills_nonzero": ";".join(s["field"] for s in ent["skills_nonzero"]),
                        })


def markdown_summary(scenarios: list[dict[str, Any]], tables: dict[str, list[dict[str, str]]]) -> str:
    lines: list[str] = []
    lines.append("# 《三国霸业》STG 结构化解析结果\n")
    lines.append("## 联合分析结论\n")
    lines.append("- `.stg` 主体结构：`Header(0x4C) -> ForceRecord(0xF0)*N -> SiteRecord(0x318)*M -> EntityRecord(0x11C)*K -> UnknownTail -> Trailer(0xA0)`。")
    lines.append("- `general` 表与 `EntityRecord +0x94..+0x118` 高度重合；武将 ID、头像、统御、兵种、等级、带兵、武力、智力、忠诚、经验和技能列可直接命名。")
    lines.append("- `castle` 表与 `SiteRecord +0x5C/+0x64/+0x90/+0x94` 确认重合；城市索引、城规模、坐标可直接命名。`+0x68/+0x6C/+0x70` 与人口/资源相关，但数值不总是等于表格静态值，脚本保留为候选字段。")
    lines.append("- `soldier` 表可通过 `EntityRecord +0xA8` 关联普通兵/贼兵模板；例如 步兵=19、槍兵=20、騎兵=21、弓箭兵=22、小賊=25、搶匪=26、賊頭目=27。")
    lines.append("- `magic` 表不以文本形式出现在 `.stg` 中，但 `general` 技能列与 `EntityRecord +0xC4..+0x118` 对齐，可用于给技能位补充名称。\n")

    lines.append("## 表格规模\n")
    lines.append("| sheet | 记录数 |")
    lines.append("|---|---:|")
    for name in ["general", "castle", "magic", "soldier"]:
        lines.append(f"| {name} | {len(tables.get(name, []))} |")
    lines.append("")

    lines.append("## EntityRecord 字段映射\n")
    lines.append("| 偏移 | 字段 | 置信度 |")
    lines.append("|---:|---|---|")
    for off, field in ENTITY_GENERAL_FIELD_MAP:
        conf = "确认" if off not in (0x9C, 0xA0) else "高重合但语义需验证"
        lines.append(f"| `{hex_at(off)}` | `{field}` | {conf} |")
    lines.append("")

    lines.append("## SiteRecord 字段映射\n")
    lines.append("| 偏移 | 字段 | 置信度 |")
    lines.append("|---:|---|---|")
    site_desc = {
        "city_index": "城市索引 / 都市索引",
        "city_scale": "城规模",
        "population_or_current_pop": "人口/当前人口候选",
        "resource_6c": "资源候选 1",
        "resource_70": "资源候选 2",
        "x": "座标X",
        "y": "座标Y",
        "site_state_98": "状态/归属/关联ID候选",
    }
    for key, off in SITE_FIELD_HINTS.items():
        conf = "确认" if key in ("city_index", "city_scale", "x", "y") else "候选"
        lines.append(f"| `{hex_at(off)}` | {site_desc[key]} | {conf} |")
    lines.append("")

    lines.append("## 剧本汇总\n")
    lines.append("| 文件 | 剧本名 | 势力 | 据点 | 城市 | 山寨 | 实体 | 武将实体 | 士兵实体 | unknown tail |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for sc in scenarios:
        sm = sc["summary"]
        lines.append(
            f"| {sc['file']} | {sc['header']['title_08']} | {sm['force_count']} | {sm['site_count']} | {sm['city_count']} | "
            f"{sm['bandit_camp_count']} | {sm['entity_count']} | {sm['general_entity_count']} | {sm['soldier_entity_count']} | {len(sc['unknown_tail_ranges'])} |"
        )
    lines.append("")

    for sc in scenarios:
        lines.append(f"## {sc['file']}：{sc['header']['title_08']}\n")
        lines.append("| 势力 | 据点数 | 实体数 | 据点列表 |")
        lines.append("|---|---:|---:|---|")
        for force in sc["forces"]:
            sites_desc = "；".join(f"{s['name']}({s['entity_count']})" for s in force["sites"])
            ent_count = sum(s["entity_count"] for s in force["sites"])
            lines.append(f"| {force['name']} | {force['site_count']} | {ent_count} | {sites_desc} |")
        lines.append("")
        absent = sc["summary"].get("cities_in_castle_table_but_absent_from_stg", [])
        if absent:
            lines.append(f"castle 表有但该 STG 未出现的城市：{', '.join(absent)}。\n")
        if sc["unknown_tail_ranges"]:
            lines.append("UnknownTail：")
            for u in sc["unknown_tail_ranges"]:
                lines.append(f"- `{u['offset_start']}..{u['offset_end']}`，{u['size']} 字节，位于 {u['after_force']} / {u['after_site']} 后。")
            lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert 三国霸业 .stg scenario files to JSON/CSV/Markdown.")
    parser.add_argument("stg", nargs="+", type=Path, help="Input .stg files")
    parser.add_argument("--tables", type=Path, help="stage_ini_conversion_tables.xlsx")
    parser.add_argument("--out", type=Path, default=Path("stg_structured_output"), help="Output directory")
    args = parser.parse_args(argv)

    tables = read_xlsx_tables(args.tables) if args.tables else {}
    # Ensure table keys exist, so the script can still run without conversion workbook.
    for key in ["general", "castle", "magic", "soldier"]:
        tables.setdefault(key, [])

    args.out.mkdir(parents=True, exist_ok=True)
    scenarios = []
    for stg_path in args.stg:
        scenario = parse_stg(stg_path, tables)
        scenarios.append(scenario)
        out_json = args.out / f"{stg_path.stem}.json"
        out_json.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")

    write_csvs(scenarios, args.out)
    (args.out / "stg_structured_report.md").write_text(markdown_summary(scenarios, tables), encoding="utf-8")
    print(f"Wrote {len(scenarios)} scenario JSON files + CSV/Markdown to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
