from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.export_stg_city_troop_analysis import CITY_FIELD_OFFSETS
from tools.stage_ini_excel_codec import read_workbook_tables

STG_STRIDE = 76
STG_WORDS_PER_RECORD = STG_STRIDE // 2
HEX_RE = re.compile(r"^[0-9a-fA-F]*$")


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def parse_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("0x"):
        return int(text, 16)
    if text.lstrip("-").isdigit():
        return int(text)
    return None


def normalize_hex(value: object, *, expected_bytes: int | None = None, field_name: str = "hex") -> str:
    text = str(value or "").strip().replace(" ", "")
    if len(text) % 2 != 0 or not HEX_RE.match(text):
        raise ValueError(f"{field_name} 不是有效十六进制字符串")
    if expected_bytes is not None and len(text) != expected_bytes * 2:
        raise ValueError(f"{field_name} 长度应为 {expected_bytes} 字节，实际为 {len(text) // 2} 字节")
    return text.lower()


def sheet_dict_rows(sheet: dict[str, object]) -> list[dict[str, object]]:
    headers = [str(value) for value in sheet["headers"]]
    rows: list[dict[str, object]] = []
    for row in sheet["rows"]:
        values = list(row)
        while len(values) < len(headers):
            values.append("")
        rows.append({header: values[index] for index, header in enumerate(headers)})
    return rows


def load_meta(sheets: dict[str, dict[str, object]]) -> dict[str, object]:
    if "meta" not in sheets:
        raise ValueError("工作簿缺少 meta sheet")
    meta: dict[str, object] = {}
    for row in sheet_dict_rows(sheets["meta"]):
        key = str(row.get("key", "")).strip()
        if key:
            meta[key] = row.get("value", "")
    for required in ("header_hex", "stride", "record_count", "tail_hex"):
        if required not in meta:
            raise ValueError(f"meta sheet 缺少 {required}")
    return meta


def load_record_buffers(sheets: dict[str, dict[str, object]], expected_count: int) -> dict[int, bytearray]:
    if "raw_records" not in sheets:
        raise ValueError("工作簿缺少 raw_records sheet")
    buffers: dict[int, bytearray] = {}
    for row in sheet_dict_rows(sheets["raw_records"]):
        record_index = parse_int(row.get("record_index"))
        if record_index is None:
            continue
        raw_hex = normalize_hex(row.get("raw_hex"), expected_bytes=STG_STRIDE, field_name=f"raw_records[{record_index}].raw_hex")
        buffers[record_index] = bytearray(bytes.fromhex(raw_hex))
    if len(buffers) != expected_count:
        raise ValueError(f"raw_records 数量应为 {expected_count}，实际为 {len(buffers)}")
    missing = [index for index in range(expected_count) if index not in buffers]
    if missing:
        raise ValueError(f"raw_records 缺少记录：{missing[:10]}")
    return buffers


def patch_u16(record_buffers: dict[int, bytearray], record_index: int, word_index: int, value: int) -> None:
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"u16 字段超出范围：{value}")
    if record_index not in record_buffers:
        raise ValueError(f"city_state 指向不存在的 record_index={record_index}")
    if not 0 <= word_index < STG_WORDS_PER_RECORD:
        raise ValueError(f"word_index 超出范围：{word_index}")
    byte_offset = word_index * 2
    record_buffers[record_index][byte_offset : byte_offset + 2] = int(value).to_bytes(2, "little", signed=False)


def apply_city_state_sheet(sheets: dict[str, dict[str, object]], record_buffers: dict[int, bytearray]) -> dict[str, object]:
    if "city_state" not in sheets:
        return {"patched_fields": 0, "patched_records": 0, "note": "工作簿没有 city_state sheet"}
    patched_fields = 0
    patched_records: set[int] = set()
    for row in sheet_dict_rows(sheets["city_state"]):
        source_record_index = parse_int(row.get("source_record_index"))
        city_id_stream_index = parse_int(row.get("city_id_stream_index"))
        if source_record_index is None or city_id_stream_index is None:
            continue
        for field_name, relative_offset in CITY_FIELD_OFFSETS.items():
            column = f"candidate_{field_name}"
            value = parse_int(row.get(column))
            if value is None:
                continue
            stream_index = city_id_stream_index + relative_offset
            absolute_record_index = source_record_index + stream_index // STG_WORDS_PER_RECORD
            word_index = stream_index % STG_WORDS_PER_RECORD
            patch_u16(record_buffers, absolute_record_index, word_index, value)
            patched_fields += 1
            patched_records.add(absolute_record_index)
    return {"patched_fields": patched_fields, "patched_records": len(patched_records)}


def rebuild_blob(meta: dict[str, object], record_buffers: dict[int, bytearray]) -> bytes:
    header_hex = normalize_hex(meta["header_hex"], expected_bytes=8, field_name="meta.header_hex")
    tail_hex = normalize_hex(meta.get("tail_hex", ""), field_name="meta.tail_hex")
    record_count = int(parse_int(meta["record_count"]) or 0)
    records = b"".join(bytes(record_buffers[index]) for index in range(record_count))
    return bytes.fromhex(header_hex) + records + bytes.fromhex(tail_hex)


def main() -> int:
    parser = argparse.ArgumentParser(description="从 .stg Excel 工作簿回写新的 .stg 二进制文件。")
    parser.add_argument("workbook", type=Path, help="由 export_stg_workbook.py 导出的 xlsx")
    parser.add_argument("root", nargs="?", default=".", type=Path, help="项目根目录")
    parser.add_argument("--out", type=Path, default=Path("derived/sidecar_analysis/stg_workbooks/stage_from_workbook.stg"), help="输出 .stg 路径")
    parser.add_argument("--compare-with", type=Path, default=None, help="可选：与原始 .stg 比较 sha256 和字节一致性")
    parser.add_argument("--no-city-state", action="store_true", help="只按 raw_records.raw_hex 重建，不应用 city_state sheet")
    args = parser.parse_args()

    root = args.root.resolve()
    workbook_path = args.workbook.resolve()
    out_path = args.out
    if not out_path.is_absolute():
        out_path = (root / out_path).resolve()
    payload = read_workbook_tables(workbook_path)
    sheets = payload["sheets"]
    meta = load_meta(sheets)
    stride = int(parse_int(meta["stride"]) or 0)
    if stride != STG_STRIDE:
        raise ValueError(f"当前导入器只支持 76 字节 .stg 记录，工作簿 stride={stride}")
    record_count = int(parse_int(meta["record_count"]) or 0)
    record_buffers = load_record_buffers(sheets, record_count)
    patch_report = {"patched_fields": 0, "patched_records": 0, "note": "已跳过 city_state"}
    if not args.no_city_state:
        patch_report = apply_city_state_sheet(sheets, record_buffers)

    rebuilt = rebuild_blob(meta, record_buffers)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(rebuilt)

    compare = None
    if args.compare_with:
        compare_path = args.compare_with
        if not compare_path.is_absolute():
            compare_path = (root / compare_path).resolve()
        original = compare_path.read_bytes()
        compare = {
            "compare_with": str(compare_path),
            "byte_identical": rebuilt == original,
            "rebuilt_sha256": sha256_bytes(rebuilt),
            "compare_sha256": sha256_bytes(original),
        }

    print(
        json.dumps(
            {
                "out": str(out_path),
                "size": len(rebuilt),
                "city_state": patch_report,
                "compare": compare,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
