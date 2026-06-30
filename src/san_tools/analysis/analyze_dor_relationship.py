from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from analyze_stage_sidecars import find_game_dir, parse_m, summarize_exe_strings
except ImportError:
    from san_tools.analysis.analyze_stage_sidecars import find_game_dir, parse_m, summarize_exe_strings

try:
    from extract_kingdom import DEFAULT_PALETTE_SOURCE, load_palette
except ImportError:
    from san_tools.map.extract_kingdom import DEFAULT_PALETTE_SOURCE, load_palette

try:
    from render_m_cel_map import canvas_size, cell_xy, parse_counted_cel, render_stage
except ImportError:
    from san_tools.map.render_m_cel_map import canvas_size, cell_xy, parse_counted_cel, render_stage

COLOR_PALETTE = ['#ef4444', '#0f766e', '#2563eb', '#d97706', '#7c3aed', '#db2777']


def guess_dor_header_size(blob: bytes) -> int:
    """根据头部是否存在扩展元数据，猜测 `.dor` 的有效头长。"""

    if len(blob) <= 32:
        return min(28, len(blob))
    if len(blob) >= 56 and any(blob[28:56]):
        return 56
    return 28


def parse_dor_records(path: Path) -> dict[str, object]:
    """按当前最稳的启发式拆出 `.dor` 头、记录区和尾区。"""

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
    tail_offset = header_size + record_count * record_stride
    records = [
        struct.unpack_from('<15I', blob, header_size + index * record_stride)
        for index in range(record_count)
    ]
    return {
        'header_size': header_size,
        'hinted_stride': hinted_stride,
        'record_stride': record_stride,
        'record_count': record_count,
        'tail_size': len(blob) - tail_offset,
        'header_dwords': [struct.unpack_from('<I', blob, offset)[0] for offset in range(0, min(header_size, len(blob)), 4)],
        'tail_hex_preview': blob[tail_offset:tail_offset + 32].hex(),
        'records': records,
    }


def expand_record_fields(record: tuple[int, ...]) -> dict[str, int]:
    """把 15 个 dword 展开成 low/high 16 位字段。"""

    fields: dict[str, int] = {}
    for index, value in enumerate(record):
        fields[f'd{index:02d}_lo'] = value & 0xFFFF
        fields[f'd{index:02d}_hi'] = value >> 16
    return fields


def summarize_field_stats(expanded_records: list[dict[str, int]]) -> list[dict[str, object]]:
    """统计每个候选字段的非零数量与取值分布。"""

    if not expanded_records:
        return []
    names = list(expanded_records[0])
    stats: list[dict[str, object]] = []
    for name in names:
        values = [record[name] for record in expanded_records]
        nonzero = [value for value in values if value > 0]
        stats.append({
            'field': name,
            'nonzero_count': len(nonzero),
            'unique_nonzero': len(set(nonzero)),
            'min_nonzero': min(nonzero) if nonzero else None,
            'max_nonzero': max(nonzero) if nonzero else None,
            'sample_nonzero': sorted(set(nonzero))[:8],
        })
    stats.sort(key=lambda item: (item['nonzero_count'], item['unique_nonzero']), reverse=True)
    return stats


def summarize_record_signatures(records: list[tuple[int, ...]]) -> list[dict[str, object]]:
    """按 dword 非零分布聚类，便于观察记录家族。"""

    counter = Counter(tuple(index for index, value in enumerate(record) if value) for record in records)
    rows: list[dict[str, object]] = []
    for signature, count in counter.most_common(8):
        rows.append({'count': count, 'nonzero_dwords': list(signature)})
    return rows


def collect_valid_points(expanded_records: list[dict[str, int]], x_field: str, y_field: str, width: int, height: int) -> list[tuple[int, int]]:
    """收集落在 `.m` cell 范围内的非零候选坐标。"""

    points: list[tuple[int, int]] = []
    for record in expanded_records:
        x_value = record[x_field]
        y_value = record[y_field]
        if 0 < x_value < width and 0 < y_value < height:
            points.append((x_value, y_value))
    return points


