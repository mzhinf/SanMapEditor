from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

import san_tools.codecs.stage_ini_codec as stage_ini_codec

TXT_DIRNAME = "uft8-game-txt"
OUTPUT_DIR = Path("derived/stage_ini_txt_analysis")
DIRECT_SHEETS = ["general", "castle", "magic", "soldier"]
SUPPLEMENTAL_SHEETS = ["history"]
TRAILER_SHEETS = ["general_tail", "castle_tail", "soldier_tail"]


def ensure_output_dir(root: Path) -> Path:
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def read_tsv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [trim_trailing_empty_cells(row) for row in csv.reader(handle, delimiter="\t") if row]


def trim_trailing_empty_cells(row: Iterable[object]) -> list[str]:
    trimmed = [str(value) for value in row]
    while trimmed and trimmed[-1] == "":
        trimmed.pop()
    return trimmed


def parse_int(cell: object) -> int | None:
    text = str(cell).strip()
    if not text:
        return None
    if text.lstrip("-").isdigit():
        return int(text)
    return None


def numeric_cells(row: Iterable[object], start_index: int = 1) -> list[int]:
    values: list[int] = []
    for cell in list(row)[start_index:]:
        parsed = parse_int(cell)
        if parsed is not None:
            values.append(parsed)
    return values


def record_blob(row: dict[str, object]) -> bytes:
    return bytes.fromhex(str(row["raw_hex"]))


def record_dwords(row: dict[str, object]) -> list[int]:
    return stage_ini_codec.read_u32_dwords(record_blob(row))


def classify_name_relation(txt_name: str, stage_names: Iterable[str]) -> str:
    cleaned = [str(name).strip() for name in stage_names if str(name).strip()]
    if txt_name in cleaned:
        return "exact_name"
    for stage_name in cleaned:
        if txt_name and (txt_name in stage_name or stage_name in txt_name):
            return "alias_name"
    return "numeric_only"


def build_stream(records: list[dict[str, object]]) -> dict[str, object]:
    dwords: list[int] = []
    record_count = len(records)
    dwords_per_record = len(record_dwords(records[0])) if records else 0
    for row in records:
        dwords.extend(record_dwords(row))
    return {
        "records": records,
        "dwords": dwords,
        "dwords_per_record": dwords_per_record,
        "record_count": record_count,
    }


def stream_record_span(start_dword: int, value_count: int, dwords_per_record: int) -> tuple[int, int]:
    record_start = start_dword // dwords_per_record
    record_end = (start_dword + max(value_count - 1, 0)) // dwords_per_record
    return record_start, record_end


def stream_record_names(records: list[dict[str, object]], record_start: int, record_end: int) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for record_index in range(record_start, record_end + 1):
        row = records[record_index]
        for value in (row.get("name", ""), row.get("label", "")):
            text = str(value).strip()
            if text and text not in seen:
                names.append(text)
                seen.add(text)
    return names


def stage_title_for_names(names: list[str], fallback: str) -> str:
    if not names:
        return fallback
    return " | ".join(names)


def find_exact_stream_candidate(
    stream: dict[str, object],
    txt_name: str,
    numeric_values: list[int],
    after_start: int = -1,
) -> dict[str, object] | None:
    if not numeric_values:
        return None
    dwords = list(stream["dwords"])
    records = list(stream["records"])
    dwords_per_record = int(stream["dwords_per_record"])
    limit = len(dwords) - len(numeric_values) + 1
    if limit <= 0:
        return None

    candidates: list[tuple[int, int, dict[str, object]]] = []
    for start in range(max(after_start + 1, 0), limit):
        if dwords[start : start + len(numeric_values)] != numeric_values:
            continue
        record_start, record_end = stream_record_span(start, len(numeric_values), dwords_per_record)
        names = stream_record_names(records, record_start, record_end)
        relation = classify_name_relation(txt_name, names)
        relation_score = {"exact_name": 3, "alias_name": 2, "numeric_only": 1}[relation]
        candidate = {
            "start_dword": start,
            "record_start": record_start,
            "record_end": record_end,
            "stage_names": names,
            "name_relation": relation,
        }
        candidates.append((relation_score, -start, candidate))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def build_trailer_row(
    txt_row_number: int,
    row: list[str],
    min_columns: int,
    reason: str,
    candidate_title: str = "",
    candidate_family: str = "",
) -> list[object]:
    padded = list(row)
    while len(padded) < min_columns:
        padded.append("")
    return [txt_row_number, reason, candidate_title, candidate_family, *padded]


