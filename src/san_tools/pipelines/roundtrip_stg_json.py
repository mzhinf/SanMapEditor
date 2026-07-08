from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Mapping, Sequence

from san_tools.codecs.stg_stream_codec_refactored import (
    FIELD_SPECS,
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


def compute_defined_byte_mask(kind: str, payload_size: int) -> list[bool]:
    """根据当前字段规格计算 payload 中哪些字节已被定义覆盖。"""

    mask = [False] * payload_size
    for spec in FIELD_SPECS.get(kind, []):
        width = int(spec.size)
        start = int(spec.offset)
        end = min(payload_size, start + width)
        for index in range(start, end):
            mask[index] = True
    return mask


def zero_undefined_bytes_in_block(block: Mapping[str, Any]) -> int:
    """把一个 block 的未定义 payload 字节清 0，并返回清零的字节数。"""

    kind = str(block.get("kind", ""))
    raw_hex = block.get("raw_hex")
    if not kind or not isinstance(raw_hex, str):
        return 0
    payload = bytearray.fromhex(raw_hex)
    mask = compute_defined_byte_mask(kind, len(payload))
    zeroed = 0
    for index, covered in enumerate(mask):
        if not covered and payload[index] != 0:
            payload[index] = 0
            zeroed += 1
    block["raw_hex"] = payload.hex()
    return zeroed


def zero_undefined_data_inplace(doc: dict[str, Any]) -> int:
    """把当前格式未覆盖到的 `.stg` 二进制区域全部清 0。"""

    zeroed = 0

    def visit_block(block: Any) -> None:
        nonlocal zeroed
        if isinstance(block, Mapping):
            zeroed += zero_undefined_bytes_in_block(block)

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

    tail = doc.get("after_forces_tail")
    if isinstance(tail, dict) and isinstance(tail.get("raw_hex"), str):
        tail_bytes = bytearray.fromhex(tail["raw_hex"])
        zeroed += sum(1 for value in tail_bytes if value != 0)
        tail["raw_hex"] = bytes(len(tail_bytes)).hex()
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
    zero_undefined_data: bool = False,
    recompute_counts: bool = True,
    patch_fields: bool = True,
) -> dict[str, Any]:
    """执行 `stg -> json -> stg`，可选移除保留字段或清 0 未定义字节。"""

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
    if zero_undefined_data:
        zeroed_byte_count = zero_undefined_data_inplace(json_doc)

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
        "zero_undefined_data": zero_undefined_data,
        "zeroed_byte_count": zeroed_byte_count,
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
    parser.add_argument("--zero-undefined-data", action="store_true", help="把当前格式未定义覆盖到的二进制字节清 0，并写回 `.stg`。")
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
        zero_undefined_data=args.zero_undefined_data,
        recompute_counts=not args.no_recompute_counts,
        patch_fields=not args.no_patch_fields,
    )
    print(f"JSON: {result['json']}")
    print(f"STG : {result['rebuilt']}")
    print(f"identical: {result['identical']}")
    if result["zero_undefined_data"]:
        print(f"zeroed_undefined_bytes: {result['zeroed_byte_count']}")
    return 0 if result.get("identical") is not False else 2


if __name__ == "__main__":
    raise SystemExit(main())
