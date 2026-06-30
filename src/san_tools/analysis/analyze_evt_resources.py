from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

from san_tools.analysis.analyze_stage_sidecars import (
    extract_ascii_tokens,
    extract_text_segments,
    find_game_dir,
    guess_record_family,
    read_u16_words,
)
from san_tools.codecs.scenario_text_codec import (
    classify_text_blob,
    decode_game_text_bytes,
    find_case_insensitive_file,
    parse_loose_script_blocks,
    parse_numbered_sections,
)

INTERESTING_ASCII_TOKENS = {"talk", "VIEW", "MAP", "MAPALL", "MOVE", "OPEN", "TIME", "TIMEOVER"}
GENERIC_EVT_LABELS = {
    "新增流程",
    "流程",
    "新增",
    "新增事件",
    "事件",
    "增事件",
    "公告",
    "佈告",
    "提升",
    "說",
    "件",
    "串12",
    "y程",
    "W流程",
    "GV單獨",
    "屬性",
}


def list_stage_stems(game_dir: Path) -> list[str]:
    """列出拥有 `.evt` 的关卡编号。"""

    return sorted(path.stem for path in game_dir.glob("stage*.evt"))


def load_text_resource(path: Path | None) -> dict[str, object] | None:
    """读取候选文本资源，并判断它是编号表、松散脚本还是二进制。"""

    if path is None or not path.exists():
        return None
    data = path.read_bytes()
    classification = classify_text_blob(data)
    payload: dict[str, object] = {
        "name": path.name,
        "path": str(path),
        **classification,
    }
    if not bool(classification["likely_text"]):
        payload["kind"] = "binary_blob"
        return payload
    text = decode_game_text_bytes(data)
    numbered_sections = parse_numbered_sections(text)
    if numbered_sections:
        payload["kind"] = "numbered_sections"
        payload["section_count"] = len(numbered_sections)
        payload["sections"] = numbered_sections
        return payload
    loose_blocks = parse_loose_script_blocks(text)
    payload["kind"] = "loose_blocks"
    payload["block_count"] = len(loose_blocks)
    payload["blocks"] = loose_blocks
    return payload


def normalize_match_text(text: str) -> str:
    """做一个轻量归一化，便于用短标签找资源文本。"""

    return "".join(char for char in text if not char.isspace())


def is_specific_label(text: str) -> bool:
    """过滤掉明显的框架标签和误解码碎片，只保留较可信的线索。"""

    if text in GENERIC_EVT_LABELS:
        return False
    if len(text.strip()) < 2:
        return False
    if text.isascii() and text not in INTERESTING_ASCII_TOKENS:
        return False
    if any(token in text for token in ("y程", "W流程", "GV單獨")):
        return False
    return True


def find_label_hits(label: str, talk_resource: dict[str, object] | None, stage_resource: dict[str, object] | None) -> list[dict[str, object]]:
    """把 `.evt` 中的标签与 `TalkNN.txt / stageNN.txt` 做文本命中比对。"""

    hits: list[dict[str, object]] = []
    target = normalize_match_text(label)
    if not target:
        return hits
    if talk_resource and talk_resource.get("kind") == "numbered_sections":
        for section in talk_resource.get("sections", []):
            header = str(section.get("header", ""))
            body = str(section.get("text", ""))
            joined = normalize_match_text(header + body)
            if target and target in joined:
                hits.append(
                    {
                        "resource": talk_resource["name"],
                        "kind": "talk_section",
                        "id": int(section["id"]),
                        "header": header,
                    }
                )
            if len(hits) >= 6:
                return hits
    if stage_resource and stage_resource.get("kind") == "loose_blocks":
        for index, block in enumerate(stage_resource.get("blocks", [])):
            speaker = str(block.get("speaker", ""))
            body = str(block.get("text", ""))
            joined = normalize_match_text(speaker + body)
            if target and target in joined:
                hits.append(
                    {
                        "resource": stage_resource["name"],
                        "kind": "stage_block",
                        "block_index": index,
                        "speaker": speaker,
                    }
                )
            if len(hits) >= 6:
                return hits
    return hits