def classify_general_special_row(
    row: list[str],
    reference_records: list[dict[str, object]],
) -> tuple[str, str, str]:
    title = row[0].strip() if row else ""
    if not title or title == "0":
        return "footer_stub", "", ""
    for record in reference_records:
        if str(record.get("name", "")).strip() == title:
            return "special_character_template", title, str(record.get("family_guess", ""))
    return "unmapped_general_row", "", ""


def classify_tail_footer_row(row: list[str], *, kind: str) -> tuple[str, str, str]:
    title = row[0].strip() if row else ""
    numeric = [parse_int(value) for value in row if parse_int(value) is not None]
    if not any(numeric):
        return "zero_padding", "", ""
    if kind == "castle":
        if title.isdigit():
            return "city_tail_parameter_block", "", ""
        return "unmapped_castle_row", "", ""
    if kind == "soldier":
        if not title:
            return "soldier_tail_footer", "", ""
        return "unmapped_soldier_row", "", ""
    return "unmapped_row", "", ""


def build_history_row(txt_row_number: int, row: list[str], general_by_name: dict[str, dict[str, object]]) -> list[object]:
    txt_name = row[0].strip()
    linked = general_by_name.get(txt_name)
    record_index = linked["record_index"] if linked else ""
    stage_name = linked["name"] if linked else ""
    return [txt_row_number, stage_name, record_index, *row]


def analysis_headers(original_header: list[str]) -> list[str]:
    return [
        "row_id",
        "TXT标题",
        "StageINI标题",
        "StageINI记录跨度",
        *original_header[1:],
        "__txt_row_number",
        "__stream_section",
        "__stream_start_dword",
        "__stream_value_count",
        "__record_start",
        "__record_end",
        "__name_relation",
        "__write_enabled",
    ]


def conversion_headers(original_header: list[str]) -> list[str]:
    return ["row_id", "title", *original_header[1:]]


def build_analysis_row(
    row_id: int,
    txt_row_number: int,
    original_row: list[str],
    stream_section: str,
    candidate: dict[str, object],
    write_enabled: int,
) -> list[object]:
    stage_title = stage_title_for_names(list(candidate["stage_names"]), original_row[0].strip())
    record_span = f"{stream_section}[{candidate['record_start']}:{candidate['record_end']}]"
    return [
        row_id,
        original_row[0].strip(),
        stage_title,
        record_span,
        *original_row[1:],
        txt_row_number,
        stream_section,
        int(candidate["start_dword"]),
        len(numeric_cells(original_row)),
        int(candidate["record_start"]),
        int(candidate["record_end"]),
        str(candidate["name_relation"]),
        write_enabled,
    ]


def build_conversion_row(row_id: int, original_row: list[str]) -> list[object]:
    return [row_id, original_row[0].strip(), *original_row[1:]]


def stream_stride_summary(row_models: dict[str, dict[str, object]]) -> str:
    starts = [int(model["stream_start_dword"]) for model in row_models.values()]
    if len(starts) < 2:
        return ""
    diffs = [b - a for a, b in zip(starts, starts[1:])]
    counter = Counter(diffs)
    step, count = counter.most_common(1)[0]
    return f"{step} dwords x {count}"


