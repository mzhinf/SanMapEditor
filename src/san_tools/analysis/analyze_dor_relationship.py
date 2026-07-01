from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None

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

IMAGE_BASE = 0x400000
COLOR_PALETTE = ['#ef4444', '#0f766e', '#2563eb', '#d97706', '#7c3aed', '#db2777']
EXE_PATTERNS = {
    '.m': b'.m\x00',
    '.s': b'.s\x00',
    '.x': b'.x\x00',
    '.spr': b'.spr\x00',
    '.dor': b'.dor\x00',
    '.evt': b'.evt\x00',
    'Soldier Data': b'Soldier Data',
    'Door    Data': b'Door    Data',
}


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
        'header_dwords': [
            struct.unpack_from('<I', blob, offset)[0]
            for offset in range(0, min(header_size, len(blob)), 4)
        ],
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



def collect_valid_points(
    expanded_records: list[dict[str, int]],
    x_field: str,
    y_field: str,
    width: int,
    height: int,
) -> list[tuple[int, int]]:
    """收集落在 `.m` cell 范围内的非零候选坐标。"""

    points: list[tuple[int, int]] = []
    for record in expanded_records:
        x_value = record[x_field]
        y_value = record[y_field]
        if 0 < x_value < width and 0 < y_value < height:
            points.append((x_value, y_value))
    return points



def rank_candidate_pairs(
    expanded_records: list[dict[str, int]],
    width: int,
    height: int,
    limit: int,
) -> list[dict[str, object]]:
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



def render_overlay_images(
    base_map_path: Path,
    overlay_dir: Path,
    layout: str,
    origin_x: int,
    origin_y: int,
    pairs: list[dict[str, object]],
) -> list[dict[str, object]]:
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
        draw.rectangle((8, 8, 360, 40), fill=(255, 255, 255, 220))
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
    return outputs + [{
        'rank': 0,
        'color': 'mixed',
        'overlay': str(combined_path),
        'x_field': 'combined',
        'y_field': 'combined',
        'point_count': sum(entry['point_count'] for entry in outputs),
        'unique_points': None,
        'sample_points': [],
    }]



def parse_pe_sections(blob: bytes) -> list[dict[str, int | str]]:
    """解析 PE section 表，便于把文件偏移映射回节区和 VA。"""

    pe_offset = struct.unpack_from('<I', blob, 0x3C)[0]
    section_count = struct.unpack_from('<H', blob, pe_offset + 6)[0]
    optional_header_size = struct.unpack_from('<H', blob, pe_offset + 20)[0]
    section_offset = pe_offset + 24 + optional_header_size
    sections: list[dict[str, int | str]] = []
    for index in range(section_count):
        offset = section_offset + index * 40
        name = blob[offset:offset + 8].split(b'\0', 1)[0].decode('ascii', errors='ignore')
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from('<IIII', blob, offset + 8)
        sections.append({
            'name': name,
            'virtual_size': virtual_size,
            'virtual_address': virtual_address,
            'raw_size': raw_size,
            'raw_offset': raw_offset,
        })
    return sections



def section_for_offset(sections: list[dict[str, int | str]], offset: int) -> dict[str, int | str] | None:
    """根据文件偏移查找所在节区。"""

    for section in sections:
        start = int(section['raw_offset'])
        end = start + max(int(section['raw_size']), int(section['virtual_size']))
        if start <= offset < end:
            return section
    return None



def offset_to_va(sections: list[dict[str, int | str]], offset: int) -> int:
    """把文件偏移转换为虚拟地址。"""

    section = section_for_offset(sections, offset)
    if section is None:
        return IMAGE_BASE + offset
    return IMAGE_BASE + int(section['virtual_address']) + (offset - int(section['raw_offset']))



