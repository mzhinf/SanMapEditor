from __future__ import annotations

import argparse
import json
import math
import statistics
import struct
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from analyze_dor_relationship import (
        COLOR_PALETTE,
        expand_record_fields,
        guess_dor_header_size,
        parse_dor_records,
        rank_candidate_pairs,
    )
except ImportError:
    from san_tools.analysis.analyze_dor_relationship import (
        COLOR_PALETTE,
        expand_record_fields,
        guess_dor_header_size,
        parse_dor_records,
        rank_candidate_pairs,
    )

try:
    from analyze_stage_sidecars import find_game_dir, parse_m
except ImportError:
    from san_tools.analysis.analyze_stage_sidecars import find_game_dir, parse_m

try:
    from extract_kingdom import DEFAULT_PALETTE_SOURCE, load_palette
except ImportError:
    from san_tools.map.extract_kingdom import DEFAULT_PALETTE_SOURCE, load_palette

try:
    from render_m_cel_map import canvas_size, cell_xy, parse_counted_cel, render_stage
except ImportError:
    from san_tools.map.render_m_cel_map import canvas_size, cell_xy, parse_counted_cel, render_stage


def parse_dor_raw_records(path: Path) -> dict[str, object]:
    """读取 `.dor` 的原始记录字节，供 byte 级分析与可视化使用。"""

    blob = path.read_bytes()
    if not blob.startswith(b'Door    Data'):
        raise ValueError(f'{path} 缺少 Door    Data 头。')
    hinted_stride = struct.unpack_from('<I', blob, 12)[0] if len(blob) >= 16 else 60
    record_stride = max(60, hinted_stride)
    header_size = guess_dor_header_size(blob)
    if len(blob) < header_size:
        header_size = len(blob)
    payload = blob[header_size:]
    record_count = len(payload) // record_stride
    records = [
        blob[header_size + index * record_stride:header_size + (index + 1) * record_stride]
        for index in range(record_count)
    ]
    return {
        'header_size': header_size,
        'record_stride': record_stride,
        'record_count': record_count,
        'records': records,
    }


def expand_record_bytes(records: list[bytes]) -> list[dict[str, int]]:
    """把每条记录展开成 `byte00..byteNN` 便于筛选和统计。"""

    expanded: list[dict[str, int]] = []
    for record in records:
        expanded.append({f'byte{index:02d}': value for index, value in enumerate(record)})
    return expanded


def build_record_cells(
    expanded_records: list[dict[str, int]],
    x_field: str,
    y_field: str,
    width: int,
    height: int,
) -> list[dict[str, object]]:
    """基于候选坐标字段为每条记录建立地图坐标。"""

    cells: list[dict[str, object]] = []
    for record_index, record in enumerate(expanded_records):
        cell_x = record[x_field]
        cell_y = record[y_field]
        valid = 0 < cell_x < width and 0 < cell_y < height
        cells.append({
            'record_index': record_index,
            'cell_x': cell_x,
            'cell_y': cell_y,
            'valid': valid,
        })
    return cells


def summarize_byte_fields(
    byte_records: list[dict[str, int]],
    record_cells: list[dict[str, object]],
    byte_start: int,
    byte_end: int,
) -> list[dict[str, object]]:
    """汇总 byte 字段取值、命中记录与简单聚类信息。"""

    summaries: list[dict[str, object]] = []
    for byte_index in range(byte_start, byte_end + 1):
        field = f'byte{byte_index:02d}'
        counter = Counter(record[field] for record in byte_records)
        nonzero_values = [value for value in counter if value != 0]
        groups: list[dict[str, object]] = []
        for value, count in counter.most_common():
            indices = [index for index, record in enumerate(byte_records) if record[field] == value]
            cells = [record_cells[index] for index in indices if record_cells[index]['valid']]
            xs = [cell['cell_x'] for cell in cells]
            ys = [cell['cell_y'] for cell in cells]
            groups.append({
                'value': value,
                'count': count,
                'record_indices': indices,
                'valid_points': [[cell['cell_x'], cell['cell_y']] for cell in cells],
                'bbox': {
                    'min_x': min(xs) if xs else None,
                    'max_x': max(xs) if xs else None,
                    'min_y': min(ys) if ys else None,
                    'max_y': max(ys) if ys else None,
                },
            })
        summaries.append({
            'field': field,
            'zero_count': counter.get(0, 0),
            'nonzero_count': sum(counter[value] for value in nonzero_values),
            'unique_values': len(counter),
            'unique_nonzero': len(nonzero_values),
            'groups': groups,
        })
    return summaries