def map_stream_table(
    *,
    source_file: str,
    sheet_name: str,
    rows: list[list[str]],
    stream_section: str,
    records: list[dict[str, object]],
    skip_numeric_title: bool,
    classification_records: list[dict[str, object]] | None = None,
) -> tuple[list[list[object]], list[list[object]], dict[str, object], list[list[object]], dict[str, object]]:
    stream = build_stream(records)
    trailer_reference_records = classification_records if classification_records is not None else records
    header = rows[0]
    analysis_rows: list[list[object]] = []
    trailer_rows: list[list[object]] = []
    conversion_rows: list[list[object]] = []
    row_models: dict[str, dict[str, object]] = {}
    exact_count = 0
    alias_count = 0
    after_start = -1

    for txt_row_number, row in enumerate(rows[1:], start=2):
        title = row[0].strip() if row else ""
        if not title or title == "0" or (skip_numeric_title and title.isdigit()):
            if stream_section == "main":
                reason, candidate_title, candidate_family = classify_general_special_row(row, trailer_reference_records)
            else:
                reason, candidate_title, candidate_family = classify_tail_footer_row(row, kind=sheet_name)
            trailer_rows.append(build_trailer_row(txt_row_number, row, len(header), reason, candidate_title, candidate_family))
            continue

        numeric_values = numeric_cells(row)
        if not numeric_values:
            if stream_section == "main":
                reason, candidate_title, candidate_family = classify_general_special_row(row, trailer_reference_records)
            else:
                reason, candidate_title, candidate_family = classify_tail_footer_row(row, kind=sheet_name)
            trailer_rows.append(build_trailer_row(txt_row_number, row, len(header), reason, candidate_title, candidate_family))
            continue

        candidate = find_exact_stream_candidate(stream, title, numeric_values, after_start)
        if candidate is None:
            if stream_section == "main":
                reason, candidate_title, candidate_family = classify_general_special_row(row, trailer_reference_records)
            else:
                reason, candidate_title, candidate_family = classify_tail_footer_row(row, kind=sheet_name)
            trailer_rows.append(build_trailer_row(txt_row_number, row, len(header), reason, candidate_title, candidate_family))
            continue

        row_id = txt_row_number - 1
        relation = str(candidate["name_relation"])
        if relation == "exact_name":
            exact_count += 1
        elif relation == "alias_name":
            alias_count += 1

        analysis_rows.append(
            build_analysis_row(
                row_id=row_id,
                txt_row_number=txt_row_number,
                original_row=row,
                stream_section=stream_section,
                candidate=candidate,
                write_enabled=1,
            )
        )
        conversion_rows.append(build_conversion_row(row_id, row))
        row_models[str(row_id)] = {
            "row_id": row_id,
            "txt_row_number": txt_row_number,
            "title": title,
            "sheet": sheet_name,
            "source_file": source_file,
            "stream_section": stream_section,
            "stream_start_dword": int(candidate["start_dword"]),
            "numeric_count": len(numeric_values),
            "record_start": int(candidate["record_start"]),
            "record_end": int(candidate["record_end"]),
            "stage_names": list(candidate["stage_names"]),
            "name_relation": relation,
        }
        after_start = int(candidate["start_dword"])

    relation = "direct" if not trailer_rows else "direct_with_trailer"
    summary = {
        "file": source_file,
        "sheet": sheet_name,
        "relation": relation,
        "mapped_rows": len(conversion_rows),
        "exact_name_rows": exact_count,
        "alias_rows": alias_count,
        "trailer_rows": len(trailer_rows),
        "notes": f"按 {stream_section} 原始 dword 流精确定位；当前稳定步长 {stream_stride_summary(row_models) or 'unknown'}。",
    }
    conversion_model = {
        "sheet": sheet_name,
        "source_file": source_file,
        "stream_section": stream_section,
        "value_headers": header[1:],
        "row_models": row_models,
    }
    return analysis_rows, trailer_rows, summary, conversion_rows, conversion_model


