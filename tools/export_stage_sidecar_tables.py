from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.analyze_stage_sidecars as sidecars


def list_stage_stems(game_dir: Path) -> list[str]:
    return sorted(path.stem for path in game_dir.glob("stage*.m"))


def join_layout(items: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for item in items:
        offset = int(item.get("offset", 0))
        text = str(item.get("text", ""))
        parts.append(f"{offset}:{text}")
    return " | ".join(parts)


def join_family_layout(items: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for item in items:
        offset = int(item.get("offset", 0))
        kind = str(item.get("kind", ""))
        parts.append(f"{offset}:{kind}")
    return " | ".join(parts)


def summarize_nonzero_words(words: list[int]) -> str:
    parts: list[str] = []
    for index, value in enumerate(words):
        if value:
            parts.append(f"w{index:02d}={value}")
    return ", ".join(parts[:16])


def flatten_record_rows(game_dir: Path, stem: str, suffix: str) -> list[dict[str, object]]:
    path = game_dir / f"{stem}.{suffix}"
    if not path.exists():
        return []
    if suffix == "stg":
        header = 8
        stride = 76
    elif suffix == "evt":
        header = 8
        stride = 72
    else:
        raise ValueError(f"Unsupported suffix: {suffix}")

    blob = path.read_bytes()
    record_count = max(0, (len(blob) - header) // stride)
    rows: list[dict[str, object]] = []
    for record_index in range(record_count):
        start = header + record_index * stride
        record = blob[start : start + stride]
        texts = sidecars.extract_text_segments(record, limit=6, max_bytes=24)
        if not texts:
            continue
        words = sidecars.read_u16_words(record)
        ascii_tokens = sidecars.extract_ascii_tokens(record, limit=8)
        actual_texts = [str(item["text"]) for item in texts]
        family_guess = sidecars.guess_record_family(
            suffix,
            record_index,
            actual_texts,
            words,
            ascii_tokens,
        )
        row: dict[str, object] = {
            "stage": stem,
            "suffix": suffix,
            "record_index": record_index,
            "family_guess": family_guess,
            "text_count": len(texts),
            "text_layout": join_layout(texts),
            "texts_joined": " | ".join(actual_texts),
            "ascii_tokens": " | ".join(ascii_tokens),
            "nonzero_words": summarize_nonzero_words(words),
        }
        for slot in range(4):
            if slot < len(texts):
                row[f"text{slot + 1}_offset"] = int(texts[slot]["offset"])
                row[f"text{slot + 1}"] = str(texts[slot]["text"])
            else:
                row[f"text{slot + 1}_offset"] = None
                row[f"text{slot + 1}"] = ""
        for word_index, value in enumerate(words):
            row[f"w{word_index:02d}"] = value
        rows.append(row)
    return rows


def build_tables(root: Path, stages: list[str] | None = None) -> dict[str, object]:
    game_dir = sidecars.find_game_dir(root.resolve())
    selected_stages = stages or list_stage_stems(game_dir)

    overview_rows: list[dict[str, object]] = []
    family_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []
    string_rows: list[dict[str, object]] = []
    exe_rows: list[dict[str, object]] = []
    record_rows: dict[str, list[dict[str, object]]] = {"stg": [], "evt": []}
    # 记录不同语义家族的字符串偏移命中次数，后续可直接观察“槽位”规律。
    text_slot_counter: defaultdict[tuple[str, str, int], int] = defaultdict(int)

    for stem in selected_stages:
        summary = sidecars.summarize_stage(game_dir, stem)
        stg_summary = summary.get("sidecars", {}).get("stg", {})
        evt_summary = summary.get("sidecars", {}).get("evt", {})
        grids = summary.get("grids", {})
        sx_similarity = grids.get("s_x_similarity", {}) if isinstance(grids, dict) else {}
        overview_rows.append(
            {
                "stage": stem,
                "width": summary["m"]["width"],
                "height": summary["m"]["height"],
                "record_count": summary["m"]["record_count"],
                "stg_title": stg_summary.get("title_cp950", ""),
                "year_start_candidate": stg_summary.get("year_start_candidate"),
                "year_end_candidate": stg_summary.get("year_end_candidate"),
                "has_stg": bool(stg_summary),
                "has_evt": bool(evt_summary),
                "has_s": "s" in grids,
                "has_x": "x" in grids,
                "s_size": grids.get("s", {}).get("size") if isinstance(grids.get("s"), dict) else None,
                "x_size": grids.get("x", {}).get("size") if isinstance(grids.get("x"), dict) else None,
                "s_x_same_ratio": sx_similarity.get("same_ratio"),
                "stg_family_count": len(stg_summary.get("record_family_summaries", [])) if isinstance(stg_summary, dict) else 0,
                "evt_family_count": len(evt_summary.get("record_family_summaries", [])) if isinstance(evt_summary, dict) else 0,
            }
        )

        for suffix, side_summary in (("stg", stg_summary), ("evt", evt_summary)):
            if not isinstance(side_summary, dict):
                continue
            for item in side_summary.get("decoded_strings_preview", []):
                string_rows.append(
                    {
                        "stage": stem,
                        "suffix": suffix,
                        "source": "decoded_strings_preview",
                        "offset": int(item.get("offset", 0)),
                        "text": str(item.get("text", "")),
                    }
                )
            for family_index, family in enumerate(side_summary.get("record_family_summaries", []), start=1):
                family_id = f"{stem}:{suffix}:{family_index}"
                layout_summary = join_family_layout(family.get("layout", []))
                sample_texts = [" / ".join(sample) for sample in family.get("sample_texts", [])]
                family_rows.append(
                    {
                        "family_id": family_id,
                        "stage": stem,
                        "suffix": suffix,
                        "family_guess": str(family.get("family_guess", "")),
                        "count": int(family.get("count", 0)),
                        "layout_summary": layout_summary,
                        "sample_record_indices": ", ".join(str(value) for value in family.get("sample_record_indices", [])),
                        "sample_texts": " || ".join(sample_texts),
                        "ascii_tokens": " | ".join(str(token) for token in family.get("ascii_tokens", [])),
                    }
                )
                for candidate in family.get("candidate_small_u16_fields", []):
                    candidate_rows.append(
                        {
                            "family_id": family_id,
                            "stage": stem,
                            "suffix": suffix,
                            "family_guess": str(family.get("family_guess", "")),
                            "layout_summary": layout_summary,
                            "word_index": int(candidate.get("word_index", 0)),
                            "byte_offset": int(candidate.get("byte_offset", 0)),
                            "nonzero_count": int(candidate.get("nonzero_count", 0)),
                            "lt_stage_width": int(candidate.get("lt_stage_width", 0)),
                            "lt_stage_height": int(candidate.get("lt_stage_height", 0)),
                            "sample_values": ", ".join(str(value) for value in candidate.get("sample_values", [])),
                        }
                    )
            rows = flatten_record_rows(game_dir, stem, suffix)
            record_rows[suffix].extend(rows)
            for row in rows:
                family_guess = str(row["family_guess"])
                for key, value in row.items():
                    if key.endswith("_offset") and value is not None:
                        text_slot_counter[(suffix, family_guess, int(value))] += 1

    for suffix, context in sidecars.summarize_exe_strings(game_dir).items():
        exe_rows.append(
            {
                "suffix": suffix,
                "offset": int(context.get("offset", 0)),
                "va": int(context.get("va", 0)),
                "xref_offsets": ", ".join(str(value) for value in context.get("xref_offsets", [])),
                "ascii": str(context.get("ascii", "")),
            }
        )

    family_total_map: dict[tuple[str, str], dict[str, object]] = {}
    for row in family_rows:
        key = (str(row["suffix"]), str(row["family_guess"]))
        item = family_total_map.setdefault(
            key,
            {
                "suffix": row["suffix"],
                "family_guess": row["family_guess"],
                "total_records": 0,
                "stages": set(),
                "layouts": Counter(),
            },
        )
        item["total_records"] = int(item["total_records"]) + int(row["count"])
        item["stages"].add(str(row["stage"]))
        item["layouts"][str(row["layout_summary"])] += int(row["count"])

    # 汇总每个家族最常出现的候选字段列，便于把研究重点压缩到少数偏移。
    candidate_hits: defaultdict[tuple[str, str], Counter[tuple[int, int]]] = defaultdict(Counter)
    for row in candidate_rows:
        key = (str(row["suffix"]), str(row["family_guess"]))
        candidate_hits[key][(int(row["word_index"]), int(row["byte_offset"]))] += 1

    family_total_rows: list[dict[str, object]] = []
    for key, item in family_total_map.items():
        top_layouts = ", ".join(
            f"{layout} x{count}"
            for layout, count in item["layouts"].most_common(3)
        )
        top_candidates = ", ".join(
            f"w{word_index:02d}@{byte_offset} x{count}"
            for (word_index, byte_offset), count in candidate_hits.get(key, Counter()).most_common(6)
        )
        family_total_rows.append(
            {
                "suffix": item["suffix"],
                "family_guess": item["family_guess"],
                "total_records": item["total_records"],
                "stage_count": len(item["stages"]),
                "stages": ", ".join(sorted(item["stages"])),
                "top_layouts": top_layouts,
                "top_candidate_columns": top_candidates,
            }
        )
    family_total_rows.sort(key=lambda row: (str(row["suffix"]), -int(row["total_records"]), str(row["family_guess"])))

    text_slot_rows = [
        {
            "suffix": suffix,
            "family_guess": family_guess,
            "text_offset": text_offset,
            "hit_count": hit_count,
        }
        for (suffix, family_guess, text_offset), hit_count in sorted(
            text_slot_counter.items(),
            key=lambda item: (item[0][0], item[0][1], -item[1], item[0][2]),
        )
    ]

    note_rows = [
        {
            "主题": "用途",
            "内容": "把当前 .stg/.evt 的文本、记录、家族聚类、候选字段导出成可筛选工作簿，方便继续拆字段。",
        },
        {
            "主题": "当前强结论",
            "内容": ".stg 已明显分成 faction_or_ruler / general_entry / troop_entry / city_or_structure / bandit_entry 等语义家族；.evt 已分成 flow/prompt/objective/name-slot 等脚本家族。",
        },
        {
            "主题": "文本槽位",
            "内容": ".stg 的名称文本经常落在 20 字节步进槽位（如 12/28/48/68），说明同一 76 字节 record 内可能复用多个名字槽；.evt 的流程/条件文本则在多个偏移滑动，像共享命令结构。",
        },
        {
            "主题": "候选字段解释",
            "内容": "candidate_rows 中的 word_index/byte_offset 只是优先排查列：这些列经常落在 stage 宽高范围内，更像坐标、owner id、city slot 或局部索引。",
        },
        {
            "主题": "建议过滤方式",
            "内容": "先按 family_guess 过滤，再观察 text_layout、nonzero_words、w00..w37/35 的联动；若要找坐标，优先看家族总计 sheet 里的 top_candidate_columns。",
        },
    ]

    return {
        "game_dir": str(game_dir),
        "selected_stages": selected_stages,
        "tables": {
            "notes": note_rows,
            "overview": overview_rows,
            "family_totals": family_total_rows,
            "families": family_rows,
            "candidate_fields": candidate_rows,
            "text_slots": text_slot_rows,
            "strings": string_rows,
            "stg_records": record_rows["stg"],
            "evt_records": record_rows["evt"],
            "exe_contexts": exe_rows,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export flattened .stg/.evt sidecar tables for workbook generation.")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", action="append", dest="stages", help="Stage stem such as stage11")
    parser.add_argument("--out-json", type=Path, default=Path("derived/sidecar_analysis/stage_sidecar_tables.json"))
    args = parser.parse_args()

    payload = build_tables(args.root, stages=args.stages)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