def build_stage_report(game_dir: Path, stem: str) -> dict[str, object]:
    """构建单个关卡 `.evt` 与脚本文本资源的交叉报告。"""

    evt_path = game_dir / f"{stem}.evt"
    blob = evt_path.read_bytes()
    header_dwords = [struct.unpack_from("<I", blob, offset)[0] for offset in range(0, min(8, len(blob)), 4)]
    header = 8
    stride = 72
    record_count = max(0, (len(blob) - header) // stride)

    digits = "".join(char for char in stem if char.isdigit())
    talk_resource = load_text_resource(find_case_insensitive_file(game_dir, f"talk{digits}.txt"))
    stage_resource = load_text_resource(find_case_insensitive_file(game_dir, f"{stem}.txt"))
    talk_ids = set()
    if talk_resource and talk_resource.get("kind") == "numbered_sections":
        talk_ids = {int(section["id"]) for section in talk_resource.get("sections", [])}

    interesting_records: list[dict[str, object]] = []
    command_counter: Counter[str] = Counter()
    label_counter: Counter[str] = Counter()
    talk_reference_counter: Counter[int] = Counter()

    for record_index in range(record_count):
        record = blob[header + record_index * stride : header + (record_index + 1) * stride]
        texts = extract_text_segments(record, limit=6, max_bytes=24)
        ascii_tokens = extract_ascii_tokens(record, limit=8)
        interesting_ascii = [token for token in ascii_tokens if token in INTERESTING_ASCII_TOKENS]
        words = read_u16_words(record)
        decoded_texts = [str(item["text"]) for item in texts]
        specific_labels = [text for text in decoded_texts if is_specific_label(text)]
        candidate_small_ids = sorted({value for value in words if 0 < value <= 512})
        matching_talk_ids = [value for value in candidate_small_ids if value in talk_ids]
        if not interesting_ascii and not specific_labels and not matching_talk_ids:
            continue
        label_hits: list[dict[str, object]] = []
        for label in specific_labels:
            label_counter[label] += 1
            label_hits.extend(find_label_hits(label, talk_resource, stage_resource))
        for token in interesting_ascii:
            command_counter[token] += 1
        for value in matching_talk_ids:
            talk_reference_counter[value] += 1
        family_guess = guess_record_family("evt", record_index, decoded_texts, words, interesting_ascii)
        interesting_records.append(
            {
                "record_index": record_index,
                "family_guess": family_guess,
                "ascii_tokens": interesting_ascii,
                "decoded_texts": decoded_texts,
                "specific_labels": specific_labels,
                "candidate_small_ids": candidate_small_ids,
                "matching_talk_ids": matching_talk_ids,
                "u16_head": words[:16],
                "label_hits": label_hits[:6],
            }
        )

    return {
        "stage": stem,
        "evt_path": str(evt_path),
        "header_dwords": header_dwords,
        "record_stride": stride,
        "record_count": record_count,
        "talk_resource": talk_resource,
        "stage_resource": stage_resource,
        "interesting_record_count": len(interesting_records),
        "command_counts": dict(command_counter.most_common()),
        "label_counts": dict(label_counter.most_common(20)),
        "talk_reference_counts": dict(sorted(talk_reference_counter.items())),
        "interesting_records": interesting_records,
    }


def build_report(root: Path, stages: list[str] | None = None) -> dict[str, object]:
    """生成 `.evt` 与外部文本资源的总体报告。"""

    game_dir = find_game_dir(root.resolve())
    selected_stages = stages or list_stage_stems(game_dir)
    stage_reports = [build_stage_report(game_dir, stem) for stem in selected_stages]
    aggregate_commands: Counter[str] = Counter()
    textual_talk_count = 0
    textual_stage_count = 0
    binary_stage_txt_count = 0
    for item in stage_reports:
        aggregate_commands.update(item.get("command_counts", {}))
        talk_resource = item.get("talk_resource")
        stage_resource = item.get("stage_resource")
        if talk_resource and talk_resource.get("kind") == "numbered_sections":
            textual_talk_count += 1
        if stage_resource and stage_resource.get("kind") == "loose_blocks":
            textual_stage_count += 1
        if stage_resource and stage_resource.get("kind") == "binary_blob":
            binary_stage_txt_count += 1
    return {
        "game_dir": str(game_dir),
        "stage_count": len(stage_reports),
        "summary": {
            "aggregate_command_counts": dict(aggregate_commands.most_common()),
            "textual_talk_file_count": textual_talk_count,
            "textual_stage_txt_count": textual_stage_count,
            "binary_stage_txt_count": binary_stage_txt_count,
        },
        "stages": stage_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="分析 `.evt` 与 `TalkNN.txt / stageNN.txt` 的资源关联。")
    parser.add_argument("root", nargs="?", default=".", type=Path, help="工作区根目录")
    parser.add_argument("--stage", action="append", dest="stages", help="指定关卡，例如 stage17")
    parser.add_argument("--out", default=Path("derived/sidecar_analysis/evt_resource_linkage.json"), type=Path, help="输出 JSON 路径")
    parser.add_argument("--indent", type=int, default=2, help="JSON 缩进")
    args = parser.parse_args()

    payload = build_report(args.root, args.stages)
    out_path = args.out if args.out.is_absolute() else args.root.resolve() / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=args.indent), encoding="utf-8")
    print(json.dumps({
        "out": str(out_path),
        "stage_count": payload["stage_count"],
        "summary": payload["summary"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
