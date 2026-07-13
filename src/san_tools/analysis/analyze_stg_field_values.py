from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from san_tools.codecs.stg_stream_codec_refactored import load_txt_tables, parse_stage_file
from san_tools.project_paths import find_game_data_dir


DEFAULT_UNCERTAIN_CONFIDENCES = ("candidate", "unknown")
DEFAULT_STAGE_GLOBS = ("stage*.stg", "new-stage*.stg")


def normalize_confidences(values: Sequence[str]) -> set[str]:
    return {value.strip().lower() for value in values if value.strip()}


def sort_key(path: Path) -> tuple[str, str]:
    return (str(path.parent).lower(), path.name.lower())


def discover_stage_files(inputs: Sequence[str | Path], game_dir: Path) -> list[Path]:
    """把命令行输入展开为待分析的 `.stg` 文件列表。"""

    candidates: list[Path] = []
    seen: set[Path] = set()
    raw_inputs = [Path(item) for item in inputs] if inputs else [game_dir, game_dir / "SGBY_MAP" / "new_san"]
    for item in raw_inputs:
        if item.is_file() and item.suffix.lower() == ".stg":
            resolved = item.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(item)
            continue
        if item.is_dir():
            for pattern in DEFAULT_STAGE_GLOBS:
                for path in sorted(item.glob(pattern), key=sort_key):
                    resolved = path.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        candidates.append(path)
    return sorted(candidates, key=sort_key)


def to_hex_if_int(value: Any) -> str:
    if isinstance(value, int):
        return f"0x{value & 0xFFFFFFFF:08X}"
    return ""


def stage_source_label(path: Path, game_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(game_dir.resolve())).replace("\\", "/")
    except Exception:
        return str(path.resolve())


def build_row(
    *,
    stage_file: str,
    stage_source: str,
    force_index: int | None = None,
    force_name: str = "",
    site_index: int | None = None,
    site_name: str = "",
    entity_index: int | None = None,
    entity_name: str = "",
    entity_list: str = "",
    block_kind: str = "",
    block_label: str = "",
    field_origin: str,
    field_name: str,
    field_offset: str,
    field_type: str,
    field_confidence: str,
    field_note: str,
    field_value: Any,
) -> dict[str, Any]:
    field_key = f"{block_kind}:{field_offset}:{field_name}" if block_kind else f"{field_origin}:{field_name}"
    return {
        "stage_file": stage_file,
        "stage_source": stage_source,
        "force_index": force_index,
        "force_name": force_name,
        "site_index": site_index,
        "site_name": site_name,
        "entity_index": entity_index,
        "entity_name": entity_name,
        "entity_list": entity_list,
        "block_kind": block_kind,
        "block_label": block_label,
        "field_origin": field_origin,
        "field_name": field_name,
        "field_offset": field_offset,
        "field_key": field_key,
        "field_type": field_type,
        "field_confidence": field_confidence,
        "field_note": field_note,
        "field_value": field_value,
        "field_value_hex": to_hex_if_int(field_value),
    }


def iter_block_rows(
    *,
    stage_file: str,
    stage_source: str,
    block: Mapping[str, Any],
    force_index: int | None = None,
    force_name: str = "",
    site_index: int | None = None,
    site_name: str = "",
    entity_index: int | None = None,
    entity_name: str = "",
    entity_list: str = "",
) -> Iterable[dict[str, Any]]:
    """把一个 block 内的字段和 size 前缀展开成逐字段行。"""

    block_kind = str(block.get("kind", ""))
    block_label = str(block.get("label", ""))
    size_value = int(block.get("size", 0))
    yield build_row(
        stage_file=stage_file,
        stage_source=stage_source,
        force_index=force_index,
        force_name=force_name,
        site_index=site_index,
        site_name=site_name,
        entity_index=entity_index,
        entity_name=entity_name,
        entity_list=entity_list,
        block_kind=block_kind,
        block_label=block_label,
        field_origin="size_prefix",
        field_name="__block_size__",
        field_offset=str(block.get("size_offset", "")),
        field_type="u32",
        field_confidence="structural",
        field_note="block 的 payload 长度前缀。",
        field_value=size_value,
    )
    fields = block.get("fields", {})
    meta = block.get("field_meta", {})
    if not isinstance(fields, Mapping):
        return
    for field_name, field_value in fields.items():
        field_meta = meta.get(field_name, {}) if isinstance(meta, Mapping) else {}
        yield build_row(
            stage_file=stage_file,
            stage_source=stage_source,
            force_index=force_index,
            force_name=force_name,
            site_index=site_index,
            site_name=site_name,
            entity_index=entity_index,
            entity_name=entity_name,
            entity_list=entity_list,
            block_kind=block_kind,
            block_label=block_label,
            field_origin="named_field",
            field_name=str(field_name),
            field_offset=str(field_meta.get("offset", "")),
            field_type=str(field_meta.get("type", "")),
            field_confidence=str(field_meta.get("confidence", "")),
            field_note=str(field_meta.get("note", "")),
            field_value=field_value,
        )