def format_window(blob: bytes, start: int, end: int) -> dict[str, object]:
    """把一小段指令窗口格式化成十六进制与 ASCII 预览。"""

    chunk = blob[start:end]
    return {
        'start_offset': start,
        'end_offset': end,
        'hex': ' '.join(f'{byte:02x}' for byte in chunk),
        'ascii': ''.join(chr(byte) if 32 <= byte < 127 else '.' for byte in chunk),
    }



def locate_exe_pattern(
    blob: bytes,
    sections: list[dict[str, int | str]],
    label: str,
    pattern: bytes,
) -> dict[str, object] | None:
    """定位字符串或魔数在 EXE 中的位置，并回溯全部 32 位绝对引用。"""

    offset = blob.find(pattern)
    if offset < 0:
        return None
    pattern_va = offset_to_va(sections, offset)
    ref_pattern = struct.pack('<I', pattern_va)
    xref_offsets: list[int] = []
    search_from = 0
    while True:
        hit = blob.find(ref_pattern, search_from)
        if hit < 0:
            break
        xref_offsets.append(hit)
        search_from = hit + 1
    return {
        'label': label,
        'pattern': pattern.decode('ascii', errors='replace'),
        'offset': offset,
        'va': pattern_va,
        'section': section_for_offset(sections, offset)['name'] if section_for_offset(sections, offset) else None,
        'xref_offsets': xref_offsets,
        'xref_vas': [offset_to_va(sections, xref) for xref in xref_offsets],
    }



def cluster_xrefs(items: list[tuple[int, str]], gap: int = 0x280) -> list[dict[str, object]]:
    """把相邻引用点聚成代码簇，用于识别成组的加载流程。"""

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
        results.append({
            'start_offset': group[0][0],
            'end_offset': group[-1][0],
            'span_bytes': group[-1][0] - group[0][0],
            'labels_in_order': [label for _offset, label in group],
            'members': [
                {
                    'label': label,
                    'xref_offset': offset,
                }
                for offset, label in group
            ],
        })
    return results



def summarize_bundle_xrefs(
    refs: dict[str, dict[str, object] | None],
    keys: list[str],
) -> dict[str, object]:
    """汇总一组扩展名的引用点，观察它们是否在 EXE 中成簇出现。"""

    items: list[tuple[int, str]] = []
    for key in keys:
        ref = refs.get(key)
        if not ref:
            continue
        items.extend((offset, key) for offset in ref['xref_offsets'])
    ordered = sorted(items)
    return {
        'members': keys,
        'xref_count': len(ordered),
        'xref_offsets': [offset for offset, _label in ordered],
        'clusters': cluster_xrefs(ordered),
    }



def inspect_magic_push_sites(
    blob: bytes,
    sections: list[dict[str, int | str]],
    ref: dict[str, object] | None,
) -> list[dict[str, object]]:
    """检查魔数引用点附近是否出现 `push 长度; push 魔数` 一类独立头校验模式。"""

    if not ref:
        return []
    sites: list[dict[str, object]] = []
    for xref_offset in ref['xref_offsets']:
        push_opcode = blob[xref_offset - 1] if xref_offset >= 1 else None
        length_push = blob[xref_offset - 3] if xref_offset >= 3 else None
        length_value = blob[xref_offset - 2] if xref_offset >= 2 else None
        sites.append({
            'xref_offset': xref_offset,
            'xref_va': offset_to_va(sections, xref_offset),
            'section': section_for_offset(sections, xref_offset)['name'] if section_for_offset(sections, xref_offset) else None,
            'looks_like_push_imm32': push_opcode == 0x68,
            'preceded_by_push_len': length_push == 0x6A,
            'push_len_value': length_value if length_push == 0x6A else None,
            'window': format_window(blob, max(0, xref_offset - 12), min(len(blob), xref_offset + 28)),
        })
    return sites