def rank_candidate_pairs(expanded_records: list[dict[str, int]], width: int, height: int, limit: int) -> list[dict[str, object]]:
    """用启发式筛出最像 `.m` 坐标对的字段组合。"""

    if not expanded_records:
        return []
    names = list(expanded_records[0])
    ranked: list[tuple[tuple[int, int, int, int], dict[str, object]]] = []
    for x_field in names:
        for y_field in names:
            if x_field == y_field:
                continue
            if x_field[:3] == y_field[:3]:
                continue
            points = collect_valid_points(expanded_records, x_field, y_field, width, height)
            if len(points) < 3:
                continue
            unique_points = len(set(points))
            unique_x = len({x_value for x_value, _ in points})
            unique_y = len({y_value for _, y_value in points})
            if unique_points < 3 or unique_x < 3 or unique_y < 3:
                continue
            ranked.append((
                (len(points), unique_points, unique_x + unique_y, min(unique_x, unique_y)),
                {
                    'x_field': x_field,
                    'y_field': y_field,
                    'point_count': len(points),
                    'unique_points': unique_points,
                    'unique_x': unique_x,
                    'unique_y': unique_y,
                    'sample_points': [list(point) for point in points[:10]],
                    'points': points,
                },
            ))
    ranked.sort(key=lambda item: item[0], reverse=True)

    selected: list[dict[str, object]] = []
    used_pairs: set[tuple[str, str]] = set()
    for _score, entry in ranked:
        pair_key = tuple(sorted((entry['x_field'], entry['y_field'])))
        if pair_key in used_pairs:
            continue
        used_pairs.add(pair_key)
        selected.append(entry)
        if len(selected) >= limit:
            break
    return selected


def project_points(points: list[tuple[int, int]], layout: str, origin_x: int, origin_y: int) -> list[tuple[int, int]]:
    """把候选 cell 坐标投影到地图渲染画布。"""

    screen_points: list[tuple[int, int]] = []
    for cell_x, cell_y in points:
        pixel_x, pixel_y = cell_xy(cell_x, cell_y, layout, origin_x, origin_y)
        screen_points.append((pixel_x + 20, pixel_y + 10))
    return screen_points


def render_overlay_images(base_map_path: Path, overlay_dir: Path, layout: str, origin_x: int, origin_y: int, pairs: list[dict[str, object]]) -> list[dict[str, object]]:
    """输出候选坐标对的总览图与分层叠加图。"""

    overlay_dir.mkdir(parents=True, exist_ok=True)
    base_image = Image.open(base_map_path).convert('RGBA')
    combined = base_image.copy()
    combined_draw = ImageDraw.Draw(combined)
    outputs: list[dict[str, object]] = []

    for index, pair in enumerate(pairs, start=1):
        color = COLOR_PALETTE[(index - 1) % len(COLOR_PALETTE)]
        overlay = base_image.copy()
        draw = ImageDraw.Draw(overlay)
        screen_points = project_points(pair['points'], layout, origin_x, origin_y)
        for point_x, point_y in screen_points:
            draw.ellipse((point_x - 4, point_y - 4, point_x + 4, point_y + 4), outline=color, width=2)
            combined_draw.ellipse((point_x - 3, point_y - 3, point_x + 3, point_y + 3), outline=color, width=2)
        draw.rectangle((8, 8, 340, 40), fill=(255, 255, 255, 220))
        draw.text((16, 16), f'#{index} {pair["x_field"]} / {pair["y_field"]} ({pair["point_count"]} 点)', fill=color)
        overlay_path = overlay_dir / f'pair_{index:02d}_{pair["x_field"]}_{pair["y_field"]}.png'
        overlay.save(overlay_path)
        outputs.append({
            'rank': index,
            'color': color,
            'overlay': str(overlay_path),
            'x_field': pair['x_field'],
            'y_field': pair['y_field'],
            'point_count': pair['point_count'],
            'unique_points': pair['unique_points'],
            'sample_points': pair['sample_points'],
        })

    legend_height = 18 * max(1, len(outputs)) + 18
    combined_draw.rectangle((8, 8, 420, 8 + legend_height), fill=(255, 255, 255, 200))
    for index, entry in enumerate(outputs, start=1):
        combined_draw.text((16, 12 + (index - 1) * 18), f'#{index} {entry["x_field"]}/{entry["y_field"]}', fill=entry['color'])
    combined_path = overlay_dir / 'dor_candidates.png'
    combined.save(combined_path)
    return outputs + [{'rank': 0, 'color': 'mixed', 'overlay': str(combined_path), 'x_field': 'combined', 'y_field': 'combined', 'point_count': sum(entry['point_count'] for entry in outputs), 'unique_points': None, 'sample_points': []}]