def collect_field_rows(doc: Mapping[str, Any], stage_path: Path, game_dir: Path) -> list[dict[str, Any]]:
    """把一个解析后的 STG 文档展开为逐字段统计行。"""

    stage_file = stage_path.name
    stage_source = stage_source_label(stage_path, game_dir)
    rows: list[dict[str, Any]] = []

    def add_top_level(field_name: str, field_value: Any, field_note: str, *, force: Mapping[str, Any] | None = None, site: Mapping[str, Any] | None = None) -> None:
        rows.append(
            build_row(
                stage_file=stage_file,
                stage_source=stage_source,
                force_index=force.get("index") if force else None,
                force_name=str(force.get("name", "")) if force else "",
                site_index=site.get("index") if site else None,
                site_name=str(site.get("name", "")) if site else "",
                block_kind="",
                block_label="",
                field_origin="top_level",
                field_name=field_name,
                field_offset="",
                field_type="u32",
                field_confidence="structural",
                field_note=field_note,
                field_value=field_value,
            )
        )

    add_top_level("present_or_version", doc.get("present_or_version"), "文件起始的 u32 版本/存在标记。")
    add_top_level("force_count", doc.get("force_count"), "root 后紧接的势力数量。")

    root1 = doc.get("root_part1", {})
    if isinstance(root1, Mapping):
        rows.extend(iter_block_rows(stage_file=stage_file, stage_source=stage_source, block=root1))
    root2 = doc.get("root_part2", {})
    if isinstance(root2, Mapping):
        rows.extend(iter_block_rows(stage_file=stage_file, stage_source=stage_source, block=root2))

    for force in doc.get("forces", []):
        if not isinstance(force, Mapping):
            continue
        force_name = str(force.get("name", ""))
        force_index = force.get("index")
        add_top_level("site_list_pre_count_or_flag", force.get("site_list_pre_count_or_flag"), "force_part2 后紧接的据点前置计数/标记。", force=force)
        for key in ("part1", "part2"):
            block = force.get(key)
            if isinstance(block, Mapping):
                rows.extend(
                    iter_block_rows(
                        stage_file=stage_file,
                        stage_source=stage_source,
                        block=block,
                        force_index=force_index,
                        force_name=force_name,
                    )
                )
        for site in force.get("sites", []):
            if not isinstance(site, Mapping):
                continue
            site_name = str(site.get("name", ""))
            site_index = site.get("index")
            add_top_level("primary_entity_count", site.get("primary_entity_count"), "site_part2 后紧接的主实体数量。", force=force, site=site)
            for key in ("part1", "part2"):
                block = site.get(key)
                if isinstance(block, Mapping):
                    rows.extend(
                        iter_block_rows(
                            stage_file=stage_file,
                            stage_source=stage_source,
                            block=block,
                            force_index=force_index,
                            force_name=force_name,
                            site_index=site_index,
                            site_name=site_name,
                        )
                    )
            entity_lists = (
                ("primary", site.get("entities", [])),
                ("optional", site.get("optional_entities", [])),
                ("extra", site.get("extra_entities", [])),
            )
            for list_name, entity_items in entity_lists:
                for entity in entity_items:
                    if not isinstance(entity, Mapping):
                        continue
                    entity_name = str(entity.get("name", ""))
                    entity_index = entity.get("index")
                    for key in ("part1", "part2"):
                        block = entity.get(key)
                        if isinstance(block, Mapping):
                            rows.extend(
                                iter_block_rows(
                                    stage_file=stage_file,
                                    stage_source=stage_source,
                                    block=block,
                                    force_index=force_index,
                                    force_name=force_name,
                                    site_index=site_index,
                                    site_name=site_name,
                                    entity_index=entity_index,
                                    entity_name=entity_name,
                                    entity_list=list_name,
                                )
                            )
    return rows


def filter_uncertain_rows(rows: Sequence[Mapping[str, Any]], uncertain_confidences: set[str]) -> list[dict[str, Any]]:
    """按置信度筛出含义仍不确定的字段行。"""

    return [dict(row) for row in rows if str(row.get("field_confidence", "")).lower() in uncertain_confidences]


