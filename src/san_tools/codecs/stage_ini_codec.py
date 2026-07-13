from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import san_tools.analysis.analyze_stage_sidecars as sidecars
import san_tools.analysis.analyze_stg_family_alignment as align

# 以下常量仅描述旧工作簿兼容视图，不代表 stage.ini 的物理块边界。
MAIN_HEADER_SIZE = 8
TAIL_STRIDE = 76


def find_stage_ini(root: Path) -> Path:
    candidates = list(root.glob("stage.ini")) + list(root.glob("*/stage.ini"))
    if not candidates:
        raise FileNotFoundError(f"Could not find stage.ini under {root}")
    return candidates[0]


def read_u16_words(blob: bytes) -> list[int]:
    return [int.from_bytes(blob[index : index + 2], "little") for index in range(0, len(blob), 2)]


def read_u32_dwords(blob: bytes) -> list[int]:
    return [int.from_bytes(blob[index : index + 4], "little") for index in range(0, len(blob), 4)]


def _read_size_block(blob: bytes, offset: int, label: str) -> tuple[dict[str, int], int]:
    """读取一个 `u32 size + payload` 块，并返回可用于精确回写的边界。"""

    if offset < 0 or offset + 4 > len(blob):
        raise ValueError(f"stage.ini {label} 缺少块长度字段：offset={offset}")
    size = int.from_bytes(blob[offset : offset + 4], "little")
    payload_offset = offset + 4
    end_offset = payload_offset + size
    if end_offset > len(blob):
        raise ValueError(
            f"stage.ini {label} 块越界：offset={offset}, size={size}, file_size={len(blob)}"
        )
    return {
        "size_offset": offset,
        "size": size,
        "payload_offset": payload_offset,
        "end_offset": end_offset,
    }, end_offset


def parse_stage_ini_block_layout(blob: bytes) -> dict[str, object]:
    """按游戏实际块流解析武将主表与城池双块记录的物理边界。"""

    if len(blob) < 4:
        raise ValueError("stage.ini 长度不足，缺少主表计数")

    main_count = int.from_bytes(blob[0:4], "little")
    offset = 4
    main_blocks: list[dict[str, int]] = []
    for index in range(main_count):
        block, offset = _read_size_block(blob, offset, f"主表[{index}]")
        main_blocks.append(block)

    city_count_offset = offset
    if city_count_offset + 4 > len(blob):
        raise ValueError("stage.ini 缺少城池计数")
    city_count = int.from_bytes(blob[city_count_offset : city_count_offset + 4], "little")
    offset += 4

    city_records: list[dict[str, object]] = []
    for index in range(city_count):
        primary, offset = _read_size_block(blob, offset, f"城池[{index}].primary")
        secondary, offset = _read_size_block(blob, offset, f"城池[{index}].secondary")
        city_records.append({"record_index": index, "primary": primary, "secondary": secondary})

    return {
        "format": "stage-ini-block-stream-v1",
        "main_count_offset": 0,
        "main_count": main_count,
        "main_blocks": main_blocks,
        "main_blocks_end": city_count_offset,
        "city_count_offset": city_count_offset,
        "city_count": city_count,
        "city_records": city_records,
        "city_records_end": offset,
        "remaining_offset": offset,
        "file_size": len(blob),
    }


def decode_zero_terminated_strings(blob: bytes) -> list[str]:
    strings: list[str] = []
    current = bytearray()
    for byte in blob:
        if byte == 0:
            if len(current) >= 2:
                text = decode_string_bytes(bytes(current))
                if text:
                    strings.append(text)
            current = bytearray()
        else:
            current.append(byte)
    if len(current) >= 2:
        text = decode_string_bytes(bytes(current))
        if text:
            strings.append(text)
    return strings


def decode_string_bytes(blob: bytes) -> str:
    for encoding in ("cp950", "cp936", "utf-8"):
        try:
            text = blob.decode(encoding)
        except UnicodeDecodeError:
            continue
        stripped = text.strip()
        if stripped:
            return stripped
    return ""


def summarize_nonzero_words(words: list[int], limit: int = 18) -> str:
    parts: list[str] = []
    for index, value in enumerate(words):
        if value:
            parts.append(f"w{index:02d}={value}")
    return ", ".join(parts[:limit])