def summarize_exe_linkage(game_dir: Path) -> dict[str, object]:
    """从 `Emperor.exe` 重新梳理 `.dor` 与 `.m` 的关系证据链。"""

    blob = (game_dir / 'Emperor.exe').read_bytes()
    sections = parse_pe_sections(blob)
    refs = {
        label: locate_exe_pattern(blob, sections, label, pattern)
        for label, pattern in EXE_PATTERNS.items()
    }

    map_bundle = summarize_bundle_xrefs(refs, ['.m', '.s', '.x'])
    sidecar_bundle = summarize_bundle_xrefs(refs, ['.spr', '.dor', '.evt'])
    door_magic_checks = inspect_magic_push_sites(blob, sections, refs.get('Door    Data'))
    soldier_magic_checks = inspect_magic_push_sites(blob, sections, refs.get('Soldier Data'))

    inference = [
        '`.m/.s/.x` 与 `.spr/.dor/.evt` 在 Emperor.exe 中分别落在两组独立扩展名引用簇里，说明主地图与 sidecar 的装配链是分开的。',
        '`.dor` 扩展名引用点始终夹在 `.spr` 与 `.evt` 之间，更像同关卡 sidecar 装配流程的一部分，而不是 `.m` 记录体的直接镜像。',
    ]
    if door_magic_checks:
        push_len_values = sorted({site['push_len_value'] for site in door_magic_checks if site['push_len_value'] is not None})
        if push_len_values:
            inference.append(
                f'`Door    Data` 只有 {len(door_magic_checks)} 处代码引用，且都带有独立的 12 字节头校验模式（push_len={push_len_values}），说明 `.dor` 是带独立文件头的 sidecar。'
            )
    if map_bundle['clusters'] and sidecar_bundle['clusters']:
        inference.append(
            '两组扩展名都呈现两段镜像代码簇，像是在“读入/写回”或“两条初始化路径”中分别处理同一批配套文件；`.dor` 与 `.m` 因此更像同 stage 级别的兄弟资源，而不是彼此内嵌。'
        )

    return {
        'image_base': IMAGE_BASE,
        'sections': sections,
        'resource_refs': {key: value for key, value in refs.items() if value is not None},
        'bundles': {
            'map_bundle': map_bundle,
            'sidecar_bundle': sidecar_bundle,
        },
        'magic_checks': {
            'Door    Data': door_magic_checks,
            'Soldier Data': soldier_magic_checks,
        },
        'inference': inference,
    }



def analyze_dor_relationship(
    root: Path,
    stage: str,
    out_dir: Path,
    layout: str,
    layers: str,
    palette_source: str,
    top_pairs: int,
) -> dict[str, object]:
    """分析 `.dor` 与 `.m` 的潜在坐标关系，并补上 Emperor.exe 侧证据。"""

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
    render_stage(stage_path, blocks, palette, base_map_path, layout, layers, None)
    _, _, origin_x, origin_y = canvas_size(width, height, layout)

    overlays = render_overlay_images(base_map_path, stage_dir / 'overlays', layout, origin_x, origin_y, candidate_pairs)
    exe_linkage = summarize_exe_linkage(game_dir)

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
        'exe_clue': exe_linkage['resource_refs'].get('.dor'),
        'exe_linkage': exe_linkage,
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
            'projection_assumption': '当前把候选字段当作 `.m` 的 cell 坐标，并按编辑器与 Emperor.exe 已确认的 stagger 网格投影到底图。',
            'confidence': 'exploratory',
        },
        'inference': [
            '当前可视化只证明“某些 `.dor` 字段组合能落入 `.m` 的地图格坐标空间”，还不能直接把它们命名成门、入口或触发器字段。',
            '结合 Emperor.exe 的扩展名引用簇与 `Door    Data` 魔数校验，`.dor` 更像与 `.spr/.evt` 并列的关卡 sidecar，而不是 `.m` 内某个 byte 字段的直接外置表。',
        ] + exe_linkage['inference'],
    }
    report_path = stage_dir / 'dor_relationship.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report['report'] = str(report_path)
    return report



def main() -> int:
    parser = argparse.ArgumentParser(description='分析 `.dor` 与 `.m` 的关系，并导出候选坐标覆盖图与 Emperor.exe 证据。')
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