def summarize_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """把逐字段明细按字段和值聚合，便于统一观察共性。"""

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    force_names: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    site_names: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    entity_names: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    stages: dict[tuple[str, str, str], set[str]] = defaultdict(set)

    for row in rows:
        block_kind = str(row.get("block_kind", ""))
        field_key = str(row.get("field_key", ""))
        value_key = str(row.get("field_value", ""))
        group_key = (block_kind, field_key, value_key)
        if group_key not in grouped:
            grouped[group_key] = {
                "block_kind": block_kind,
                "field_key": field_key,
                "field_name": row.get("field_name", ""),
                "field_offset": row.get("field_offset", ""),
                "field_type": row.get("field_type", ""),
                "field_confidence": row.get("field_confidence", ""),
                "field_note": row.get("field_note", ""),
                "field_value": row.get("field_value", ""),
                "field_value_hex": row.get("field_value_hex", ""),
                "occurrence_count": 0,
            }
        grouped[group_key]["occurrence_count"] += 1
        stages[group_key].add(str(row.get("stage_source", "")))
        if row.get("force_name"):
            force_names[group_key].add(str(row.get("force_name", "")))
        if row.get("site_name"):
            site_names[group_key].add(str(row.get("site_name", "")))
        if row.get("entity_name"):
            entity_names[group_key].add(str(row.get("entity_name", "")))

    summary_rows: list[dict[str, Any]] = []
    for group_key, payload in grouped.items():
        summary = dict(payload)
        summary["stage_count"] = len(stages[group_key])
        summary["stage_examples"] = " | ".join(sorted(stages[group_key])[:5])
        summary["force_examples"] = " | ".join(sorted(force_names[group_key])[:5])
        summary["site_examples"] = " | ".join(sorted(site_names[group_key])[:5])
        summary["entity_examples"] = " | ".join(sorted(entity_names[group_key])[:5])
        summary_rows.append(summary)
    return sorted(
        summary_rows,
        key=lambda item: (
            str(item.get("block_kind", "")),
            str(item.get("field_offset", "")),
            str(item.get("field_name", "")),
            -int(item.get("occurrence_count", 0)),
            str(item.get("field_value", "")),
        ),
    )


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="统计 `.stg` 各字段取值，并额外导出含义不确定字段的明细与聚合表。")
    parser.add_argument("inputs", nargs="*", help="可选：`.stg` 文件或目录；为空时自动扫描游戏目录与 `new_san`。")
    parser.add_argument("--game-dir", type=Path, help="游戏数据目录；默认自动查找 data/game。")
    parser.add_argument("--out-dir", type=Path, default=Path("derived/stg_field_statistics"), help="输出目录。")
    parser.add_argument(
        "--uncertain-confidence",
        nargs="+",
        default=list(DEFAULT_UNCERTAIN_CONFIDENCES),
        help="哪些置信度视为“含义不确定”；默认 candidate unknown。",
    )
    parser.add_argument("--strict-parse", action="store_true", help="遇到任一 STG 解析失败时立刻报错退出。")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    game_dir = args.game_dir.resolve() if args.game_dir else find_game_data_dir()
    stage_files = discover_stage_files(args.inputs, game_dir)
    if not stage_files:
        raise SystemExit("未找到可分析的 `.stg` 文件。")

    uncertain_confidences = normalize_confidences(args.uncertain_confidence)
    tables = load_txt_tables(game_dir)

    all_rows: list[dict[str, Any]] = []
    parsed_files: list[str] = []
    parse_errors: list[dict[str, str]] = []

    for stage_path in stage_files:
        try:
            doc = parse_stage_file(stage_path, tables=tables, strict=True, detect_tail_entities=True)
            all_rows.extend(collect_field_rows(doc, stage_path, game_dir))
            parsed_files.append(stage_source_label(stage_path, game_dir))
        except Exception as exc:
            parse_errors.append({"stage_source": stage_source_label(stage_path, game_dir), "error": str(exc)})
            if args.strict_parse:
                raise

    uncertain_rows = filter_uncertain_rows(all_rows, uncertain_confidences)
    all_summary_rows = summarize_rows(all_rows)
    uncertain_summary_rows = summarize_rows(uncertain_rows)

    out_dir = args.out_dir.resolve()
    write_csv(out_dir / "stg_field_values_all_rows.csv", all_rows)
    write_csv(out_dir / "stg_field_values_uncertain_rows.csv", uncertain_rows)
    write_csv(out_dir / "stg_field_values_all_summary.csv", all_summary_rows)
    write_csv(out_dir / "stg_field_values_uncertain_summary.csv", uncertain_summary_rows)

    manifest = {
        "game_dir": str(game_dir),
        "parsed_stage_count": len(parsed_files),
        "parsed_stages": parsed_files,
        "all_row_count": len(all_rows),
        "uncertain_row_count": len(uncertain_rows),
        "all_summary_count": len(all_summary_rows),
        "uncertain_summary_count": len(uncertain_summary_rows),
        "uncertain_confidences": sorted(uncertain_confidences),
        "parse_errors": parse_errors,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"已分析 {len(parsed_files)} 个 STG，逐字段明细 {len(all_rows)} 行。")
    print(f"输出目录：{out_dir}")
    if parse_errors:
        print(f"有 {len(parse_errors)} 个文件解析失败，详情见 {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