def join_layout(items: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for item in items:
        parts.append(f"{int(item['offset'])}:{str(item['text'])}")
    return " | ".join(parts)


def normalize_tail_family_words(family_guess: str, words: list[int]) -> tuple[str, list[int]] | None:
    family_key = family_guess
    if family_key == "city_92_family":
        family_key = "city_or_structure"
    config = align.FAMILY_CONFIGS.get(family_key)
    if config is None:
        return None
    normalized = align.normalize_family_words(
        words,
        anchor_value=config["anchor_value"],
        anchor_index=config["anchor_index"],
    )
    if normalized is None:
        return None
    rotated, _anchor = normalized
    return family_key, rotated


def guess_main_family(strings: list[str]) -> str:
    if not strings:
        return "main_unknown"
    if len(strings) >= 2 and "將" in strings[1]:
        return "general_master"
    if strings[0] in {"女武神", "白吉勝", "田恩沛", "黃柏文"}:
        return "special_character"
    return "main_named_record"


def parse_main_records(blob: bytes, count: int, stride: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for record_index in range(count):
        start = MAIN_HEADER_SIZE + record_index * stride
        record = blob[start : start + stride]
        words = read_u16_words(record)
        dwords = read_u32_dwords(record)
        strings = decode_zero_terminated_strings(record)
        family_guess = guess_main_family(strings)
        row: dict[str, object] = {
            "section": "main",
            "record_index": record_index,
            "record_id_candidate": record_index + 1,
            "family_guess": family_guess,
            "name": strings[0] if strings else "",
            "label": strings[1] if len(strings) >= 2 else "",
            "strings_joined": " | ".join(strings),
            "text_count": len(strings),
            "nonzero_words": summarize_nonzero_words(words, limit=24),
            "raw_hex": record.hex(),
            "u16_words": words,
            "u32_dwords_preview": dwords[:24],
        }
        for index, value in enumerate(words):
            row[f"w{index:03d}"] = value
        rows.append(row)
    return rows


def parse_tail_records(blob: bytes, tail_offset: int) -> list[dict[str, object]]:
    tail_blob = blob[tail_offset:]
    count = len(tail_blob) // TAIL_STRIDE
    tail_blob = tail_blob[: count * TAIL_STRIDE]
    rows: list[dict[str, object]] = []
    for record_index in range(count):
        start = tail_offset + record_index * TAIL_STRIDE
        record = blob[start : start + TAIL_STRIDE]
        texts = sidecars.extract_text_segments(record, limit=8, max_bytes=24)
        words = sidecars.read_u16_words(record)
        strings = [str(item["text"]) for item in texts]
        family_guess = sidecars.guess_stg_family(record_index, strings, words)
        row: dict[str, object] = {
            "section": "tail",
            "record_index": record_index,
            "file_offset": start,
            "family_guess": family_guess,
            "name": strings[0] if strings else "",
            "label": strings[1] if len(strings) >= 2 else "",
            "text_layout": join_layout(texts),
            "strings_joined": " | ".join(strings),
            "text_count": len(strings),
            "nonzero_words": summarize_nonzero_words(words, limit=20),
            "raw_hex": record.hex(),
            "u16_words": words,
        }
        for index, value in enumerate(words):
            row[f"w{index:02d}"] = value

        normalized = normalize_tail_family_words(family_guess, words)
        if normalized is not None:
            normalized_family, rotated = normalized
            row["normalized_family"] = normalized_family
            row["normalized_nonzero_words"] = summarize_nonzero_words(rotated, limit=20)
            for index, value in enumerate(rotated):
                row[f"nw{index:02d}"] = value
        else:
            row["normalized_family"] = ""
            row["normalized_nonzero_words"] = ""
        rows.append(row)
    return rows


def build_payload(root: Path) -> dict[str, object]:
    stage_ini_path = find_stage_ini(root.resolve())
    blob = stage_ini_path.read_bytes()
    block_layout = parse_stage_ini_block_layout(blob)
    main_count = int.from_bytes(blob[0:4], "little")
    main_stride = int.from_bytes(blob[4:8], "little")
    tail_offset = MAIN_HEADER_SIZE + main_count * main_stride
    main_records = parse_main_records(blob, main_count, main_stride)
    tail_records = parse_tail_records(blob, tail_offset)
    tail_records_end = tail_offset + len(tail_records) * TAIL_STRIDE
    tail_remainder = blob[tail_records_end:]

    tail_family_counter = Counter(str(row["family_guess"]) for row in tail_records)
    main_family_counter = Counter(str(row["family_guess"]) for row in main_records)

    general_master = [
        {
            "record_index": row["record_index"],
            "record_id_candidate": row["record_id_candidate"],
            "name": row["name"],
            "label": row["label"],
            "family_guess": row["family_guess"],
            "nonzero_words": row["nonzero_words"],
        }
        for row in main_records
        if row["name"]
    ]

    city_master = [
        {
            "record_index": row["record_index"],
            "name": row["name"],
            "label": row["label"],
            "family_guess": row["family_guess"],
            "normalized_family": row["normalized_family"],
            "normalized_nonzero_words": row["normalized_nonzero_words"],
            "place_id_candidate_stage_ini": row.get("nw16", 0),
            "small_field_a_candidate": row.get("nw20", 0),
            "small_field_b_candidate": row.get("nw22", 0),
            "value_a_candidate": row.get("nw24", 0),
            "value_b_candidate": row.get("nw26", 0),
            "value_c_candidate": row.get("nw30", 0),
            "value_d_candidate": row.get("nw32", 0),
        }
        for row in tail_records
        if str(row["family_guess"]) in {"city_or_structure", "city_92_family"} and row["name"]
    ]

    troop_master = [
        {
            "record_index": row["record_index"],
            "name": row["name"],
            "label": row["label"],
            "family_guess": row["family_guess"],
            "normalized_family": row["normalized_family"],
            "normalized_nonzero_words": row["normalized_nonzero_words"],
            "code_a_candidate": row.get("nw12", 0),
            "code_b_candidate": row.get("nw14", 0),
            "field_w24_candidate": row.get("nw24", 0),
            "field_w26_candidate": row.get("nw26", 0),
            "field_w36_candidate": row.get("nw36", 0),
        }
        for row in tail_records
        if str(row["family_guess"]) == "troop_entry" and row["name"]
    ]

    notes = [
        {
            "主题": "用途",
            "内容": "把 stage.ini 拆成可读主表与尾表，并保留逐记录 raw_hex/u16_words，后续既能看表，也能在 JSON 上做可逆回写。",
        },
        {
            "主题": "主表",
            "内容": "物理格式以 main_count 开始，随后是 u32 size + payload 主块；普通武将使用 size=224，除标题和 49 个字段外还包含两个能力镜像。",
        },
        {
            "主题": "尾表",
            "内容": "主块之后先保存 city_count；每座城池由 size=92 主块和 size=0 次块组成，后续还混有兵种、山寨/盗贼、技能/文本字典等全局资源。",
        },
        {
            "主题": "当前印证",
            "内容": "尾表中的城市名与 .stg 已识别城市 id 空间能多点对上，例如 鄴=7、譙=18、宛=20。主表中的武将顺序也与 .stg/.evt 武将 id 空间高度相关。",
        },
        {
            "主题": "回写策略",
            "内容": "旧工作簿仍按 224/76 字节兼容视图展示；raw_hex、u16_words 与不足 76 字节的尾部余数共同保证 byte-for-byte round-trip。新增对象必须按真实 size 块流写入。",
        },
    ]

    return {
        "stage_ini_path": str(stage_ini_path),
        "header": {
            "main_count": main_count,
            "main_stride": main_stride,
            "tail_offset": tail_offset,
            "tail_stride": TAIL_STRIDE,
            "tail_count": len(tail_records),
            "tail_remainder_size": len(tail_remainder),
            "file_size": len(blob),
        },
        "notes": notes,
        "block_layout": block_layout,
        "tail_remainder_hex": tail_remainder.hex(),
        "tables": {
            "main_family_totals": [
                {"family_guess": family_name, "count": count}
                for family_name, count in main_family_counter.most_common()
            ],
            "tail_family_totals": [
                {"family_guess": family_name, "count": count}
                for family_name, count in tail_family_counter.most_common()
            ],
            "general_master": general_master,
            "city_master": city_master,
            "troop_master": troop_master,
            "main_records": main_records,
            "tail_records": tail_records,
        },
    }


def record_bytes_from_row(row: dict[str, object], expected_size: int) -> bytes:
    raw_hex = str(row.get("raw_hex", ""))
    if raw_hex:
        blob = bytes.fromhex(raw_hex)
        if len(blob) != expected_size:
            raise ValueError(f"Record {row.get('record_index')} raw_hex has size {len(blob)} != {expected_size}")
        return blob

    words = row.get("u16_words")
    if not isinstance(words, list):
        raise ValueError(f"Record {row.get('record_index')} has neither raw_hex nor u16_words")
    blob = b"".join(int(value).to_bytes(2, "little", signed=False) for value in words)
    if len(blob) != expected_size:
        raise ValueError(f"Record {row.get('record_index')} packed size {len(blob)} != {expected_size}")
    return blob


def rebuild_stage_ini(payload: dict[str, object]) -> bytes:
    header = payload["header"]
    main_count = int(header["main_count"])
    main_stride = int(header["main_stride"])
    tail_stride = int(header["tail_stride"])

    main_records = payload["tables"]["main_records"]
    tail_records = payload["tables"]["tail_records"]

    if len(main_records) != main_count:
        raise ValueError(f"main record count mismatch: payload has {len(main_records)} rows, header says {main_count}")

    main_blob = b"".join(record_bytes_from_row(row, main_stride) for row in main_records)
    tail_blob = b"".join(record_bytes_from_row(row, tail_stride) for row in tail_records)
    tail_remainder = bytes.fromhex(str(payload.get("tail_remainder_hex", "")))
    if len(tail_remainder) != int(header.get("tail_remainder_size", len(tail_remainder))):
        raise ValueError("tail remainder size mismatch")
    return (
        int(main_count).to_bytes(4, "little")
        + int(main_stride).to_bytes(4, "little")
        + main_blob
        + tail_blob
        + tail_remainder
    )


def payload_to_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