def analyze_dor_relationship(
    root: Path,
    stage: str,
    out_dir: Path,
    layout: str,
    layers: str,
    palette_source: str,
    top_pairs: int,
) -> dict[str, object]:
    """分析 `.dor` 与 `.m` 的潜在坐标关系，并导出可视化结果。"""

    game_dir = find_game_dir(root)
    stage_dir = out_dir / stage
    stage_dir.mkdir(parents=True, exist_ok=True)

    stage_path = game_dir / f'{stage}.m'
    dor_path = game_dir / f'{stage}.dor'
    width, height, _ = parse_m(stage_path)
    dor_meta = parse_dor_records(dor_path)
    expanded_records = [expand_record_fields(record) for record in dor_meta['records']]
    field_stats = summarize_field_stats(expanded_records)
    candidate_pairs = rank_candidate_pairs(expanded_records, width, height, top_pairs)

    palette = load_palette(game_dir, palette_source)
    blocks = parse_counted_cel(game_dir / 'kingdom.cel')
    base_map_path = stage_dir / 'dor_base_map.png'
    render_meta = render_stage(stage_path, blocks, palette, base_map_path, layout, layers, None)
    _, _, origin_x, origin_y = canvas_size(width, height, layout)

    overlays = render_overlay_images(base_map_path, stage_dir / 'overlays', layout, origin_x, origin_y, candidate_pairs)
    exe_clues = summarize_exe_strings(game_dir).get('.dor')

    report = {
        'stage': stage,
        'm_dimensions': {'width': width, 'height': height},
        'dor_path': str(dor_path),
        'dor_layout': {
            'header_size': dor_meta['header_size'],
            'hinted_stride': dor_meta['hinted_stride'],
            'record_stride': dor_meta['record_stride'],
            'record_count': dor_meta['record_count'],
            'tail_size': dor_meta['tail_size'],
            'header_dwords': dor_meta['header_dwords'],
            'tail_hex_preview': dor_meta['tail_hex_preview'],
        },
        'exe_clue': exe_clues,
        'record_signatures': summarize_record_signatures(dor_meta['records']),
        'field_stats_top': field_stats[:12],
        'candidate_pairs': [
            {
                'rank': index + 1,
                'x_field': pair['x_field'],
                'y_field': pair['y_field'],
                'point_count': pair['point_count'],
                'unique_points': pair['unique_points'],
                'unique_x': pair['unique_x'],
                'unique_y': pair['unique_y'],
                'sample_points': pair['sample_points'],
            }
            for index, pair in enumerate(candidate_pairs)
        ],
        'visualization': {
            'base_map': str(base_map_path),
            'overlays': overlays,
            'projection_assumption': '当前把候选字段当作 `.m` 的 cell 坐标，并按编辑器/Emperor 已确认的 stagger 网格投影到地图画布。',
            'confidence': 'exploratory',
        },
        'inference': [
            '`.dor` 至少已经稳定暴露出 `Door    Data` 魔数，且 Emperor.exe 的文件名字符串把 `.evt/.dor/.spr` 放在同一组关卡 sidecar 读取路径里。',
            '当前可视化只证明“某些 `.dor` 字段组合能落入 `.m` 的地图格坐标空间”，还不能直接把它们命名成门、入口或触发器字段。',
        ],
    }
    report_path = stage_dir / 'dor_relationship.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report['report'] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='分析 `.dor` 与 `.m` 的关系，并导出候选坐标覆盖图。')
    parser.add_argument('root', nargs='?', default='.', type=Path, help='项目根目录')
    parser.add_argument('--stage', default='stage01', help='要分析的关卡名，例如 stage01')
    parser.add_argument('--out', default=Path('derived/dor_relationship'), type=Path, help='输出目录')
    parser.add_argument('--layout', choices=['rect', 'iso', 'skew', 'stagger'], default='stagger', help='底图渲染布局')
    parser.add_argument('--layers', default='xyz', help='底图渲染层，默认 xyz')
    parser.add_argument('--palette', default=DEFAULT_PALETTE_SOURCE, help='底图渲染使用的调色板来源')
    parser.add_argument('--top-pairs', type=int, default=6, help='最多导出多少组候选坐标对')
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    result = analyze_dor_relationship(root, args.stage, out_dir, args.layout, args.layers, args.palette, args.top_pairs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())