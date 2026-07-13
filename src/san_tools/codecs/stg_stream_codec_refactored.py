#!/usr/bin/env python3
"""
EXE-derived reusable STG stream codec for 《三国霸业》.

本文件用于把 `.stg` 剧本文件解析为结构化 dict/JSON，并从 dict/JSON
无损构建回 `.stg`。这版的核心设计目标是：

1. 核心 API 不依赖 argparse.Namespace，方便被编辑器、测试、Codex 或其它模块 import。
2. 所有未知二进制字段都保存在 raw_hex 中，build 时默认原样保留。
3. 已命名字段只作为 raw_hex 上的安全 patch，不会重排未知字段。
4. EXE 流式结构里的块大小由文件自身的 u32 size 决定，不硬编码固定版本。

This parser follows the object stream shape observed from Emperor.exe:

  u32 present/version
  Block root_part1: u32 size + payload[0x4C or 0x48]
  Block root_part2: u32 size + payload[0x34]
  u32 force_count
  Force * force_count
    Block force_part1: u32 size + payload[0x60]
    Block force_part2: u32 size + payload[0x84 or 0x7C]
    u32 site_list_pre_count_or_flag
    Site * force_part2.site_count
      Block site_part1: u32 size + payload[0x5C or 0x58]
      Block site_part2: u32 size + payload[0x2B0]
      u32 primary_entity_count
      Entity * primary_entity_count
        Block entity_part1: u32 size + payload[0x34 or 0x30]
        Block entity_part2: u32 size + payload[0xE0]
      Optional Entity blocks controlled by site_part2 flags
  after_forces_tail raw bytes

可复用入口示例：

    tables = load_txt_tables("game")
    doc = parse_stage_file("game/stage/stage01.stg", tables=tables)
    doc["forces"][0]["sites"][0]["entities"][0]["part2"]["fields"]["general_帶兵數"] = 80
    new_bytes = build_stage_bytes(doc)

CLI 只在 main() 中解析参数，然后调用普通函数；核心逻辑不接收 args。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from zipfile import ZipFile

ENCODING = "big5"

ROOT1_SIZE = 0x4C
ROOT2_SIZE = 0x34
FORCE_PART1_SIZE = 0x60
FORCE_PART2_SIZE = 0x84
SITE_PART1_SIZE = 0x5C
SITE_PART2_SIZE = 0x2B0
ENTITY_PART1_SIZE = 0x34
ENTITY_PART2_SIZE = 0xE0
ENTITY_TOTAL_SIZE = 4 + ENTITY_PART1_SIZE + 4 + ENTITY_PART2_SIZE

OPTIONAL_ENTITY_FLAG_OFFSETS = [0x27C, 0x280, 0x284, 0x288, 0x28C]

# -----------------------------------------------------------------------------
# 重要说明：为什么这里使用“Block”模型
# -----------------------------------------------------------------------------
# EXE 读写 STG 时不是直接 fread 固定的 Force/Site/Entity 聚合结构，
# 而是反复读取：
#
#   1) u32 size
#   2) size 字节 payload
#
# 也就是说，`0x60/0x84/0x5C/0x2B0/0x34/0xE0` 都是 payload size，
# 不是包含 size 字段自身的总长度。
#
# 早期脚本把多个 Block 合并成 ForceRecord/SiteRecord/EntityRecord，虽然
# 可以 roundtrip，但字段偏移会偏离 EXE 的真实对象结构。当前脚本保留 EXE
# 流式对象边界，后续继续反汇编时更容易把 `[this+offset]` 对应到字段。
#
# 安全性原则：
# - parse：每个 Block 的 payload 原始字节保存为 raw_hex。
# - build：先从 raw_hex 还原 payload，再把 fields 里已命名字段 patch 回去。
# - 未命名字段、未解析尾部 after_forces_tail 均原样保留。
# - 文本字段只允许同长度或更短的 Big5 文本，避免覆盖文本后的隐藏标记。


XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
XLSX_REL_ATTR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


@dataclass(frozen=True)
class FieldSpec:
    offset: int
    name: str
    type: str = "i32"  # u32, i32, text
    size: int = 4
    confidence: str = "unknown"
    note: str = ""


ROOT1_FIELDS = [
    FieldSpec(0x00, "scenario_title", "text", 8, "confirmed", "Big5 剧本名"),
    FieldSpec(0x08, "value_08", "u32", confidence="candidate", note="stage01 为 0x4000"),
    FieldSpec(0x1C, "scenario_year_or_value_1c", "u32", confidence="high", note="四大剧本为 189/194/200/219"),
    FieldSpec(0x20, "general_capacity_20", "u32", confidence="candidate", note="四大剧本为 500"),
    FieldSpec(0x24, "scenario_id_24", "u32", confidence="confirmed", note="四大剧本为 1/2/3/4"),
]

ROOT2_FIELDS = [
    FieldSpec(0x14, "force_count_mirror_candidate", "u32", confidence="candidate", note="stage01 为 10，可能与势力数相关"),
]

FORCE_PART1_FIELDS = [
    FieldSpec(0x00, "force_name", "text", 20, "confirmed", "Big5 势力名；payload 开头"),
]

FORCE_PART2_FIELDS = [
    FieldSpec(0x00, "site_count", "u32", confidence="structural", note="EXE 按此值循环读取 Site"),
]

# castle.txt columns map exactly onto site_part1: name[0x14] + numeric fields.
CASTLE_NUMERIC_COLUMNS = [
    "都市索引", "房子屬性", "城規模", "人口", "金", "糧", "待命士兵", "開發值", "商業值", "治安值",
    "開發上限", "商業上限", "治安上限", "座標X", "座標Y", "太守", "武將",
]
SITE_PART1_FIELDS = [FieldSpec(0x00, "site_name", "text", 20, "confirmed", "Big5 据点/城市名")]
for idx, col in enumerate(CASTLE_NUMERIC_COLUMNS):
    SITE_PART1_FIELDS.append(FieldSpec(0x14 + idx * 4, f"castle_{col}", "i32", confidence="confirmed", note=f"castle.txt:{col}"))

SITE_PART2_FIELDS = [
    FieldSpec(0x04, "site_part2_x_or_runtime_x_candidate", "i32", confidence="candidate", note="例如平原为 187；不是 castle.txt 座標X"),
    FieldSpec(0x08, "site_part2_y_or_runtime_y_candidate", "i32", confidence="candidate", note="例如平原为 120；不是 castle.txt 座標Y"),
    FieldSpec(0x27C, "optional_entity_flag_27c", "u32", confidence="high", note="非 0 时后面会额外读取 Entity"),
    FieldSpec(0x280, "optional_entity_flag_280", "u32", confidence="high", note="非 0 时后面会额外读取 Entity"),
    FieldSpec(0x284, "optional_entity_flag_284", "u32", confidence="high", note="非 0 时后面会额外读取 Entity"),
    FieldSpec(0x288, "optional_entity_flag_288", "u32", confidence="high", note="非 0 时后面会额外读取 Entity"),
    FieldSpec(0x28C, "optional_entity_flag_28c", "u32", confidence="high", note="非 0 时后面会额外读取 Entity"),
    FieldSpec(0x2AC, "extra_entity_count_candidate_2ac", "u32", confidence="candidate", note="额外 Entity 列表 count 候选；需继续 EXE 验证"),
]

ENTITY_PART1_FIELDS = [
    FieldSpec(0x00, "owner_force_index_runtime", "u32", confidence="confirmed", note="运行时所属势力序号候选，常与父 Force 一致"),
    FieldSpec(0x04, "runtime_04", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x08, "runtime_08", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x0C, "runtime_0c", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x10, "runtime_10", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x14, "runtime_14", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x18, "runtime_18", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x1C, "runtime_1c", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x20, "runtime_20", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x24, "runtime_24", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x28, "runtime_28", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x2C, "runtime_2c", "i32", confidence="unknown", note="运行时/位置/状态字段"),
    FieldSpec(0x30, "runtime_30", "i32", confidence="unknown", note="运行时/位置/状态字段"),
]

# general.txt columns map onto entity_part2: name[0x14] + numeric fields.
GENERAL_NUMERIC_COLUMNS = [
    "人物編號", "頭像編號", "所屬君主", "所在地", "統御力", "兵種號", "等級", "帶兵數", "武力", "智力", "忠誠值", "經驗值",
    "火花技1", "火炎技2", "火龍技3", "落石技1", "崩石技2", "隕石技3", "落雷技1", "狂雷技2", "爆雷技3",
    "一氣斬1", "月氣斬2", "爆發斬3", "槍1", "槍2", "槍3", "穿心箭技1", "亂矢箭2", "萬箭技3",
    "說服技", "鼓舞技", "大喝技", "迷惑技", "必殺技", "行動狀態", "被關=1", "讀取=1", "屬性", "參照自己",
    "武將警戒", "武將追捕", "武將撤退", "行動方針", "伏兵 =?", "叛變國id", "最大帶兵數", "最大武力", "最大智力",
]
ENTITY_PART2_FIELDS = [FieldSpec(0x00, "entity_name", "text", 20, "confirmed", "Big5 武将名/兵种模板名")]
for idx, col in enumerate(GENERAL_NUMERIC_COLUMNS):
    safe = col.replace("=", "eq").replace("?", "unknown").replace(" ", "_").replace("/", "_")
    ENTITY_PART2_FIELDS.append(FieldSpec(0x14 + idx * 4, f"general_{safe}", "i32", confidence="confirmed", note=f"general.txt:{col}"))
# Two trailing dwords in 0xE0 are still unknown/reserved.
ENTITY_PART2_FIELDS.extend([
    FieldSpec(0xD8, "entity_part2_reserved_d8", "i32", confidence="unknown", note="general.txt 不覆盖，常为 0"),
    FieldSpec(0xDC, "entity_part2_reserved_dc", "i32", confidence="unknown", note="general.txt 不覆盖，常为 0"),
])

FIELD_SPECS: dict[str, list[FieldSpec]] = {
    "root_part1": ROOT1_FIELDS,
    "root_part2": ROOT2_FIELDS,
    "force_part1": FORCE_PART1_FIELDS,
    "force_part2": FORCE_PART2_FIELDS,
    "site_part1": SITE_PART1_FIELDS,
    "site_part2": SITE_PART2_FIELDS,
    "entity_part1": ENTITY_PART1_FIELDS,
    "entity_part2": ENTITY_PART2_FIELDS,
}

GENERIC_SOLDIER_DISPLAY = {"步兵", "槍兵", "騎兵", "弓箭兵", "小賊", "搶匪", "賊頭目"}


class StgStreamError(ValueError):
    pass


def u32(data: bytes | bytearray, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def i32(data: bytes | bytearray, off: int) -> int:
    return struct.unpack_from("<i", data, off)[0]


def put_u32(buf: bytearray, off: int, val: int) -> None:
    if not (0 <= int(val) <= 0xFFFFFFFF):
        raise ValueError(f"u32 out of range: {val}")
    struct.pack_into("<I", buf, off, int(val))


def put_i32(buf: bytearray, off: int, val: int) -> None:
    if not (-0x80000000 <= int(val) <= 0x7FFFFFFF):
        raise ValueError(f"i32 out of range: {val}")
    struct.pack_into("<i", buf, off, int(val))


def read_text(data: bytes | bytearray, off: int, size: int) -> str:
    return bytes(data[off:off + size]).split(b"\0", 1)[0].decode(ENCODING, errors="replace")


def put_text_if_changed(buf: bytearray, off: int, size: int, value: str) -> None:
    current = read_text(buf, off, size)
    if current == value:
        return
    area = bytes(buf[off:off + size])
    nul = area.find(b"\0")
    visible_len = len(area) if nul < 0 else nul
    raw = value.encode(ENCODING, errors="strict")
    if len(raw) > visible_len:
        raise ValueError(f"text +0x{off:X} can only be edited in-place up to {visible_len} Big5 bytes; got {len(raw)}: {value!r}")
    buf[off:off + len(raw)] = raw
    if len(raw) < visible_len:
        buf[off + len(raw):off + visible_len] = b"\0" * (visible_len - len(raw))


def hx(n: int) -> str:
    return f"0x{n:X}"


def parse_hx(v: str | int) -> int:
    if isinstance(v, int):
        return v
    return int(v, 16) if str(v).lower().startswith("0x") else int(v)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def int_or_none(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v)))
    except Exception:
        return None


def spec_to_dict(spec: FieldSpec) -> dict[str, Any]:
    return {"offset": hx(spec.offset), "name": spec.name, "type": spec.type, "size": spec.size, "confidence": spec.confidence, "note": spec.note}


def read_txt_table(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    text = p.read_bytes().decode(ENCODING, errors="replace")
    lines = [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    headers = lines[0].split("\t")
    # Normalize first column to title, while preserving original header too.
    title_header = headers[0]
    rows = []
    for idx, line in enumerate(lines[1:], start=1):
        parts = line.split("\t")
        if len(parts) < len(headers):
            parts += [""] * (len(headers) - len(parts))
        row = {h: parts[i] if i < len(parts) else "" for i, h in enumerate(headers) if h != ""}
        filled = sum(1 for v in row.values() if v != "")
        title = row.get(title_header, parts[0] if parts else "")
        # Some original TXT files contain trailing partial/broken rows. They are not table records.
        if not title or filled < max(2, int(len([h for h in headers if h]) * 0.75)):
            continue
        row["row_id"] = str(len(rows) + 1)
        row["title"] = title
        rows.append(row)
    return rows


def load_txt_tables(game_dir: str | Path | None) -> dict[str, list[dict[str, str]]]:
    if game_dir is None:
        return {}
    base = Path(game_dir)
    files = {"general": "general.txt", "castle": "castle.txt", "soldier": "soldier.txt", "magic": "magic.txt"}
    out: dict[str, list[dict[str, str]]] = {}
    for key, fname in files.items():
        p = base / fname
        if p.exists():
            out[key] = read_txt_table(p)
    return out


def excel_cell_to_row_col(ref: str) -> tuple[int, int]:
    col_part = "".join(ch for ch in ref if ch.isalpha())
    row_part = "".join(ch for ch in ref if ch.isdigit())
    col = 0
    for ch in col_part.upper():
        col = col * 26 + ord(ch) - 64
    return int(row_part), col


def read_xlsx_tables(path: str | Path | None) -> dict[str, list[dict[str, str]]]:
    if path is None:
        return {}
    with ZipFile(path) as zf:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"].lstrip("/") for rel in rels}
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared_strings = ["".join(t.text or "" for t in si.findall(".//a:t", XLSX_NS)) for si in sst.findall("a:si", XLSX_NS)]
        tables: dict[str, list[dict[str, str]]] = {}
        for sheet_el in workbook.find("a:sheets", XLSX_NS) or []:
            name = sheet_el.attrib["name"]
            target = relmap[sheet_el.attrib[XLSX_REL_ATTR]]
            root = ET.fromstring(zf.read(target))
            cells: dict[tuple[int, int], str] = {}
            max_row = max_col = 0
            for cell in root.findall(".//a:c", XLSX_NS):
                ref = cell.attrib.get("r")
                if not ref:
                    continue
                row, col = excel_cell_to_row_col(ref)
                typ = cell.attrib.get("t")
                if typ == "inlineStr":
                    val = "".join(t.text or "" for t in cell.findall(".//a:t", XLSX_NS))
                else:
                    v = cell.find("a:v", XLSX_NS)
                    val = v.text if v is not None and v.text is not None else ""
                    if typ == "s" and val and shared_strings:
                        val = shared_strings[int(val)]
                cells[(row, col)] = val
                max_row = max(max_row, row)
                max_col = max(max_col, col)
            headers = [cells.get((1, c), "") for c in range(1, max_col + 1)]
            rows = []
            for r in range(2, max_row + 1):
                row = {h: cells.get((r, c), "") for c, h in enumerate(headers, 1) if h}
                if any(v != "" for v in row.values()):
                    row.setdefault("title", row.get(headers[1] if len(headers) > 1 else headers[0], ""))
                    rows.append(row)
            tables[name] = rows
        return tables


def build_table_indexes(tables: Mapping[str, list[dict[str, str]]] | None) -> dict[str, Any]:
    tables = tables or {}
    return {
        "general_by_id": {int_or_none(r.get("人物編號")): r for r in tables.get("general", []) if int_or_none(r.get("人物編號")) is not None},
        "castle_by_index": {int_or_none(r.get("都市索引")): r for r in tables.get("castle", []) if int_or_none(r.get("都市索引")) is not None},
        "castle_by_name": {r.get("title", ""): r for r in tables.get("castle", []) if r.get("title")},
        "soldier_by_id": {int_or_none(r.get("人物編號")): r for r in tables.get("soldier", []) if int_or_none(r.get("人物編號")) is not None},
        "magic_rows": tables.get("magic", []),
    }


def extract_fields(payload: bytes, specs: Sequence[FieldSpec]) -> tuple[dict[str, Any], dict[str, Any]]:
    fields: dict[str, Any] = {}
    meta: dict[str, Any] = {}
    for spec in specs:
        if spec.offset + spec.size > len(payload):
            continue
        if spec.type == "text":
            value: Any = read_text(payload, spec.offset, spec.size)
        elif spec.type == "u32":
            value = u32(payload, spec.offset)
        elif spec.type == "i32":
            value = i32(payload, spec.offset)
        else:
            raise ValueError(f"unknown type: {spec.type}")
        fields[spec.name] = value
        meta[spec.name] = spec_to_dict(spec)
    return fields, meta


def make_block(kind: str, label: str, size_offset: int, payload_offset: int, payload: bytes, include_words: bool = False) -> dict[str, Any]:
    fields, meta = extract_fields(payload, FIELD_SPECS.get(kind, []))
    out: dict[str, Any] = {
        "kind": kind,
        "label": label,
        "size_offset": hx(size_offset),
        "payload_offset": hx(payload_offset),
        "size": len(payload),
        "end": hx(payload_offset + len(payload)),
        "raw_hex": payload.hex(),
        "fields": fields,
        "field_meta": meta,
    }
    if include_words:
        out["u32_words"] = [{"offset": hx(off), "u32": u32(payload, off), "i32": i32(payload, off)} for off in range(0, len(payload) - 3, 4)]
    return out


def read_block(data: bytes, off: int, kind: str, label: str, expected_size: int | None = None, strict: bool = True, include_words: bool = False) -> dict[str, Any]:
    """Read one EXE-style block: `<u32 payload_size><payload>`.

    `kind` decides which FieldSpec list will be applied to payload.
    `label` is only for diagnostics/JSON readability.
    `expected_size` is optional because uploaded STG files show version differences
    such as 0x48/0x4C root_part1 and 0x30/0x34 entity_part1.
    """
    if off + 4 > len(data):
        raise StgStreamError(f"truncated block header at {hx(off)} for {label}")
    size = u32(data, off)
    if strict and expected_size is not None and size != expected_size:
        raise StgStreamError(f"{label} at {hx(off)} size expected {expected_size}, got {size}")
    payload_off = off + 4
    end = payload_off + size
    if end > len(data):
        raise StgStreamError(f"truncated block payload {label} at {hx(off)} size {size}")
    return make_block(kind, label, off, payload_off, data[payload_off:end], include_words=include_words)


def block_end(block: Mapping[str, Any]) -> int:
    return parse_hx(block["end"])


def apply_block_fields(block: Mapping[str, Any], kind: str, patch_fields: bool = True) -> bytes:
    """Build `<u32 size><payload>` from a parsed block.

    The payload is restored from `raw_hex`. If `patch_fields=True`, named fields
    are written back into that payload. Unknown bytes are never regenerated or
    guessed, so this is safe for lossless roundtrip.
    """
    payload = bytearray.fromhex(str(block.get("raw_hex", "")))
    if len(payload) != int(block.get("size", len(payload))):
        raise StgStreamError(f"block {block.get('label')} raw size mismatch")
    if patch_fields:
        fields = block.get("fields", {})
        if isinstance(fields, Mapping):
            for spec in FIELD_SPECS.get(kind, []):
                if spec.name not in fields:
                    continue
                val = fields[spec.name]
                if spec.type == "text":
                    put_text_if_changed(payload, spec.offset, spec.size, str(val))
                elif spec.type == "u32":
                    put_u32(payload, spec.offset, int(val))
                elif spec.type == "i32":
                    put_i32(payload, spec.offset, int(val))
    return struct.pack("<I", len(payload)) + bytes(payload)


def enrich_site(site: dict[str, Any], indexes: Mapping[str, Any]) -> None:
    fields = site["part1"].get("fields", {})
    city_index = fields.get("castle_都市索引")
    name = fields.get("site_name", "")
    castle = indexes.get("castle_by_index", {}).get(city_index) or indexes.get("castle_by_name", {}).get(name)
    site["name"] = name
    site["classification"] = "city" if castle else ("bandit_camp" if name == "山寨" else "unknown_site")
    if castle:
        site["matched_castle"] = castle


def enrich_entity(entity: dict[str, Any], indexes: Mapping[str, Any]) -> None:
    p2fields = entity["part2"].get("fields", {})
    name = p2fields.get("entity_name", "")
    pid = p2fields.get("general_人物編號")
    soldier_type = p2fields.get("general_兵種號")
    general = indexes.get("general_by_id", {}).get(pid)
    soldier = indexes.get("soldier_by_id", {}).get(soldier_type)
    entity["name"] = name
    if name in GENERIC_SOLDIER_DISPLAY:
        cls = "soldier"
    elif general and general.get("title") == name:
        cls = "general"
    elif soldier:
        cls = "soldier"
    else:
        cls = "unknown_entity"
    entity["classification"] = cls
    if general:
        entity["matched_general"] = {k: general.get(k, "") for k in ["row_id", "title", "人物編號", "頭像編號", "統御力", "兵種號", "帶兵數", "武力", "智力", "忠誠值", "最大帶兵數", "最大武力", "最大智力"]}
    if soldier:
        entity["matched_soldier"] = {k: soldier.get(k, "") for k in ["row_id", "title", "人物編號", "攻擊力", "防禦力", "行動速度", "兵種屬性"]}


def parse_entity(data: bytes, off: int, indexes: Mapping[str, Any], *, include_words: bool = False, strict: bool = True, list_name: str = "primary", index: int | None = None) -> dict[str, Any]:
    """Parse one Entity object.

    Entity consists of two blocks:
    - entity_part1: runtime/state block, still partially unknown.
    - entity_part2: static/general-like block aligned with general.txt.
    """
    p1 = read_block(data, off, "entity_part1", "entity_part1", None, strict=strict, include_words=include_words)
    p2 = read_block(data, block_end(p1), "entity_part2", "entity_part2", None, strict=strict, include_words=include_words)
    ent: dict[str, Any] = {"offset": hx(off), "end": p2["end"], "list": list_name, "part1": p1, "part2": p2}
    if index is not None:
        ent["index"] = index
    enrich_entity(ent, indexes)
    return ent


def parse_site(data: bytes, off: int, indexes: Mapping[str, Any], *, include_words: bool = False, strict: bool = True, index: int | None = None) -> dict[str, Any]:
    """Parse one Site object and its child entity lists.

    Layout:
      site_part1 block: castle.txt-aligned static/site data.
      site_part2 block: runtime/AI/optional-entity control data.
      u32 primary_entity_count
      primary Entity * count
      optional Entity blocks controlled by selected site_part2 flags.
    """
    p1 = read_block(data, off, "site_part1", "site_part1", None, strict=strict, include_words=include_words)
    p2 = read_block(data, block_end(p1), "site_part2", "site_part2", None, strict=strict, include_words=include_words)
    cur = block_end(p2)
    if cur + 4 > len(data):
        raise StgStreamError(f"truncated entity count at {hx(cur)}")
    entity_count = u32(data, cur)
    cur += 4
    site: dict[str, Any] = {"offset": hx(off), "part1": p1, "part2": p2, "primary_entity_count": entity_count, "entities": [], "optional_entities": [], "extra_entities": []}
    if index is not None:
        site["index"] = index
    enrich_site(site, indexes)
    for i in range(entity_count):
        ent = parse_entity(data, cur, indexes, include_words=include_words, strict=strict, list_name="primary", index=i + 1)
        site["entities"].append(ent)
        cur = parse_hx(ent["end"])
    payload2 = bytes.fromhex(p2["raw_hex"])
    flags = []
    for rel in OPTIONAL_ENTITY_FLAG_OFFSETS:
        if rel + 4 <= len(payload2):
            flag = u32(payload2, rel)
            flags.append({"offset": hx(rel), "value": flag})
            if flag != 0:
                ent = parse_entity(data, cur, indexes, include_words=include_words, strict=strict, list_name=f"optional_{rel:03X}")
                site["optional_entities"].append(ent)
                cur = parse_hx(ent["end"])
    site["optional_flags"] = flags
    extra_count = u32(payload2, 0x2AC) if len(payload2) >= 0x2B0 else 0
    site["extra_entity_count_candidate_2ac"] = extra_count
    if extra_count and cur + 4 <= len(data) and u32(data, cur) == ENTITY_PART1_SIZE:
        # Conservative: parse only if the pattern looks like an Entity block.
        tmp = cur
        parsed = []
        ok = True
        for i in range(extra_count):
            try:
                ent = parse_entity(data, tmp, indexes, include_words=include_words, strict=strict, list_name="extra_2AC_candidate", index=i + 1)
                parsed.append(ent)
                tmp = parse_hx(ent["end"])
            except Exception:
                ok = False
                break
        if ok:
            site["extra_entities"] = parsed
            cur = tmp
    site["end"] = hx(cur)
    return site


def parse_force(data: bytes, off: int, indexes: Mapping[str, Any], *, include_words: bool = False, strict: bool = True, index: int | None = None) -> dict[str, Any]:
    """Parse one Force object and all Site objects under it.

    The site count is stored in force_part2 payload +0x00. A second u32
    immediately after force_part2 is preserved as `site_list_pre_count_or_flag`;
    by sample comparison it often mirrors the site count, but we keep both.
    """
    p1 = read_block(data, off, "force_part1", "force_part1", None, strict=strict, include_words=include_words)
    p2 = read_block(data, block_end(p1), "force_part2", "force_part2", None, strict=strict, include_words=include_words)
    payload2 = bytes.fromhex(p2["raw_hex"])
    site_count = u32(payload2, 0) if len(payload2) >= 4 else 0
    cur = block_end(p2)
    if cur + 4 > len(data):
        raise StgStreamError(f"truncated site list pre count at {hx(cur)}")
    pre_count = u32(data, cur)
    cur += 4
    force: dict[str, Any] = {"offset": hx(off), "part1": p1, "part2": p2, "site_count": site_count, "site_list_pre_count_or_flag": pre_count, "sites": []}
    if index is not None:
        force["index"] = index
    force["name"] = p1["fields"].get("force_name", "")
    for i in range(site_count):
        site = parse_site(data, cur, indexes, include_words=include_words, strict=strict, index=i + 1)
        force["sites"].append(site)
        cur = parse_hx(site["end"])
    force["end"] = hx(cur)
    return force


def detect_entity_like_blocks(data: bytes, start: int, end: int, indexes: Mapping[str, Any], *, include_words: bool = False) -> list[dict[str, Any]]:
    blocks = []
    off = start
    while off + ENTITY_TOTAL_SIZE <= end:
        if u32(data, off) == ENTITY_PART1_SIZE and u32(data, off + 4 + ENTITY_PART1_SIZE) == ENTITY_PART2_SIZE:
            try:
                ent = parse_entity(data, off, indexes, include_words=include_words, strict=True, list_name="tail_detected")
                blocks.append({
                    "offset": ent["offset"],
                    "end": ent["end"],
                    "name": ent.get("name", ""),
                    "classification": ent.get("classification", ""),
                    "person_id": ent["part2"].get("fields", {}).get("general_人物編號"),
                    "troop_count": ent["part2"].get("fields", {}).get("general_帶兵數"),
                })
                off = parse_hx(ent["end"])
                continue
            except Exception:
                pass
        off += 4
    return blocks


def parse_stage_bytes(data: bytes, *, source_name: str = "<bytes>", tables: Mapping[str, list[dict[str, str]]] | None = None, include_words: bool = False, strict: bool = True, detect_tail_entities: bool = True) -> dict[str, Any]:
    """Parse a STG byte string into a lossless JSON-like document.

    This is the main reusable parse API. It does not know about argparse or file
    system output. Pass preloaded `tables` to enrich names/IDs without rereading
    TXT/XLSX for every STG file.
    """
    indexes = build_table_indexes(tables)
    cur = 0
    if len(data) < 4:
        raise StgStreamError("empty/truncated STG")
    present_or_version = u32(data, cur)
    cur += 4
    root1 = read_block(data, cur, "root_part1", "root_part1_variable", None, strict=strict, include_words=include_words)
    cur = block_end(root1)
    root2 = read_block(data, cur, "root_part2", "root_part2", None, strict=strict, include_words=include_words)
    cur = block_end(root2)
    if cur + 4 > len(data):
        raise StgStreamError("missing force_count")
    force_count = u32(data, cur)
    cur += 4
    forces = []
    for i in range(force_count):
        force = parse_force(data, cur, indexes, include_words=include_words, strict=strict, index=i + 1)
        forces.append(force)
        cur = parse_hx(force["end"])
    tail = data[cur:]
    tail_scan_end = len(data)
    # Keep old 0xA0 trailer candidate only as a detection boundary when tail is large enough.
    trailer_candidate_offset = max(cur, len(data) - 0xA0)
    tail_entity_like = detect_entity_like_blocks(data, cur, trailer_candidate_offset, indexes, include_words=False) if detect_tail_entities else []
    doc = {
        "codec": "stg_stream_codec",
        "codec_version": 1,
        "source_file": source_name,
        "file_size": len(data),
        "source_sha256": sha256_hex(data),
        "encoding": ENCODING,
        "layout": {
            "root1_size": ROOT1_SIZE,
            "root2_size": ROOT2_SIZE,
            "force_part1_size": FORCE_PART1_SIZE,
            "force_part2_size": FORCE_PART2_SIZE,
            "site_part1_size": SITE_PART1_SIZE,
            "site_part2_size": SITE_PART2_SIZE,
            "entity_part1_size": ENTITY_PART1_SIZE,
            "entity_part2_size": ENTITY_PART2_SIZE,
            "parse_rule": "EXE-derived block stream: u32 size + payload",
        },
        "field_maps": {k: [spec_to_dict(s) for s in v] for k, v in FIELD_SPECS.items()},
        "present_or_version": present_or_version,
        "root_part1": root1,
        "root_part2": root2,
        "force_count": force_count,
        "forces": forces,
        "after_forces_tail": {
            "offset": hx(cur),
            "size": len(tail),
            "raw_hex": tail.hex(),
            "trailer_candidate_offset_0xA0": hx(trailer_candidate_offset),
            "trailer_candidate_size_0xA0": len(data) - trailer_candidate_offset,
            "tail_entity_like_count_to_trailer_candidate": len(tail_entity_like),
            "tail_entity_like_blocks_to_trailer_candidate": tail_entity_like,
            "note": "EXE 主力/据点读取完成后的剩余流；当前原样保留。大剧本中可检测到 entity-like block，但准确列表逻辑还需继续反 EXE。",
        },
    }
    doc["summary"] = summarize_stage(doc)
    return doc


def parse_stage_file(path: str | Path, *, tables: Mapping[str, list[dict[str, str]]] | None = None, tables_dir: str | Path | None = None, include_words: bool = False, strict: bool = True, detect_tail_entities: bool = True) -> dict[str, Any]:
    if tables is None and tables_dir is not None:
        tables = load_txt_tables(tables_dir)
    p = Path(path)
    return parse_stage_bytes(p.read_bytes(), source_name=p.name, tables=tables, include_words=include_words, strict=strict, detect_tail_entities=detect_tail_entities)


def summarize_stage(doc: Mapping[str, Any]) -> dict[str, Any]:
    forces = doc.get("forces", [])
    sites = [s for f in forces for s in f.get("sites", [])]
    primary_entities = [e for s in sites for e in s.get("entities", [])]
    optional_entities = [e for s in sites for e in s.get("optional_entities", []) + s.get("extra_entities", [])]
    all_entities = primary_entities + optional_entities
    return {
        "title": doc.get("root_part1", {}).get("fields", {}).get("scenario_title", ""),
        "scenario_id": doc.get("root_part1", {}).get("fields", {}).get("scenario_id_24"),
        "file_size": doc.get("file_size"),
        "force_count": len(forces),
        "site_count": len(sites),
        "primary_entity_count": len(primary_entities),
        "optional_entity_count": len(optional_entities),
        "general_entity_count": sum(1 for e in all_entities if e.get("classification") == "general"),
        "soldier_entity_count": sum(1 for e in all_entities if e.get("classification") == "soldier"),
        "unknown_entity_count": sum(1 for e in all_entities if e.get("classification") == "unknown_entity"),
        "after_forces_tail_size": doc.get("after_forces_tail", {}).get("size", 0),
        "tail_entity_like_count": doc.get("after_forces_tail", {}).get("tail_entity_like_count_to_trailer_candidate", 0),
    }


def build_entity_bytes(ent: Mapping[str, Any], *, patch_fields: bool = True) -> bytes:
    return apply_block_fields(ent["part1"], "entity_part1", patch_fields) + apply_block_fields(ent["part2"], "entity_part2", patch_fields)


def build_site_bytes(site: Mapping[str, Any], *, recompute_counts: bool = True, patch_fields: bool = True) -> bytes:
    out = bytearray()
    out += apply_block_fields(site["part1"], "site_part1", patch_fields)
    out += apply_block_fields(site["part2"], "site_part2", patch_fields)
    entities = list(site.get("entities", []))
    count = len(entities) if recompute_counts else int(site.get("primary_entity_count", len(entities)))
    out += struct.pack("<I", count)
    for ent in entities:
        out += build_entity_bytes(ent, patch_fields=patch_fields)
    for ent in site.get("optional_entities", []):
        out += build_entity_bytes(ent, patch_fields=patch_fields)
    for ent in site.get("extra_entities", []):
        out += build_entity_bytes(ent, patch_fields=patch_fields)
    return bytes(out)


def build_force_bytes(force: Mapping[str, Any], *, recompute_counts: bool = True, patch_fields: bool = True) -> bytes:
    out = bytearray()
    out += apply_block_fields(force["part1"], "force_part1", patch_fields)
    p2 = bytearray(apply_block_fields(force["part2"], "force_part2", patch_fields))
    sites = list(force.get("sites", []))
    if recompute_counts:
        # p2 includes 4-byte size prefix, payload starts at +4.
        put_u32(p2, 4 + 0x00, len(sites))
    out += p2
    pre_count = len(sites) if recompute_counts else int(force.get("site_list_pre_count_or_flag", len(sites)))
    out += struct.pack("<I", pre_count)
    for site in sites:
        out += build_site_bytes(site, recompute_counts=recompute_counts, patch_fields=patch_fields)
    return bytes(out)


def apply_block_fields(block: Mapping[str, Any], kind: str, patch_fields: bool = True) -> bytes:
    payload = bytearray.fromhex(str(block.get("raw_hex", "")))
    if patch_fields:
        fields = block.get("fields", {})
        if isinstance(fields, Mapping):
            for spec in FIELD_SPECS.get(kind, []):
                if spec.name not in fields:
                    continue
                value = fields[spec.name]
                if spec.type == "text":
                    put_text_if_changed(payload, spec.offset, spec.size, str(value))
                elif spec.type == "u32":
                    put_u32(payload, spec.offset, int(value))
                elif spec.type == "i32":
                    put_i32(payload, spec.offset, int(value))
    return struct.pack("<I", len(payload)) + bytes(payload)


def build_stage_bytes(doc: Mapping[str, Any], *, recompute_counts: bool = True, patch_fields: bool = True) -> bytes:
    """Build STG bytes from a parsed document.

    `recompute_counts=True` is recommended for editor use: force_count,
    site_count, and primary_entity_count are recalculated from list lengths.
    `patch_fields=True` means named field edits are applied to raw_hex payloads.
    Unknown regions, including after_forces_tail, are appended unchanged.
    """
    out = bytearray()
    out += struct.pack("<I", int(doc.get("present_or_version", 1)))
    out += apply_block_fields(doc["root_part1"], "root_part1", patch_fields)
    out += apply_block_fields(doc["root_part2"], "root_part2", patch_fields)
    forces = list(doc.get("forces", []))
    out += struct.pack("<I", len(forces) if recompute_counts else int(doc.get("force_count", len(forces))))
    for force in forces:
        out += build_force_bytes(force, recompute_counts=recompute_counts, patch_fields=patch_fields)
    out += bytes.fromhex(str(doc.get("after_forces_tail", {}).get("raw_hex", "")))
    return bytes(out)


def roundtrip_stage_file(path: str | Path, *, tables: Mapping[str, list[dict[str, str]]] | None = None, tables_dir: str | Path | None = None, out_json: str | Path | None = None, out_rebuilt: str | Path | None = None) -> dict[str, Any]:
    p = Path(path)
    original = p.read_bytes()
    doc = parse_stage_file(p, tables=tables, tables_dir=tables_dir)
    rebuilt = build_stage_bytes(doc)
    if out_json:
        write_json(doc, out_json)
    if out_rebuilt:
        Path(out_rebuilt).parent.mkdir(parents=True, exist_ok=True)
        Path(out_rebuilt).write_bytes(rebuilt)
    return {"source": str(p), "size": len(original), "source_sha256": sha256_hex(original), "rebuilt_sha256": sha256_hex(rebuilt), "identical": original == rebuilt, "summary": doc["summary"]}


def write_json(doc: Mapping[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_json_to_stg_file(json_path: str | Path, out_path: str | Path, *, compare_path: str | Path | None = None, recompute_counts: bool = True, patch_fields: bool = True) -> dict[str, Any]:
    doc = load_json(json_path)
    data = build_stage_bytes(doc, recompute_counts=recompute_counts, patch_fields=patch_fields)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    result = {"out": str(out), "size": len(data), "sha256": sha256_hex(data), "identical_to_compare": None}
    if compare_path:
        orig = Path(compare_path).read_bytes()
        result["identical_to_compare"] = orig == data
        result["compare_sha256"] = sha256_hex(orig)
    return result


def write_stage_csvs(docs: Sequence[Mapping[str, Any]], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "stages_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["source_file", "title", "scenario_id", "file_size", "force_count", "site_count", "primary_entity_count", "optional_entity_count", "general_entity_count", "soldier_entity_count", "unknown_entity_count", "after_forces_tail_size", "tail_entity_like_count"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for doc in docs:
            row = {"source_file": doc["source_file"], **doc["summary"]}
            w.writerow(row)
    with (out / "forces.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["source_file", "force_index", "force_name", "offset", "site_count", "site_list_pre_count_or_flag", "end"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for doc in docs:
            for force in doc.get("forces", []):
                w.writerow({"source_file": doc["source_file"], "force_index": force.get("index"), "force_name": force.get("name"), "offset": force.get("offset"), "site_count": force.get("site_count"), "site_list_pre_count_or_flag": force.get("site_list_pre_count_or_flag"), "end": force.get("end")})
    with (out / "sites.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["source_file", "force_index", "force_name", "site_index", "site_name", "classification", "offset", "primary_entity_count", "optional_count", "city_index", "castle_scale", "population", "gold", "food", "standby_soldier", "dev", "commerce", "security", "x", "y", "site_part2_x_candidate", "site_part2_y_candidate"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for doc in docs:
            for force in doc.get("forces", []):
                for site in force.get("sites", []):
                    sf = site["part1"]["fields"]
                    p2f = site["part2"]["fields"]
                    w.writerow({
                        "source_file": doc["source_file"], "force_index": force.get("index"), "force_name": force.get("name"),
                        "site_index": site.get("index"), "site_name": site.get("name"), "classification": site.get("classification"), "offset": site.get("offset"),
                        "primary_entity_count": site.get("primary_entity_count"), "optional_count": len(site.get("optional_entities", [])) + len(site.get("extra_entities", [])),
                        "city_index": sf.get("castle_都市索引"), "castle_scale": sf.get("castle_城規模"), "population": sf.get("castle_人口"), "gold": sf.get("castle_金"), "food": sf.get("castle_糧"), "standby_soldier": sf.get("castle_待命士兵"), "dev": sf.get("castle_開發值"), "commerce": sf.get("castle_商業值"), "security": sf.get("castle_治安值"), "x": sf.get("castle_座標X"), "y": sf.get("castle_座標Y"), "site_part2_x_candidate": p2f.get("site_part2_x_or_runtime_x_candidate"), "site_part2_y_candidate": p2f.get("site_part2_y_or_runtime_y_candidate"),
                    })
    with (out / "entities.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["source_file", "force_index", "force_name", "site_index", "site_name", "list", "entity_index", "classification", "offset", "entity_name", "owner_force_index_runtime", "person_id", "portrait_id", "soldier_type_id", "level", "troop_count", "force", "intellect", "loyalty", "max_troop", "max_force", "max_intellect"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for doc in docs:
            for force in doc.get("forces", []):
                for site in force.get("sites", []):
                    for ent in site.get("entities", []) + site.get("optional_entities", []) + site.get("extra_entities", []):
                        p1f = ent["part1"]["fields"]
                        p2f = ent["part2"]["fields"]
                        w.writerow({
                            "source_file": doc["source_file"], "force_index": force.get("index"), "force_name": force.get("name"), "site_index": site.get("index"), "site_name": site.get("name"), "list": ent.get("list"), "entity_index": ent.get("index"), "classification": ent.get("classification"), "offset": ent.get("offset"), "entity_name": ent.get("name"),
                            "owner_force_index_runtime": p1f.get("owner_force_index_runtime"), "person_id": p2f.get("general_人物編號"), "portrait_id": p2f.get("general_頭像編號"), "soldier_type_id": p2f.get("general_兵種號"), "level": p2f.get("general_等級"), "troop_count": p2f.get("general_帶兵數"), "force": p2f.get("general_武力"), "intellect": p2f.get("general_智力"), "loyalty": p2f.get("general_忠誠值"), "max_troop": p2f.get("general_最大帶兵數"), "max_force": p2f.get("general_最大武力"), "max_intellect": p2f.get("general_最大智力"),
                        })
    with (out / "tail_entity_like.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["source_file", "offset", "end", "name", "classification", "person_id", "troop_count"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for doc in docs:
            for ent in doc.get("after_forces_tail", {}).get("tail_entity_like_blocks_to_trailer_candidate", []):
                w.writerow({"source_file": doc["source_file"], **ent})


def write_markdown_report(docs: Sequence[Mapping[str, Any]], path: str | Path, *, table_counts: Mapping[str, int] | None = None, roundtrip_results: Sequence[Mapping[str, Any]] | None = None) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# STG EXE 流式结构解析报告")
    lines.append("")
    lines.append("## 结构结论")
    lines.append("")
    lines.append("```text")
    lines.append("u32 present/version")
    lines.append("Block root_part1 = u32 size + payload[0x4C]")
    lines.append("Block root_part2 = u32 size + payload[0x34]")
    lines.append("u32 force_count")
    lines.append("Force * force_count")
    lines.append("  Block force_part1 = u32 size + payload[0x60]")
    lines.append("  Block force_part2 = u32 size + payload[0x84]")
    lines.append("  u32 site_list_pre_count_or_flag")
    lines.append("  Site * force_part2.site_count")
    lines.append("    Block site_part1 = u32 size + payload[0x5C]  # castle.txt 对齐")
    lines.append("    Block site_part2 = u32 size + payload[0x2B0] # 运行态/AI/可选实体控制")
    lines.append("    u32 primary_entity_count")
    lines.append("    Entity * primary_entity_count")
    lines.append("      Block entity_part1 = u32 size + payload[0x34] # 运行态/位置/状态")
    lines.append("      Block entity_part2 = u32 size + payload[0xE0] # general.txt 对齐")
    lines.append("after_forces_tail raw bytes")
    lines.append("```")
    lines.append("")
    if table_counts:
        lines.append("## 静态表")
        lines.append("")
        lines.append("| 表 | 行数 |")
        lines.append("|---|---:|")
        for k, v in table_counts.items():
            lines.append(f"| {k} | {v} |")
        lines.append("")
    if roundtrip_results:
        lines.append("## Roundtrip 验证")
        lines.append("")
        lines.append("| 文件 | 结果 | 大小 | SHA256 |")
        lines.append("|---|---|---:|---|")
        for r in roundtrip_results:
            lines.append(f"| {Path(str(r['source'])).name} | {'OK' if r['identical'] else 'FAIL'} | {r['size']} | `{r['source_sha256'][:16]}...` |")
        lines.append("")
    lines.append("## STG 汇总")
    lines.append("")
    lines.append("| 文件 | 标题 | 势力 | 据点 | 主实体 | 可选实体 | Tail Entity-like | Tail bytes |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for doc in docs:
        s = doc["summary"]
        lines.append(f"| {doc['source_file']} | {s.get('title','')} | {s['force_count']} | {s['site_count']} | {s['primary_entity_count']} | {s['optional_entity_count']} | {s['tail_entity_like_count']} | {s['after_forces_tail_size']} |")
    lines.append("")
    lines.append("## 字段映射重点")
    lines.append("")
    lines.append("### site_part1 与 castle.txt 对齐")
    lines.append("")
    lines.append("`site_part1 +0x00` 是城市/据点名，`+0x14` 起按 `castle.txt` 数值列顺序排列：都市索引、房子属性、城规模、人口、金、粮、待命士兵、开发/商业/治安、上限、坐标、太守、武将。")
    lines.append("")
    lines.append("### entity_part2 与 general.txt 对齐")
    lines.append("")
    lines.append("`entity_part2 +0x00` 是实体名，`+0x14` 起按 `general.txt` 数值列顺序排列：人物编号、头像编号、所属君主、所在地、统御、兵种、等级、带兵、武力、智力、忠诚、经验、技能位、必杀技、行动状态、属性、AI 方针、最大带兵/武力/智力等。")
    lines.append("")
    lines.append("### entity_part1 仍需继续命名")
    lines.append("")
    lines.append("`entity_part1` 是 0x34 字节的运行态块，已知 `+0x00` 多数对应当前所属势力序号，其余字段更像位置/状态/AI 运行字段，建议通过存档或单变量修改继续确认。")
    lines.append("")
    lines.append("### after_forces_tail 仍原样保留")
    lines.append("")
    lines.append("大剧本 `after_forces_tail` 中存在大量 entity-like block，但目前还没有完全反推出 EXE 的尾部列表逻辑；新版脚本会检测并导出这些候选块，同时 build 时原样保留。")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")



# =============================================================================
# Public workflow API
# =============================================================================
# The following functions are the preferred import targets for editors/tests.
# None of them accepts argparse.Namespace. CLI conversion happens only in main().


def resolve_tables(
    *,
    tables: Mapping[str, list[dict[str, str]]] | None = None,
    tables_dir: str | Path | None = None,
    xlsx_path: str | Path | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Return static conversion tables from an already-loaded mapping/TXT/XLSX.

    Priority:
    1. `tables` argument, for callers that cache tables themselves.
    2. `tables_dir`, a directory containing general.txt/castle.txt/soldier.txt/magic.txt.
    3. `xlsx_path`, the converted workbook.

    Keeping this separate avoids repeatedly reading the same static tables when
    parsing many STG files.
    """
    if tables is not None:
        return dict(tables)
    if tables_dir is not None:
        return load_txt_tables(tables_dir)
    if xlsx_path is not None:
        return read_xlsx_tables(xlsx_path)
    return {}