def map_history(rows: list[list[str]], stage_payload: dict[str, object]) -> tuple[list[list[object]], dict[str, object]]:
    general_by_name = {
        str(row["name"]).strip(): row
        for row in stage_payload["tables"]["general_master"]
        if row.get("name")
    }
    linked_rows = [
        build_history_row(txt_row_number, row, general_by_name)
        for txt_row_number, row in enumerate(rows[1:], start=2)
        if row and row[0].strip()
    ]
    matched_rows = sum(1 for row in linked_rows if row[2] != "")
    summary = {
        "file": "History.txt",
        "sheet": "history",
        "relation": "supplemental",
        "mapped_rows": matched_rows,
        "exact_name_rows": matched_rows,
        "alias_rows": 0,
        "trailer_rows": len(linked_rows) - matched_rows,
        "notes": "用于补充查看人物条目，不参与 stage.ini 自动回写。",
    }
    return linked_rows, summary


def build_overview_rows(file_summaries: list[dict[str, object]]) -> list[list[object]]:
    rows: list[list[object]] = []
    for item in file_summaries:
        rows.append(
            [
                item["file"],
                item["sheet"],
                item["relation"],
                item["mapped_rows"],
                item["exact_name_rows"],
                item["alias_rows"],
                item["trailer_rows"],
                item["notes"],
            ]
        )
    return rows


def build_notes_rows(stage_payload: dict[str, object], file_summaries: list[dict[str, object]]) -> list[list[object]]:
    direct_files = ", ".join(item["file"] for item in file_summaries if str(item["relation"]).startswith("direct"))
    return [
        ["stage.ini 路径", stage_payload["stage_ini_path"]],
        ["主表规模", f"{stage_payload['header']['main_count']} * {stage_payload['header']['main_stride']} bytes"],
        ["尾表规模", f"{stage_payload['header']['tail_count']} * {stage_payload['header']['tail_stride']} bytes"],
        ["已确认直接关联 txt", direct_files],
        ["分析版用途", "保留 StageINI 关联标题、记录跨度、dword 起点等逆向信息，便于复核二进制结构。"],
        ["转换版用途", "只保留 row_id、title 和可回写字段；真正的回写定位信息放在 JSON 元数据，不写进 Excel。"],
        ["回写策略", "当前 Excel -> stage.ini 只改写已确认映射字段对应的 dword；名称和未识别字节原样保留。"],
    ]


