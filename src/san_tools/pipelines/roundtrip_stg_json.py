from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Mapping, Sequence

from san_tools.codecs.stg_stream_codec_refactored import (
    build_stage_file_from_json,
    parse_stage_file,
    resolve_tables,
    write_json,
)


def is_reserved_field_name(field_name: str) -> bool:
    """判断字段名是否属于保留字段。"""

    return "reserved" in field_name.lower()


def strip_reserved_fields_from_block(block: Mapping[str, Any]) -> None:
    """从单个 block 的 fields/field_meta 中移除保留字段。"""

    fields = block.get("fields")
    if isinstance(fields, dict):
        for key in list(fields.keys()):
            if is_reserved_field_name(str(key)):
                del fields[key]
    field_meta = block.get("field_meta")
    if isinstance(field_meta, dict):
        for key in list(field_meta.keys()):
            if is_reserved_field_name(str(key)):
                del field_meta[key]


def strip_reserved_fields_inplace(doc: dict[str, Any]) -> dict[str, Any]:
    """原地移除 JSON 文档中的保留字段定义与字段值。"""

    field_maps = doc.get("field_maps")
    if isinstance(field_maps, dict):
        for kind, specs in list(field_maps.items()):
            if isinstance(specs, list):
                field_maps[kind] = [
                    spec for spec in specs
                    if not is_reserved_field_name(str(spec.get("name", "")))
                ]

    def visit_block(block: Any) -> None:
        if isinstance(block, Mapping):
            strip_reserved_fields_from_block(block)

    visit_block(doc.get("root_part1"))
    visit_block(doc.get("root_part2"))
    for force in doc.get("forces", []):
        if not isinstance(force, dict):
            continue
        visit_block(force.get("part1"))
        visit_block(force.get("part2"))
        for site in force.get("sites", []):
            if not isinstance(site, dict):
                continue
            visit_block(site.get("part1"))
            visit_block(site.get("part2"))
            for entity_list_name in ("entities", "optional_entities", "extra_entities"):
                for entity in site.get(entity_list_name, []):
                    if not isinstance(entity, dict):
                        continue
                    visit_block(entity.get("part1"))
                    visit_block(entity.get("part2"))
    return doc


def reserved_zero_ranges(kind: str, payload_size: int) -> list[tuple[int, int]]:
    """返回当前 block 中明确标记为 `reserved_zero` 的字节范围。"""

    ranges: list[tuple[int, int]] = []
    if kind == "root_part1":
        ranges.extend([(0x14, 0x1C), (0x28, 0x2C), (0x40, 0x44)])
        if payload_size >= 0x4C:
            ranges.append((0x48, 0x4C))
    elif kind == "root_part2":
        ranges.extend([(0x18, 0x1C), (0x20, 0x24), (0x2C, 0x30)])
    elif kind == "force_part1":
        ranges.extend([(0x30, 0x38), (0x44, 0x48)])
    elif kind == "force_part2":
        ranges.extend([(0x0C, 0x10), (0x18, 0x24)])
        if payload_size >= 0x84:
            ranges.append((0x7C, 0x84))
    elif kind == "site_part2":
        ranges.extend([
            (0x000, 0x004),
            (0x018, 0x01C),
            (0x020, 0x024),
            (0x028, 0x030),
            (0x034, 0x03C),
            (0x040, 0x058),
            (0x134, 0x210),
            (0x290, 0x294),
            (0x2A4, 0x2B0),
        ])
    elif kind == "entity_part1":
        ranges.append((0x000, 0x024))

    return [(start, min(end, payload_size)) for start, end in ranges if start < payload_size]


def zero_reserved_zero_bytes_in_block(block: Mapping[str, Any]) -> int:
    """把一个 block 中明确标记为 `reserved_zero` 的字节清 0。"""

    kind = str(block.get("kind", ""))
    raw_hex = block.get("raw_hex")
    if not kind or not isinstance(raw_hex, str):
        return 0

    payload = bytearray.fromhex(raw_hex)
    zeroed = 0
    for start, end in reserved_zero_ranges(kind, len(payload)):
        for index in range(start, end):
            if payload[index] != 0:
                payload[index] = 0
                zeroed += 1
    block["raw_hex"] = payload.hex()
    return zeroed


def zero_reserved_zero_fields_inplace(doc: dict[str, Any]) -> int:
    """把当前格式中明确标成 `reserved_zero` 的字段清 0。"""

    zeroed = 0

    def visit_block(block: Any) -> None:
        nonlocal zeroed
        if isinstance(block, Mapping):
            zeroed += zero_reserved_zero_bytes_in_block(block)

    visit_block(doc.get("root_part1"))
    visit_block(doc.get("root_part2"))
    for force in doc.get("forces", []):
        if not isinstance(force, dict):
            continue
        visit_block(force.get("part1"))
        visit_block(force.get("part2"))
        for site in force.get("sites", []):
            if not isinstance(site, dict):
                continue
            visit_block(site.get("part1"))
            visit_block(site.get("part2"))
            for entity_list_name in ("entities", "optional_entities", "extra_entities"):
                for entity in site.get(entity_list_name, []):
                    if not isinstance(entity, dict):
                        continue
                    visit_block(entity.get("part1"))
                    visit_block(entity.get("part2"))
    return zeroed