def parse_stage_files(
    paths: Sequence[str | Path],
    *,
    tables: Mapping[str, list[dict[str, str]]] | None = None,
    tables_dir: str | Path | None = None,
    xlsx_path: str | Path | None = None,
    include_words: bool = False,
    strict: bool = True,
    detect_tail_entities: bool = True,
) -> list[dict[str, Any]]:
    """Parse multiple STG files and return documents.

    This is the batch parse API. It is safe to call from a GUI/editor because it
    returns Python data only and performs no implicit writing.
    """
    table_map = resolve_tables(tables=tables, tables_dir=tables_dir, xlsx_path=xlsx_path)
    return [
        parse_stage_file(
            p,
            tables=table_map,
            include_words=include_words,
            strict=strict,
            detect_tail_entities=detect_tail_entities,
        )
        for p in paths
    ]


def export_stage_documents(
    docs: Sequence[Mapping[str, Any]],
    out_dir: str | Path,
    *,
    write_json_files: bool = True,
    write_csv_files: bool = True,
    write_report: bool = True,
    table_counts: Mapping[str, int] | None = None,
    roundtrip_results: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Path]:
    """Write parsed STG documents to JSON/CSV/Markdown outputs.

    Returns paths of generated output groups so callers can display or link them.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {"out_dir": out}

    if write_json_files:
        json_dir = out / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        for doc in docs:
            write_json(doc, json_dir / f"{Path(str(doc['source_file'])).stem}.stg_stream.json")
        result["json_dir"] = json_dir

    if write_csv_files:
        csv_dir = out / "csv"
        write_stage_csvs(docs, csv_dir)
        result["csv_dir"] = csv_dir

    if write_report:
        report_path = out / "stg_stream_report.md"
        write_markdown_report(
            docs,
            report_path,
            table_counts=table_counts,
            roundtrip_results=roundtrip_results,
        )
        result["report"] = report_path

    return result


def parse_stg_to_output(
    stg_paths: Sequence[str | Path],
    out_dir: str | Path,
    *,
    tables: Mapping[str, list[dict[str, str]]] | None = None,
    tables_dir: str | Path | None = None,
    xlsx_path: str | Path | None = None,
    include_words: bool = False,
    strict: bool = True,
    detect_tail_entities: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    """Parse STG files and write standard JSON/CSV/Markdown outputs.

    This replaces the old `cli_parse(args)` pattern. It can be used directly by
    application code; the CLI simply forwards parsed command-line values here.
    """
    table_map = resolve_tables(tables=tables, tables_dir=tables_dir, xlsx_path=xlsx_path)
    docs = parse_stage_files(
        stg_paths,
        tables=table_map,
        include_words=include_words,
        strict=strict,
        detect_tail_entities=detect_tail_entities,
    )
    outputs = export_stage_documents(
        docs,
        out_dir,
        table_counts={k: len(v) for k, v in table_map.items()},
    )
    return docs, outputs


def roundtrip_stage_files(
    stg_paths: Sequence[str | Path],
    *,
    tables: Mapping[str, list[dict[str, str]]] | None = None,
    tables_dir: str | Path | None = None,
    xlsx_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    include_words: bool = False,
    strict: bool = True,
    detect_tail_entities: bool = True,
) -> list[dict[str, Any]]:
    """Run STG -> document -> STG verification for multiple files.

    If `out_dir` is provided, the parsed JSON and rebuilt STG are also written.
    The return value contains byte-for-byte identity status for each source.
    """
    table_map = resolve_tables(tables=tables, tables_dir=tables_dir, xlsx_path=xlsx_path)
    out = Path(out_dir) if out_dir is not None else None
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for p in map(Path, stg_paths):
        result = roundtrip_stage_file(
            p,
            tables=table_map,
            out_json=(out / f"{p.stem}.json") if out else None,
            out_rebuilt=(out / f"{p.stem}.rebuilt.stg") if out else None,
        )
        results.append(result)
    return results


def build_stage_file_from_json(
    json_path: str | Path,
    out_path: str | Path,
    *,
    compare_path: str | Path | None = None,
    recompute_counts: bool = True,
    patch_fields: bool = True,
) -> dict[str, Any]:
    """Build one STG file from a JSON document produced by this codec."""
    return build_json_to_stg_file(
        json_path,
        out_path,
        compare_path=compare_path,
        recompute_counts=recompute_counts,
        patch_fields=patch_fields,
    )


# =============================================================================
# CLI thin wrappers
# =============================================================================
# These functions print user-facing status for the command line only. They still
# accept normal Python parameters, not argparse.Namespace, so they can be tested
# or called without constructing fake args objects.


def cli_parse(
    stg_paths: Sequence[str | Path],
    *,
    tables_dir: str | Path | None = None,
    xlsx_path: str | Path | None = None,
    out_dir: str | Path = "stg_stream_output",
    include_words: bool = False,
    strict: bool = True,
    detect_tail_entities: bool = True,
) -> int:
    docs, outputs = parse_stg_to_output(
        stg_paths,
        out_dir,
        tables_dir=tables_dir,
        xlsx_path=xlsx_path,
        include_words=include_words,
        strict=strict,
        detect_tail_entities=detect_tail_entities,
    )
    print(f"parsed {len(docs)} STG files -> {outputs['out_dir']}")
    return 0


def cli_roundtrip(
    stg_paths: Sequence[str | Path],
    *,
    tables_dir: str | Path | None = None,
    xlsx_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    include_words: bool = False,
    strict: bool = True,
    detect_tail_entities: bool = True,
) -> int:
    results = roundtrip_stage_files(
        stg_paths,
        tables_dir=tables_dir,
        xlsx_path=xlsx_path,
        out_dir=out_dir,
        include_words=include_words,
        strict=strict,
        detect_tail_entities=detect_tail_entities,
    )
    for r in results:
        print(f"{Path(str(r['source'])).name}: {'OK' if r['identical'] else 'FAIL'} size={r['size']} sha256={r['source_sha256']}")
    return 0 if all(r["identical"] for r in results) else 1


def cli_build(
    json_path: str | Path,
    *,
    out_path: str | Path,
    compare_path: str | Path | None = None,
    recompute_counts: bool = True,
    patch_fields: bool = True,
) -> int:
    result = build_stage_file_from_json(
        json_path,
        out_path,
        compare_path=compare_path,
        recompute_counts=recompute_counts,
        patch_fields=patch_fields,
    )
    print(f"built {result['out']} size={result['size']} sha256={result['sha256']}")
    if compare_path:
        print("compare:", "byte-for-byte identical" if result["identical_to_compare"] else "DIFFERENT")
    return 0 if result.get("identical_to_compare", True) is not False else 2


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the command-line parser.

    Keeping parser construction isolated makes `main(argv)` easy to test and
    ensures the rest of this module remains import-friendly.
    """
    ap = argparse.ArgumentParser(description="EXE-derived STG stream codec")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="parse STG files to JSON/CSV/Markdown")
    p.add_argument("stg", nargs="+")
    p.add_argument("--tables-dir", help="directory containing general.txt/castle.txt/soldier.txt/magic.txt")
    p.add_argument("--xlsx", help="optional stage_ini_conversion_tables.xlsx")
    p.add_argument("--out-dir", default="stg_stream_output")
    p.add_argument("--include-words", action="store_true")
    p.add_argument("--no-strict", action="store_true", help="skip strict marker/shape validation where applicable")
    p.add_argument("--no-tail-detect", action="store_true", help="do not scan after_forces_tail for entity-like blocks")

    p = sub.add_parser("roundtrip", help="verify STG -> JSON/doc -> STG byte equality")
    p.add_argument("stg", nargs="+")
    p.add_argument("--tables-dir")
    p.add_argument("--xlsx")
    p.add_argument("--out-dir")
    p.add_argument("--include-words", action="store_true")
    p.add_argument("--no-strict", action="store_true")
    p.add_argument("--no-tail-detect", action="store_true")

    p = sub.add_parser("build", help="build one STG from JSON")
    p.add_argument("json")
    p.add_argument("--out", required=True)
    p.add_argument("--compare")
    p.add_argument("--no-recompute-counts", action="store_true")
    p.add_argument("--no-patch-fields", action="store_true")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint. Converts argparse results into normal function calls."""
    args = build_arg_parser().parse_args(argv)
    if args.cmd == "parse":
        return cli_parse(
            args.stg,
            tables_dir=args.tables_dir,
            xlsx_path=args.xlsx,
            out_dir=args.out_dir,
            include_words=args.include_words,
            strict=not args.no_strict,
            detect_tail_entities=not args.no_tail_detect,
        )
    if args.cmd == "roundtrip":
        return cli_roundtrip(
            args.stg,
            tables_dir=args.tables_dir,
            xlsx_path=args.xlsx,
            out_dir=args.out_dir,
            include_words=args.include_words,
            strict=not args.no_strict,
            detect_tail_entities=not args.no_tail_detect,
        )
    if args.cmd == "build":
        return cli_build(
            args.json,
            out_path=args.out,
            compare_path=args.compare,
            recompute_counts=not args.no_recompute_counts,
            patch_fields=not args.no_patch_fields,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
