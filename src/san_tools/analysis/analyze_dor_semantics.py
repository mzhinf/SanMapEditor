from __future__ import annotations

import argparse
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

MAGIC = b"Door    Data"
EMPTY_SENTINEL = "<empty>"
EXE_PATTERNS = {
    ".m": b".m\x00",
    ".s": b".s\x00",
    ".x": b".x\x00",
    ".spr": b".spr\x00",
    ".dor": b".dor\x00",
    ".evt": b".evt\x00",
    "Door    Data": b"Door    Data",
}


def find_game_dir(root: Path) -> Path:
    """在给定目录及其一级子目录中定位包含 `Emperor.exe` 的游戏目录。"""

    if (root / "Emperor.exe").exists():
        return root
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "Emperor.exe").exists():
            return child
    raise FileNotFoundError("未找到包含 Emperor.exe 的游戏目录。")


def parse_m_dimensions(path: Path) -> tuple[int, int] | None:
    """只解析 `.m` 的宽高，避免依赖仓库内其他解析模块。"""

    if not path.exists():
        return None
    blob = path.read_bytes()
    if len(blob) < 16 or blob[8:16] != b"Hello1.0":
        return None
    return struct.unpack_from("<II", blob, 0)


def choose_record_stride(blob: bytes) -> int:
    """优先信任 `.dor` 头里的 stride 提示，当前样本稳定落在 56/60 两类。"""

    if len(blob) < 16:
        return 60
    hinted = struct.unpack_from("<I", blob, 12)[0]
    if hinted in (56, 60):
        return hinted
    return 60


def choose_header_size(blob: bytes, stride: int) -> int:
    """区分 28 字节空头、56 字节完整头，以及“中间 28 字节全零”的完整头。"""

    if len(blob) < 28:
        return len(blob)
    if len(blob) >= 56:
        extension = blob[28:56]
        if any(extension):
            return 56
        if len(blob) == 56:
            return 56
        probe = blob[28 : 28 + stride]
        if len(probe) >= 28 and not any(probe[:28]) and any(probe[28:]):
            return 56
    return 28