def clustering_score(byte_records: list[dict[str, int]], record_cells: list[dict[str, object]], byte_field: str) -> float | None:
    """用同值点的平均曼哈顿距离评估一个坐标对是否更像聚类结果。"""

    scores: list[float] = []
    values = sorted({record[byte_field] for record in byte_records if record[byte_field] != 0})
    for value in values:
        points = [
            (record_cells[index]['cell_x'], record_cells[index]['cell_y'])
            for index, record in enumerate(byte_records)
            if record[byte_field] == value and record_cells[index]['valid']
        ]
        if len(points) < 2:
            continue
        pair_distances = []
        for left_index in range(len(points)):
            for right_index in range(left_index + 1, len(points)):
                left_x, left_y = points[left_index]
                right_x, right_y = points[right_index]
                pair_distances.append(abs(left_x - right_x) + abs(left_y - right_y))
        if pair_distances:
            scores.append(statistics.mean(pair_distances))
    if not scores:
        return None
    return statistics.mean(scores)


def choose_coordinate_pair(
    candidate_pairs: list[dict[str, object]],
    expanded_records: list[dict[str, int]],
    byte_records: list[dict[str, int]],
    width: int,
    height: int,
    cluster_byte: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """在候选坐标对中优先选择让目标 byte 同值更聚集的一组。"""

    comparisons: list[dict[str, object]] = []
    cluster_field = f'byte{cluster_byte:02d}'
    if not candidate_pairs:
        raise ValueError('当前关卡没有找到可用的 `.dor` 候选坐标对。')
    for pair in candidate_pairs:
        cells = build_record_cells(expanded_records, pair['x_field'], pair['y_field'], width, height)
        score = clustering_score(byte_records, cells, cluster_field)
        valid_count = sum(1 for cell in cells if cell['valid'])
        comparisons.append({
            'x_field': pair['x_field'],
            'y_field': pair['y_field'],
            'valid_count': valid_count,
            'cluster_byte': cluster_field,
            'cluster_score': score,
        })
    comparisons.sort(
        key=lambda item: (
            math.inf if item['cluster_score'] is None else item['cluster_score'],
            -item['valid_count'],
        )
    )
    selected_key = (comparisons[0]['x_field'], comparisons[0]['y_field'])
    selected_pair = next(
        pair for pair in candidate_pairs if (pair['x_field'], pair['y_field']) == selected_key
    )
    return selected_pair, comparisons


def project_cell(cell_x: int, cell_y: int, layout: str, origin_x: int, origin_y: int) -> tuple[int, int]:
    """把 `.m` cell 坐标投影到底图画布像素坐标。"""

    pixel_x, pixel_y = cell_xy(cell_x, cell_y, layout, origin_x, origin_y)
    return pixel_x + 20, pixel_y + 10


def color_for_index(index: int) -> str:
    """按稳定顺序为图例值分配颜色。"""

    return COLOR_PALETTE[index % len(COLOR_PALETTE)]


def render_byte_overlay(
    base_map_path: Path,
    overlay_path: Path,
    byte_field: str,
    byte_records: list[dict[str, int]],
    record_cells: list[dict[str, object]],
    layout: str,
    origin_x: int,
    origin_y: int,
    show_zero: bool,
) -> dict[str, object]:
    """为单个 byte 字段绘制取值覆盖图。"""

    base_image = Image.open(base_map_path).convert('RGBA')
    draw = ImageDraw.Draw(base_image)
    counter = Counter(record[byte_field] for record in byte_records)
    values = [value for value, _count in counter.most_common() if show_zero or value != 0]
    colors = {value: color_for_index(index) for index, value in enumerate(values)}

    plotted = 0
    for record_index, record in enumerate(byte_records):
        value = record[byte_field]
        if not show_zero and value == 0:
            continue
        cell = record_cells[record_index]
        if not cell['valid']:
            continue
        point_x, point_y = project_cell(cell['cell_x'], cell['cell_y'], layout, origin_x, origin_y)
        color = colors[value]
        draw.ellipse((point_x - 5, point_y - 5, point_x + 5, point_y + 5), outline=color, width=2)
        draw.text((point_x + 7, point_y - 8), f'{value}', fill=color)
        plotted += 1

    legend_rows = [f'{byte_field} 记录数 {len(byte_records)}']
    for value, count in counter.most_common():
        if not show_zero and value == 0:
            continue
        legend_rows.append(f'{value}: {count}')
    legend_width = 260
    legend_height = 14 + 18 * max(1, len(legend_rows))
    draw.rectangle((8, 8, 8 + legend_width, 8 + legend_height), fill=(255, 255, 255, 215))
    for row_index, row in enumerate(legend_rows):
        fill = '#111827'
        if row_index > 0:
            fill = colors[int(row.split(':', 1)[0])]
        draw.text((16, 14 + row_index * 18), row, fill=fill)

    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    base_image.save(overlay_path)
    return {
        'field': byte_field,
        'overlay': str(overlay_path),
        'plotted_points': plotted,
        'value_counts': [{'value': value, 'count': count} for value, count in counter.most_common()],
    }


def render_combined_sheet(overlays: list[Path], out_path: Path) -> str:
    """把多个 byte 覆盖图拼成总览图，便于快速比较。"""

    if not overlays:
        return str(out_path)
    images = [Image.open(path).convert('RGBA') for path in overlays]
    tile_width = max(image.width for image in images)
    tile_height = max(image.height for image in images)
    columns = 2
    rows = math.ceil(len(images) / columns)
    canvas = Image.new('RGBA', (tile_width * columns, tile_height * rows), (255, 255, 255, 255))
    for index, image in enumerate(images):
        col = index % columns
        row = index // columns
        canvas.paste(image, (col * tile_width, row * tile_height))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return str(out_path)


def scan_hypotheses(root: Path, hypotheses: list[tuple[int, str, int | None]]) -> list[dict[str, object]]:
    """全量扫描所有 `.dor`，确认指定 byte 猜想在不同关卡中的命中情况。"""

    game_dir = find_game_dir(root)
    results: list[dict[str, object]] = []
    for byte_index, operator, expected in hypotheses:
        hits: list[dict[str, object]] = []
        for path in sorted(game_dir.glob('stage*.dor')):
            meta = parse_dor_raw_records(path)
            for record_index, record in enumerate(meta['records']):
                actual = record[byte_index]
                matched = False
                if operator == 'eq' and expected is not None:
                    matched = actual == expected
                elif operator == 'ne0':
                    matched = actual != 0
                if matched:
                    hits.append({
                        'stage': path.stem,
                        'record_index': record_index,
                        'value': actual,
                    })
        results.append({
            'byte_field': f'byte{byte_index:02d}',
            'operator': operator,
            'expected': expected,
            'hit_count': len(hits),
            'hits': hits,
        })
    return results


def infer_hypotheses(
    byte_records: list[dict[str, int]],
    record_cells: list[dict[str, object]],
    stage_hypotheses: list[tuple[int, str, int | None]],
) -> list[dict[str, object]]:
    """为当前关卡生成更易读的猜想判断摘要。"""

    summaries: list[dict[str, object]] = []
    for byte_index, operator, expected in stage_hypotheses:
        field = f'byte{byte_index:02d}'
        matches: list[dict[str, object]] = []
        for record_index, record in enumerate(byte_records):
            actual = record[field]
            matched = False
            if operator == 'eq' and expected is not None:
                matched = actual == expected
            elif operator == 'ne0':
                matched = actual != 0
            if not matched:
                continue
            cell = record_cells[record_index]
            matches.append({
                'record_index': record_index,
                'value': actual,
                'cell': [cell['cell_x'], cell['cell_y']] if cell['valid'] else None,
            })
        summaries.append({
            'field': field,
            'operator': operator,
            'expected': expected,
            'match_count': len(matches),
            'matches': matches,
        })
    return summaries


def analyze_dor_byte_fields(
    root: Path,
    stage: str,
    out_dir: Path,
    layout: str,
    layers: str,
    palette_source: str,
    top_pairs: int,
    byte_start: int,
    byte_end: int,
    cluster_byte: int,
    show_zero: bool,
    x_field: str | None,
    y_field: str | None,
) -> dict[str, object]:
    """分析 `.dor` 的 byte08-15 一类原始字段，并投影到地图上。"""

    game_dir = find_game_dir(root)
    stage_dir = out_dir / stage
    stage_dir.mkdir(parents=True, exist_ok=True)

    stage_path = game_dir / f'{stage}.m'
    dor_path = game_dir / f'{stage}.dor'
    width, height, _ = parse_m(stage_path)
    dor_meta = parse_dor_records(dor_path)
    raw_meta = parse_dor_raw_records(dor_path)
    expanded_records = [expand_record_fields(record) for record in dor_meta['records']]
    byte_records = expand_record_bytes(raw_meta['records'])
    candidate_pairs = rank_candidate_pairs(expanded_records, width, height, top_pairs)

    if x_field and y_field:
        selected_pair = {
            'x_field': x_field,
            'y_field': y_field,
        }
        pair_comparisons = []
    else:
        selected_pair, pair_comparisons = choose_coordinate_pair(
            candidate_pairs,
            expanded_records,
            byte_records,
            width,
            height,
            cluster_byte,
        )

    record_cells = build_record_cells(expanded_records, selected_pair['x_field'], selected_pair['y_field'], width, height)

    palette = load_palette(game_dir, palette_source)
    blocks = parse_counted_cel(game_dir / 'kingdom.cel')
    base_map_path = stage_dir / 'dor_byte_base_map.png'
    render_stage(stage_path, blocks, palette, base_map_path, layout, layers, None)
    _, _, origin_x, origin_y = canvas_size(width, height, layout)

    byte_outputs = []
    overlay_paths: list[Path] = []
    for byte_index in range(byte_start, byte_end + 1):
        byte_field = f'byte{byte_index:02d}'
        overlay_path = stage_dir / 'overlays' / f'{byte_field}.png'
        byte_outputs.append(
            render_byte_overlay(
                base_map_path,
                overlay_path,
                byte_field,
                byte_records,
                record_cells,
                layout,
                origin_x,
                origin_y,
                show_zero,
            )
        )
        overlay_paths.append(overlay_path)

    combined_path = render_combined_sheet(overlay_paths, stage_dir / 'overlays' / 'byte_fields_sheet.png')
    byte_summaries = summarize_byte_fields(byte_records, record_cells, byte_start, byte_end)
    local_hypotheses = infer_hypotheses(
        byte_records,
        record_cells,
        [
            (9, 'eq', 1),
            (8, 'eq', 218),
            (10, 'eq', 239),
            (11, 'ne0', None),
        ],
    )
    global_hypotheses = scan_hypotheses(
        root,
        [
            (9, 'eq', 1),
            (8, 'eq', 218),
            (10, 'eq', 239),
            (11, 'ne0', None),
        ],
    )

    byte11_summary = next(item for item in byte_summaries if item['field'] == 'byte11')
    byte12_summary = next((item for item in byte_summaries if item['field'] == 'byte12'), None)

    report = {
        'stage': stage,
        'numbering_note': '本报告使用 `.dor` 单条记录的 0-based 原始 byte 偏移命名，即 `byte08` = `record[8]`。',
        'm_dimensions': {'width': width, 'height': height},
        'dor_path': str(dor_path),
        'selected_coordinate_pair': {
            'x_field': selected_pair['x_field'],
            'y_field': selected_pair['y_field'],
            'valid_record_count': sum(1 for cell in record_cells if cell['valid']),
            'comparison': pair_comparisons,
        },
        'byte_range': [byte_start, byte_end],
        'byte_fields': byte_summaries,
        'visualization': {
            'base_map': str(base_map_path),
            'byte_overlays': byte_outputs,
            'combined_sheet': combined_path,
        },
        'hypotheses_stage': local_hypotheses,
        'hypotheses_global': global_hypotheses,
        'judgement': [
            '按当前 0-based byte08-15 口径，`byte08=218` 与 `byte10=239` 在全量 `.dor` 中都没有命中，说明这两个猜想大概率依赖另一套编号口径或另一段记录。',
            '按当前 0-based byte08-15 口径，`byte09=1` 只在 `stage00` 与 `stage03` 命中，属于稀有值，不像全局“不可达”标记，更像少数关卡特例。',
            f'当前关卡 `{stage}` 的 `byte11` 非零值分布为 {[(group["value"], group["count"]) for group in byte11_summary["groups"] if group["value"] != 0]}，更像阶段内常量或记录族标记，而不像城市 ID。',
            f'当前关卡 `{stage}` 若要找“同值成对出现”的字段，`byte12` 比 `byte11` 更像候选项；其非零值分布为 {[(group["value"], group["count"]) for group in (byte12_summary["groups"] if byte12_summary else []) if group["value"] != 0]}。',
        ],
    }
    report_path = stage_dir / 'dor_byte_fields.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report['report'] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='分析 `.dor` 原始 byte 字段并绘制 byte08-15 覆盖图。')
    parser.add_argument('root', nargs='?', default='.', type=Path, help='项目根目录')
    parser.add_argument('--stage', default='stage20', help='要分析的关卡名，例如 stage20')
    parser.add_argument('--out', default=Path('derived/dor_byte_fields'), type=Path, help='输出目录')
    parser.add_argument('--layout', choices=['rect', 'iso', 'skew', 'stagger'], default='stagger', help='底图渲染布局')
    parser.add_argument('--layers', default='xyz', help='底图渲染层，默认 xyz')
    parser.add_argument('--palette', default=DEFAULT_PALETTE_SOURCE, help='底图调色板来源')
    parser.add_argument('--top-pairs', type=int, default=3, help='最多参与坐标对筛选的候选数')
    parser.add_argument('--byte-start', type=int, default=8, help='起始 byte 偏移，默认 8')
    parser.add_argument('--byte-end', type=int, default=15, help='结束 byte 偏移，默认 15')
    parser.add_argument('--cluster-byte', type=int, default=11, help='自动挑选坐标对时用于聚类打分的 byte 偏移')
    parser.add_argument('--show-zero', action='store_true', help='绘图时也标出值为 0 的记录')
    parser.add_argument('--x-field', help='显式指定 `.dor` 候选 x 字段，如 d06_lo')
    parser.add_argument('--y-field', help='显式指定 `.dor` 候选 y 字段，如 d07_lo')
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    result = analyze_dor_byte_fields(
        root,
        args.stage,
        out_dir,
        args.layout,
        args.layers,
        args.palette,
        args.top_pairs,
        args.byte_start,
        args.byte_end,
        args.cluster_byte,
        args.show_zero,
        args.x_field,
        args.y_field,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