def build_bundle(root: Path) -> dict[str, object]:
    root = root.resolve()
    txt_dir = root / TXT_DIRNAME
    stage_payload = stage_ini_codec.build_payload(root)

    general_rows = read_tsv_rows(txt_dir / "general.txt")
    castle_rows = read_tsv_rows(txt_dir / "castle.txt")
    magic_rows = read_tsv_rows(txt_dir / "magic.txt")
    soldier_rows = read_tsv_rows(txt_dir / "soldier.txt")
    history_rows = read_tsv_rows(txt_dir / "History.txt")

    general_analysis, general_trailer, general_summary, general_conversion, general_model = map_stream_table(
        source_file="general.txt",
        sheet_name="general",
        rows=general_rows,
        stream_section="main",
        records=stage_payload["tables"]["main_records"],
        skip_numeric_title=False,
        classification_records=stage_payload["tables"]["main_records"] + stage_payload["tables"]["tail_records"],
    )
    castle_analysis, castle_trailer, castle_summary, castle_conversion, castle_model = map_stream_table(
        source_file="castle.txt",
        sheet_name="castle",
        rows=castle_rows,
        stream_section="tail",
        records=stage_payload["tables"]["tail_records"],
        skip_numeric_title=True,
    )
    magic_analysis, _magic_trailer, magic_summary, magic_conversion, magic_model = map_stream_table(
        source_file="magic.txt",
        sheet_name="magic",
        rows=magic_rows,
        stream_section="tail",
        records=stage_payload["tables"]["tail_records"],
        skip_numeric_title=False,
    )
    soldier_analysis, soldier_trailer, soldier_summary, soldier_conversion, soldier_model = map_stream_table(
        source_file="soldier.txt",
        sheet_name="soldier",
        rows=soldier_rows,
        stream_section="tail",
        records=stage_payload["tables"]["tail_records"],
        skip_numeric_title=False,
    )
    history_linked, history_summary = map_history(history_rows, stage_payload)

    file_summaries = [general_summary, castle_summary, magic_summary, soldier_summary, history_summary]

    analysis_workbook_sheets = [
        {
            "name": "说明",
            "headers": ["项目", "内容"],
            "rows": build_notes_rows(stage_payload, file_summaries),
        },
        {
            "name": "关联总览",
            "headers": ["TXT文件", "Sheet", "关联级别", "映射行数", "精确名称行", "别名行", "尾行数", "说明"],
            "rows": build_overview_rows(file_summaries),
        },
        {
            "name": "general",
            "headers": analysis_headers(general_rows[0]),
            "rows": general_analysis,
        },
        {
            "name": "castle",
            "headers": analysis_headers(castle_rows[0]),
            "rows": castle_analysis,
        },
        {
            "name": "magic",
            "headers": analysis_headers(magic_rows[0]),
            "rows": magic_analysis,
        },
        {
            "name": "soldier",
            "headers": analysis_headers(soldier_rows[0]),
            "rows": soldier_analysis,
        },
        {
            "name": "general_tail",
            "headers": ["__txt_row_number", "__trailer_reason", "__candidate_title", "__candidate_family", *general_rows[0]],
            "rows": general_trailer,
        },
        {
            "name": "castle_tail",
            "headers": ["__txt_row_number", "__trailer_reason", "__candidate_title", "__candidate_family", *castle_rows[0]],
            "rows": castle_trailer,
        },
        {
            "name": "soldier_tail",
            "headers": ["__txt_row_number", "__trailer_reason", "__candidate_title", "__candidate_family", *soldier_rows[0]],
            "rows": soldier_trailer,
        },
        {
            "name": "history",
            "headers": ["__txt_row_number", "StageINI标题", "__matched_general_record", *history_rows[0]],
            "rows": history_linked,
        },
    ]

    conversion_workbook_sheets = [
        {
            "name": "general",
            "headers": conversion_headers(general_rows[0]),
            "rows": general_conversion,
        },
        {
            "name": "castle",
            "headers": conversion_headers(castle_rows[0]),
            "rows": castle_conversion,
        },
        {
            "name": "magic",
            "headers": conversion_headers(magic_rows[0]),
            "rows": magic_conversion,
        },
        {
            "name": "soldier",
            "headers": conversion_headers(soldier_rows[0]),
            "rows": soldier_conversion,
        },
    ]

    conversion_models = {
        "general": general_model,
        "castle": castle_model,
        "magic": magic_model,
        "soldier": soldier_model,
    }

    unlinked_files = []
    for path in sorted(txt_dir.glob("*.txt")):
        if path.name in {"general.txt", "castle.txt", "magic.txt", "soldier.txt", "History.txt"}:
            continue
        unlinked_files.append({"file": path.name, "relation": "none", "notes": "当前未发现与 stage.ini 的直接数值流映射。"})

    return {
        "stage_ini_path": stage_payload["stage_ini_path"],
        "header": stage_payload["header"],
        "file_summaries": file_summaries,
        "unlinked_files": unlinked_files,
        "analysis_workbook_sheets": analysis_workbook_sheets,
        "conversion_workbook_sheets": conversion_workbook_sheets,
        "conversion_models": conversion_models,
        "workbook_sheets": analysis_workbook_sheets,
    }


def export_bundle(root: Path) -> Path:
    output_dir = ensure_output_dir(root)
    payload = build_bundle(root)
    out_path = output_dir / "stage_ini_txt_links.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def normalize_row_for_compare(row: list[object]) -> list[object]:
    normalized: list[object] = []
    for value in row:
        if value is None:
            normalized.append("")
        else:
            normalized.append(value)
    return normalized