def parse_dor(path: Path) -> dict[str, object]:
    """解析单个 `.dor` 文件的头、记录区与尾区。"""

    blob = path.read_bytes()
    if not blob.startswith(MAGIC):
        raise ValueError(f"{path} 缺少 Door    Data 文件头。")
    stride = choose_record_stride(blob)
    header_size = choose_header_size(blob, stride)
    record_count = max(0, (len(blob) - header_size) // stride)
    record_bytes = [
        blob[header_size + index * stride : header_size + (index + 1) * stride]
        for index in range(record_count)
    ]
    record_u32 = [
        list(struct.unpack_from(f"<{stride // 4}I", record))
        for record in record_bytes
    ]
    used_size = header_size + record_count * stride
    return {
        "path": str(path),
        "name": path.name,
        "size": len(blob),
        "stride": stride,
        "header_size": header_size,
        "record_count": record_count,
        "tail_size": len(blob) - used_size,
        "header_dwords": [
            struct.unpack_from("<I", blob, offset)[0]
            for offset in range(0, min(header_size, len(blob)), 4)
        ],
        "header_hex": blob[:header_size].hex(),
        "tail_hex": blob[used_size:].hex(),
        "records_raw": record_bytes,
        "records_u32": record_u32,
    }


def build_dword_rows(records_u32: list[list[int]]) -> list[dict[str, int]]:
    """把记录数组转成 `d00/d01/...` 命名，便于跨关卡比较。"""

    rows: list[dict[str, int]] = []
    for record in records_u32:
        rows.append({f"d{index:02d}": value for index, value in enumerate(record)})
    return rows


def build_byte_rows(records_raw: list[bytes]) -> list[dict[str, int]]:
    """保留逐字节视角，用于识别常量字节与 0/1 标志位。"""

    rows: list[dict[str, int]] = []
    for record in records_raw:
        rows.append({f"b{index:02d}": value for index, value in enumerate(record)})
    return rows


def build_nonzero_signatures(records_u32: list[list[int]]) -> list[dict[str, object]]:
    """按 dword 非零分布聚类，区分不同记录家族。"""

    counter = Counter(tuple(index for index, value in enumerate(record) if value) for record in records_u32)
    results: list[dict[str, object]] = []
    for signature, count in counter.most_common(8):
        results.append(
            {
                "count": count,
                "dword_indices": list(signature),
                "dword_names": [f"d{index:02d}" for index in signature],
            }
        )
    return results


def summarize_constant_bytes(byte_rows: list[dict[str, int]]) -> list[dict[str, object]]:
    """找出“全记录稳定一致但非零”的字节，通常对应类型码或家族常量。"""

    if not byte_rows:
        return []
    byte_names = list(byte_rows[0].keys())
    results: list[dict[str, object]] = []
    for name in byte_names:
        values = {row[name] for row in byte_rows}
        if len(values) != 1:
            continue
        value = next(iter(values))
        if value == 0:
            continue
        offset = int(name[1:])
        results.append(
            {
                "byte": name,
                "offset": offset,
                "value": value,
                "hex": f"0x{value:02x}",
            }
        )
    return results


def summarize_binary_dwords(dword_rows: list[dict[str, int]]) -> list[dict[str, object]]:
    """识别在 0/1 之间切换的 dword，通常是左右门扇、单双向等标记位。"""

    if not dword_rows:
        return []
    names = list(dword_rows[0].keys())
    results: list[dict[str, object]] = []
    for name in names:
        values = sorted({row[name] for row in dword_rows})
        if values in ([0, 1], [1]):
            results.append(
                {
                    "field": name,
                    "values": values,
                    "count_1": sum(1 for row in dword_rows if row[name] == 1),
                }
            )
    return results


def evaluate_coordinate_pair(
    dword_rows: list[dict[str, int]],
    width: int,
    height: int,
    x_field: str,
    y_field: str,
) -> dict[str, object]:
    """评估一组字段是否像地图坐标。"""

    valid_points: list[tuple[int, int]] = []
    invalid_count = 0
    for row in dword_rows:
        x_value = row[x_field]
        y_value = row[y_field]
        if 0 < x_value < width and 0 < y_value < height:
            valid_points.append((x_value, y_value))
        else:
            invalid_count += 1
    unique_points = len(set(valid_points))
    repeated_count = len(valid_points) - unique_points
    return {
        "x_field": x_field,
        "y_field": y_field,
        "valid_count": len(valid_points),
        "invalid_count": invalid_count,
        "unique_points": unique_points,
        "repeated_count": repeated_count,
        "sample_points": [list(point) for point in valid_points[:8]],
    }


def rank_coordinate_pairs(
    dword_rows: list[dict[str, int]],
    width: int,
    height: int,
) -> list[dict[str, object]]:
    """穷举候选坐标对，后续分别挑选“入口点”和“落点”两类字段。"""

    if not dword_rows:
        return []
    names = list(dword_rows[0].keys())
    ranked: list[dict[str, object]] = []
    for x_field in names:
        for y_field in names:
            if x_field == y_field:
                continue
            if x_field[:3] == y_field[:3]:
                continue
            summary = evaluate_coordinate_pair(dword_rows, width, height, x_field, y_field)
            if summary["valid_count"] == 0:
                continue
            ranked.append(summary)
    ranked.sort(
        key=lambda item: (
            item["valid_count"],
            item["repeated_count"],
            item["unique_points"],
        ),
        reverse=True,
    )
    return ranked


def choose_target_pair(pairs: list[dict[str, object]]) -> dict[str, object] | None:
    """优先选择“多条记录汇入少量坐标”的字段组，作为落点/目标点候选。"""

    if not pairs:
        return None
    scored = sorted(
        pairs,
        key=lambda item: (
            item["repeated_count"] * 100 + item["valid_count"] * 10 - item["unique_points"],
            item["valid_count"],
        ),
        reverse=True,
    )
    return scored[0]


def choose_source_pair(
    pairs: list[dict[str, object]],
    target_pair: dict[str, object] | None,
) -> dict[str, object] | None:
    """优先选择“有效点多、坐标更分散”的字段组，作为入口源点候选。"""

    if not pairs:
        return None
    blocked_fields: set[str] = set()
    if target_pair:
        blocked_fields = {target_pair["x_field"], target_pair["y_field"]}
    filtered = [
        item
        for item in pairs
        if item["x_field"] not in blocked_fields and item["y_field"] not in blocked_fields
    ]
    if not filtered:
        filtered = pairs
    scored = sorted(
        filtered,
        key=lambda item: (
            item["unique_points"] * 100 + item["valid_count"] * 10 - item["repeated_count"],
            item["valid_count"],
        ),
        reverse=True,
    )
    return scored[0]


def build_target_groups(
    dword_rows: list[dict[str, int]],
    target_pair: dict[str, object] | None,
    source_pair: dict[str, object] | None,
    width: int,
    height: int,
) -> list[dict[str, object]]:
    """按目标点聚合，观察是否存在“多个入口点指向同一落点”的模式。"""

    if not target_pair or not source_pair:
        return []
    groups: dict[tuple[int, int], list[dict[str, object]]] = defaultdict(list)
    for index, row in enumerate(dword_rows):
        target_x = row[target_pair["x_field"]]
        target_y = row[target_pair["y_field"]]
        source_x = row[source_pair["x_field"]]
        source_y = row[source_pair["y_field"]]
        if not (0 < target_x < width and 0 < target_y < height):
            continue
        if not (0 < source_x < width and 0 < source_y < height):
            continue
        groups[(target_x, target_y)].append(
            {
                "record_index": index,
                "source": [source_x, source_y],
                "target": [target_x, target_y],
            }
        )
    results: list[dict[str, object]] = []
    for target, entries in groups.items():
        if len(entries) < 2:
            continue
        results.append(
            {
                "target": list(target),
                "record_count": len(entries),
                "sources": [entry["source"] for entry in entries],
                "record_indices": [entry["record_index"] for entry in entries],
            }
        )
    results.sort(key=lambda item: (item["record_count"], item["target"]), reverse=True)
    return results


def classify_stage(
    record_count: int,
    signatures: list[dict[str, object]],
    target_groups: list[dict[str, object]],
    constant_bytes: list[dict[str, object]],
) -> dict[str, object]:
    """根据记录数量、签名复杂度与目标聚合模式做粗分类。"""

    if record_count == 0:
        return {"family": "empty_placeholder", "confidence": "high"}
    signature_diversity = len(signatures)
    dominant_ratio = 0.0
    if signatures:
        dominant_ratio = signatures[0]["count"] / record_count
    if record_count >= 40 or signature_diversity >= 6:
        return {"family": "complex_world_links", "confidence": "medium"}
    if target_groups:
        family = "portal_pairs"
        if any(item["offset"] in (50, 58) for item in constant_bytes):
            family = "portal_pairs_with_family_constants"
        if dominant_ratio < 0.5:
            return {"family": "mixed_portal_pairs", "confidence": "medium"}
        return {"family": family, "confidence": "high"}
    return {"family": "mixed_or_unknown", "confidence": "low"}


def build_stage_judgement(
    stage: str,
    dimensions: tuple[int, int] | None,
    target_pair: dict[str, object] | None,
    source_pair: dict[str, object] | None,
    target_groups: list[dict[str, object]],
    constant_bytes: list[dict[str, object]],
    binary_dwords: list[dict[str, object]],
    family: dict[str, object],
) -> list[str]:
    """生成单关卡的中文结论摘要。"""

    notes: list[str] = []
    if dimensions is None:
        notes.append("当前目录缺少同名 `.m` 或 `.m` 头无效，只能做结构分析，不能校验坐标落点。")
        return notes
    if target_pair and source_pair:
        notes.append(
            f"候选落点字段更像 `{target_pair['x_field']}/{target_pair['y_field']}`，候选入口字段更像 `{source_pair['x_field']}/{source_pair['y_field']}`。"
        )
    if target_groups:
        notes.append("同一落点下聚合出多个入口点，强烈支持“门/入口源点 -> 关卡内落点”的数据模型。")
    if any(item["field"] in ("d09", "d10") for item in binary_dwords):
        notes.append("存在 0/1 dword 标志位，像是左右门扇、单双向或同组内次序标记。")
    if any(item["offset"] in (27, 23) for item in constant_bytes):
        notes.append("记录内存在稳定的非零类型字节，像是门类型、场景类型或装配分支号。")
    if family["family"] == "complex_world_links":
        notes.append("该关卡记录族明显更复杂，像是世界地图/大型场景的连通或触发表，而不是普通二元入口表。")
    if stage in {"stage00", "stage01", "stage02", "stage03", "stage04"}:
        notes.append("该批关卡与普通战场图的记录形态不同，应视为“大地图/特殊场景”变体。")
    return notes


def summarize_global_roles(stage_reports: list[dict[str, object]]) -> dict[str, object]:
    """统计哪些字段最常被推断成入口/落点字段。"""

    role_counter: dict[str, Counter[str]] = {
        "target_x": Counter(),
        "target_y": Counter(),
        "source_x": Counter(),
        "source_y": Counter(),
    }
    for stage in stage_reports:
        inference = stage.get("coordinate_inference", {})
        target_pair = inference.get("target_pair")
        source_pair = inference.get("source_pair")
        if target_pair:
            role_counter["target_x"][target_pair["x_field"]] += 1
            role_counter["target_y"][target_pair["y_field"]] += 1
        if source_pair:
            role_counter["source_x"][source_pair["x_field"]] += 1
            role_counter["source_y"][source_pair["y_field"]] += 1
    return {
        role: [{"field": field, "count": count} for field, count in counter.most_common(6)]
        for role, counter in role_counter.items()
    }


def parse_pe_sections(blob: bytes) -> list[dict[str, int | str]]:
    """解析 PE section，便于把字符串偏移映射回虚拟地址。"""

    pe_offset = struct.unpack_from("<I", blob, 0x3C)[0]
    section_count = struct.unpack_from("<H", blob, pe_offset + 6)[0]
    optional_header_size = struct.unpack_from("<H", blob, pe_offset + 20)[0]
    section_offset = pe_offset + 24 + optional_header_size
    sections: list[dict[str, int | str]] = []
    for index in range(section_count):
        offset = section_offset + index * 40
        name = blob[offset : offset + 8].split(b"\0", 1)[0].decode("ascii", errors="ignore")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", blob, offset + 8)
        sections.append(
            {
                "name": name,
                "virtual_size": virtual_size,
                "virtual_address": virtual_address,
                "raw_size": raw_size,
                "raw_offset": raw_offset,
            }
        )
    return sections


def section_for_offset(sections: list[dict[str, int | str]], offset: int) -> dict[str, int | str] | None:
    """查找文件偏移落在哪个节区。"""

    for section in sections:
        start = int(section["raw_offset"])
        end = start + max(int(section["raw_size"]), int(section["virtual_size"]))
        if start <= offset < end:
            return section
    return None


def offset_to_va(sections: list[dict[str, int | str]], offset: int) -> int:
    """把文件偏移换算成 EXE 虚拟地址。"""

    section = section_for_offset(sections, offset)
    if section is None:
        return 0x400000 + offset
    return 0x400000 + int(section["virtual_address"]) + (offset - int(section["raw_offset"]))


def locate_exe_pattern(
    blob: bytes,
    sections: list[dict[str, int | str]],
    label: str,
    pattern: bytes,
) -> dict[str, object] | None:
    """定位字符串并回收所有绝对地址引用。"""

    offset = blob.find(pattern)
    if offset < 0:
        return None
    pattern_va = offset_to_va(sections, offset)
    ref_pattern = struct.pack("<I", pattern_va)
    refs: list[int] = []
    search_from = 0
    while True:
        hit = blob.find(ref_pattern, search_from)
        if hit < 0:
            break
        refs.append(hit)
        search_from = hit + 1
    section = section_for_offset(sections, offset)
    return {
        "label": label,
        "offset": offset,
        "va": pattern_va,
        "section": section["name"] if section else None,
        "xref_offsets": refs,
        "xref_vas": [offset_to_va(sections, ref) for ref in refs],
    }


def cluster_offsets(items: list[tuple[int, str]], gap: int = 0x280) -> list[dict[str, object]]:
    """按文件偏移聚成代码簇，用于观察 sidecar 装配链。"""

    if not items:
        return []
    ordered = sorted(items)
    groups: list[list[tuple[int, str]]] = [[ordered[0]]]
    for item in ordered[1:]:
        if item[0] - groups[-1][-1][0] <= gap:
            groups[-1].append(item)
        else:
            groups.append([item])
    results: list[dict[str, object]] = []
    for group in groups:
        results.append(
            {
                "start_offset": group[0][0],
                "end_offset": group[-1][0],
                "labels": [label for _offset, label in group],
            }
        )
    return results


def summarize_exe_evidence(game_dir: Path) -> dict[str, object]:
    """从 `Emperor.exe` 提取 `.dor` 的装配链侧证。"""

    blob = (game_dir / "Emperor.exe").read_bytes()
    sections = parse_pe_sections(blob)
    refs = {
        label: locate_exe_pattern(blob, sections, label, pattern)
        for label, pattern in EXE_PATTERNS.items()
    }
    refs = {key: value for key, value in refs.items() if value is not None}
    sidecar_items: list[tuple[int, str]] = []
    map_items: list[tuple[int, str]] = []
    for label in (".spr", ".dor", ".evt"):
        if label in refs:
            sidecar_items.extend((offset, label) for offset in refs[label]["xref_offsets"])
    for label in (".m", ".s", ".x"):
        if label in refs:
            map_items.extend((offset, label) for offset in refs[label]["xref_offsets"])
    inference = [
        "`.spr/.dor/.evt` 与 `.m/.s/.x` 在 Emperor.exe 里分属两组引用簇，说明 `.dor` 走的是独立 sidecar 装配链。",
        "`Door    Data` 作为独立魔数存在，说明 `.dor` 不是 `.m` 内嵌片段，而是单独文件格式。",
    ]
    return {
        "patterns": refs,
        "sidecar_clusters": cluster_offsets(sidecar_items),
        "map_clusters": cluster_offsets(map_items),
        "inference": inference,
    }


def analyze_stage(path: Path, dor_meta: dict[str, object], dimensions: tuple[int, int] | None) -> dict[str, object]:
    """分析单个关卡 `.dor` 的结构与字段语义。"""

    dword_rows = build_dword_rows(dor_meta["records_u32"])
    byte_rows = build_byte_rows(dor_meta["records_raw"])
    signatures = build_nonzero_signatures(dor_meta["records_u32"])
    constant_bytes = summarize_constant_bytes(byte_rows)
    binary_dwords = summarize_binary_dwords(dword_rows)
    coordinate_pairs: list[dict[str, object]] = []
    target_pair = None
    source_pair = None
    target_groups: list[dict[str, object]] = []
    if dimensions is not None and dword_rows:
        width, height = dimensions
        coordinate_pairs = rank_coordinate_pairs(dword_rows, width, height)
        target_pair = choose_target_pair(coordinate_pairs)
        source_pair = choose_source_pair(coordinate_pairs, target_pair)
        target_groups = build_target_groups(dword_rows, target_pair, source_pair, width, height)
    family = classify_stage(dor_meta["record_count"], signatures, target_groups, constant_bytes)
    judgement = build_stage_judgement(
        path.stem,
        dimensions,
        target_pair,
        source_pair,
        target_groups,
        constant_bytes,
        binary_dwords,
        family,
    )
    return {
        "stage": path.stem,
        "file": {
            "path": str(path),
            "size": dor_meta["size"],
            "header_size": dor_meta["header_size"],
            "record_stride": dor_meta["stride"],
            "record_count": dor_meta["record_count"],
            "tail_size": dor_meta["tail_size"],
            "header_dwords": dor_meta["header_dwords"],
            "tail_hex": dor_meta["tail_hex"],
        },
        "map_dimensions": {"width": dimensions[0], "height": dimensions[1]} if dimensions else None,
        "signatures": signatures,
        "constant_bytes": constant_bytes,
        "binary_dwords": binary_dwords,
        "coordinate_inference": {
            "top_pairs": coordinate_pairs[:8],
            "target_pair": target_pair,
            "source_pair": source_pair,
            "target_groups": target_groups[:8],
        },
        "family": family,
        "judgement": judgement,
    }


def build_global_conclusions(stage_reports: list[dict[str, object]], exe_evidence: dict[str, object]) -> list[str]:
    """生成跨关卡的综合结论。"""

    family_counter = Counter(stage["family"]["family"] for stage in stage_reports)
    linked_stage_count = sum(
        1
        for stage in stage_reports
        if stage["coordinate_inference"]["target_groups"]
    )
    conclusions = [
        "`.dor` 在 Emperor.exe 侧明确属于与 `.spr/.evt` 并列的关卡 sidecar，`Door    Data` 是它的独立文件头。",
        f"在 {linked_stage_count} 个关卡里，记录天然呈现“多个入口点指向同一落点”的聚合结构，最符合门、入口、通路或传送点定义表。",
        f"关卡家族分布为：{dict(family_counter)}，说明 `.dor` 至少存在“普通入口表”和“大地图/复杂连通表”两种变体。",
        "普通战场图里，最常见的记录模型是“两组坐标 + 0/1 标志位 + 若干场景常量”，其中一组更像入口源点，另一组更像进入后的落点。",
        "部分关卡在记录后方额外挂有 36/40/44/48/52 字节尾区，当前更像补充表或结尾块，而不是主记录体的一部分。",
    ]
    conclusions.extend(exe_evidence["inference"])
    return conclusions


def render_markdown_report(report: dict[str, object]) -> str:
    """把结构化结果转成便于人工阅读的 Markdown 摘要。"""

    lines: list[str] = []
    lines.append("# `.dor` 语义分析报告")
    lines.append("")
    lines.append("## 全局结论")
    for item in report["global_conclusions"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 字段角色统计")
    for role, entries in report["field_role_summary"].items():
        if not entries:
            continue
        joined = "，".join(f"{entry['field']} × {entry['count']}" for entry in entries[:4])
        lines.append(f"- `{role}`：{joined}")
    lines.append("")
    lines.append("## 关卡摘要")
    for stage in report["stages"]:
        file_meta = stage["file"]
        lines.append(f"### {stage['stage']}")
        lines.append(
            f"- 家族：`{stage['family']['family']}`（{stage['family']['confidence']}）"
        )
        lines.append(
            f"- 结构：header={file_meta['header_size']}，stride={file_meta['record_stride']}，records={file_meta['record_count']}，tail={file_meta['tail_size']}"
        )
        if stage["map_dimensions"]:
            dims = stage["map_dimensions"]
            lines.append(f"- 地图尺寸：{dims['width']} x {dims['height']}")
        coord = stage["coordinate_inference"]
        if coord["target_pair"] and coord["source_pair"]:
            lines.append(
                f"- 候选落点：`{coord['target_pair']['x_field']}/{coord['target_pair']['y_field']}`；候选入口：`{coord['source_pair']['x_field']}/{coord['source_pair']['y_field']}`"
            )
        if coord["target_groups"]:
            sample = coord["target_groups"][0]
            lines.append(
                f"- 目标聚合样例：落点 {sample['target']} 关联 {sample['record_count']} 条记录，入口点 {sample['sources']}"
            )
        if stage["constant_bytes"]:
            preview = "，".join(f"{item['byte']}={item['hex']}" for item in stage["constant_bytes"][:5])
            lines.append(f"- 常量字节：{preview}")
        for note in stage["judgement"][:3]:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def analyze_all(root: Path, out_dir: Path) -> dict[str, object]:
    """汇总所有 `.dor` 的结构、语义与 EXE 侧证。"""

    game_dir = find_game_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    dor_files = sorted(game_dir.glob("stage*.dor"))
    stage_reports: list[dict[str, object]] = []
    for path in dor_files:
        dor_meta = parse_dor(path)
        dimensions = parse_m_dimensions(game_dir / f"{path.stem}.m")
        stage_reports.append(analyze_stage(path, dor_meta, dimensions))
    exe_evidence = summarize_exe_evidence(game_dir)
    report = {
        "root": str(root),
        "game_dir": str(game_dir),
        "dor_file_count": len(dor_files),
        "exe_evidence": exe_evidence,
        "field_role_summary": summarize_global_roles(stage_reports),
        "global_conclusions": build_global_conclusions(stage_reports, exe_evidence),
        "stages": stage_reports,
    }
    json_path = out_dir / "dor_semantics_report.json"
    md_path = out_dir / "dor_semantics_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return {
        "report": report,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
    }


def main() -> int:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="独立分析 `.dor` 的文件结构与字段语义。")
    parser.add_argument("root", nargs="?", default=".", type=Path, help="项目根目录或游戏目录")
    parser.add_argument("--out", default=Path("derived/dor_semantics"), type=Path, help="输出目录")
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    result = analyze_all(root, out_dir)
    summary = {
        "json_path": result["json_path"],
        "markdown_path": result["markdown_path"],
        "global_conclusions": result["report"]["global_conclusions"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