def default_output_paths(source_path: Path, out_dir: Path) -> tuple[Path, Path]:
    """根据源文件名生成默认的 JSON 与回写 STG 路径。"""

    return out_dir / f"{source_path.stem}.json", out_dir / f"{source_path.stem}.rebuilt.stg"


def convert_stg_json_roundtrip(
    stg_path: str | Path,
    *,
    json_out: str | Path,
    stg_out: str | Path,
    tables: Mapping[str, list[dict[str, str]]] | None = None,
    tables_dir: str | Path | None = None,
    xlsx_path: str | Path | None = None,
    include_words: bool = False,
    strict: bool = True,
    detect_tail_entities: bool = True,
    strip_reserved_fields: bool = False,
    zero_reserved_zero_fields: bool = False,
    recompute_counts: bool = True,
    patch_fields: bool = True,
) -> dict[str, Any]:
    """执行 `stg -> json -> stg`，可选移除保留字段或清 0 保留零字段。"""

    source_path = Path(stg_path)
    table_map = resolve_tables(tables=tables, tables_dir=tables_dir, xlsx_path=xlsx_path)
    doc = parse_stage_file(
        source_path,
        tables=table_map,
        include_words=include_words,
        strict=strict,
        detect_tail_entities=detect_tail_entities,
    )
    json_doc = copy.deepcopy(doc)
    zeroed_byte_count = 0
    if strip_reserved_fields:
        strip_reserved_fields_inplace(json_doc)
    if zero_reserved_zero_fields:
        zeroed_byte_count = zero_reserved_zero_fields_inplace(json_doc)

    json_path = Path(json_out)
    write_json(json_doc, json_path)
    build_result = build_stage_file_from_json(
        json_path,
        stg_out,
        compare_path=source_path,
        recompute_counts=recompute_counts,
        patch_fields=patch_fields,
    )
    return {
        "source": str(source_path),
        "json": str(json_path),
        "rebuilt": str(stg_out),
        "strip_reserved_fields": strip_reserved_fields,
        "zero_reserved_zero_fields": zero_reserved_zero_fields,
        "zeroed_reserved_zero_bytes": zeroed_byte_count,
        "identical": build_result.get("identical_to_compare"),
        "size": build_result.get("size"),
        "sha256": build_result.get("sha256"),
        "compare_sha256": build_result.get("compare_sha256"),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="把 `.stg` 导出为 JSON，再从 JSON 回写 `.stg`。")
    parser.add_argument("stg", help="输入 `.stg` 路径。")
    parser.add_argument("--json-out", help="导出的 JSON 路径；默认写到 out-dir。")
    parser.add_argument("--stg-out", help="回写后的 `.stg` 路径；默认写到 out-dir。")
    parser.add_argument("--out-dir", default="derived/stg_json_roundtrip", help="默认输出目录。")
    parser.add_argument("--tables-dir", help="可选：general.txt/castle.txt/soldier.txt/magic.txt 所在目录。")
    parser.add_argument("--xlsx", help="可选：stage_ini_conversion_tables.xlsx 路径。")
    parser.add_argument("--include-words", action="store_true", help="在 JSON 中附带每个 block 的 u32/i32 words。")
    parser.add_argument("--no-strict", action="store_true", help="关闭严格结构校验。")
    parser.add_argument("--no-tail-detect", action="store_true", help="关闭 after_forces_tail 中 entity-like 候选扫描。")
    parser.add_argument("--strip-reserved-fields", action="store_true", help="仅移除 JSON 中的保留字段名与字段值。")
    parser.add_argument("--zero-reserved-zero-fields", action="store_true", help="只把当前格式中明确标成 reserved_zero 的字段清 0，并写回 `.stg`。")
    parser.add_argument("--zero-undefined-data", dest="zero_reserved_zero_fields", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-recompute-counts", action="store_true", help="回写时不重算 force/site/entity 计数。")
    parser.add_argument("--no-patch-fields", action="store_true", help="回写时不把 JSON fields patch 回 raw_hex。")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    source_path = Path(args.stg)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    default_json_out, default_stg_out = default_output_paths(source_path, out_dir)
    result = convert_stg_json_roundtrip(
        source_path,
        json_out=args.json_out or default_json_out,
        stg_out=args.stg_out or default_stg_out,
        tables_dir=args.tables_dir,
        xlsx_path=args.xlsx,
        include_words=args.include_words,
        strict=not args.no_strict,
        detect_tail_entities=not args.no_tail_detect,
        strip_reserved_fields=args.strip_reserved_fields,
        zero_reserved_zero_fields=args.zero_reserved_zero_fields,
        recompute_counts=not args.no_recompute_counts,
        patch_fields=not args.no_patch_fields,
    )
    print(f"JSON: {result['json']}")
    print(f"STG : {result['rebuilt']}")
    print(f"identical: {result['identical']}")
    if result["zero_reserved_zero_fields"]:
        print(f"zeroed_reserved_zero_bytes: {result['zeroed_reserved_zero_bytes']}")
    return 0 if result.get("identical") is not False else 2


if __name__ == "__main__":
    raise SystemExit(main())