def patch_stream_values(
    record_buffers: dict[int, bytearray],
    *,
    dwords_per_record: int,
    start_dword: int,
    numeric_values: list[int],
) -> None:
    for offset, value in enumerate(numeric_values):
        global_dword_index = start_dword + offset
        record_index = global_dword_index // dwords_per_record
        dword_index = global_dword_index % dwords_per_record
        buffer = record_buffers[record_index]
        byte_offset = dword_index * 4
        buffer[byte_offset : byte_offset + 4] = int(value).to_bytes(4, "little", signed=False)


def apply_workbook_tables_to_stage_ini(root: Path, workbook_tables: dict[str, dict[str, object]]) -> dict[str, object]:
    resolved_root = root.resolve()
    payload = stage_ini_codec.build_payload(resolved_root)
    reference_bundle = build_bundle(resolved_root)
    conversion_models = reference_bundle["conversion_models"]

    reference_rows: dict[str, dict[int, list[object]]] = {}
    for sheet in reference_bundle["conversion_workbook_sheets"]:
        row_map: dict[int, list[object]] = {}
        for row in sheet["rows"]:
            row_map[int(row[0])] = list(row)
        reference_rows[str(sheet["name"])] = row_map

    main_records = payload["tables"]["main_records"]
    tail_records = payload["tables"]["tail_records"]
    main_buffers = {int(row["record_index"]): bytearray(record_blob(row)) for row in main_records}
    tail_buffers = {int(row["record_index"]): bytearray(record_blob(row)) for row in tail_records}
    touched_main: set[int] = set()
    touched_tail: set[int] = set()
    main_dwords_per_record = int(payload["header"]["main_stride"]) // 4
    tail_dwords_per_record = int(payload["header"]["tail_stride"]) // 4

    for sheet_name in DIRECT_SHEETS:
        if sheet_name not in workbook_tables:
            continue
        workbook_sheet = workbook_tables[sheet_name]
        headers = [str(value) for value in workbook_sheet["headers"]]
        rows = workbook_sheet["rows"]
        if headers[:2] != ["row_id", "title"]:
            raise ValueError(f"Workbook sheet {sheet_name} does not match pure conversion layout")

        model = conversion_models[sheet_name]
        value_count = len(model["value_headers"])
        row_models = model["row_models"]
        for row in rows:
            row_id = int(parse_int(row[0]) or 0)
            reference_row = reference_rows.get(sheet_name, {}).get(row_id)
            if reference_row is not None and normalize_row_for_compare(list(row)) == normalize_row_for_compare(reference_row):
                continue

            row_model = row_models.get(str(row_id))
            if row_model is None:
                continue

            numeric_values: list[int] = []
            for cell in list(row)[2 : 2 + value_count]:
                parsed = parse_int(cell)
                numeric_values.append(0 if parsed is None else int(parsed))
            numeric_values = numeric_values[: int(row_model["numeric_count"])]

            if str(row_model["stream_section"]) == "main":
                patch_stream_values(
                    main_buffers,
                    dwords_per_record=main_dwords_per_record,
                    start_dword=int(row_model["stream_start_dword"]),
                    numeric_values=numeric_values,
                )
                for record_index in range(int(row_model["record_start"]), int(row_model["record_end"]) + 1):
                    touched_main.add(record_index)
            else:
                patch_stream_values(
                    tail_buffers,
                    dwords_per_record=tail_dwords_per_record,
                    start_dword=int(row_model["stream_start_dword"]),
                    numeric_values=numeric_values,
                )
                for record_index in range(int(row_model["record_start"]), int(row_model["record_end"]) + 1):
                    touched_tail.add(record_index)

    for row in main_records:
        record_index = int(row["record_index"])
        if record_index not in touched_main:
            continue
        rebuilt = bytes(main_buffers[record_index])
        row["raw_hex"] = rebuilt.hex()
        row["u16_words"] = stage_ini_codec.read_u16_words(rebuilt)

    for row in tail_records:
        record_index = int(row["record_index"])
        if record_index not in touched_tail:
            continue
        rebuilt = bytes(tail_buffers[record_index])
        row["raw_hex"] = rebuilt.hex()
        row["u16_words"] = stage_ini_codec.read_u16_words(rebuilt)

    return payload
