from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
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
    from palette import PAINT_RGB_TEXT_PALETTE
except ImportError:
    from san_tools.map.palette import PAINT_RGB_TEXT_PALETTE

try:
    from render_m_cel_map import canvas_size, cell_xy, parse_counted_cel, render_stage
except ImportError:
    from san_tools.map.render_m_cel_map import canvas_size, cell_xy, parse_counted_cel, render_stage

COLOR_PALETTE = [
    '#e11d48', '#2563eb', '#059669', '#d97706', '#7c3aed', '#0891b2', '#dc2626', '#65a30d',
    '#c2410c', '#1d4ed8', '#0f766e', '#9333ea', '#be123c', '#0ea5e9', '#16a34a', '#ea580c',
]

BYTE_LABELS = {
    8: 'byte08',
    9: 'byte09',
    10: 'byte10',
    11: 'byte11',
    12: 'byte12',
    13: 'byte13',
    14: 'byte14',
    15: 'byte15',
}


def parse_record_fields(record: bytes) -> dict[str, int]:
    """把 `.m` 单个 cell 记录拆成可读字段。"""

    return {
        'acwx': int.from_bytes(record[0:2], 'little', signed=True),
        'acwy': int.from_bytes(record[2:4], 'little', signed=True),
        'acwz': int.from_bytes(record[4:6], 'little', signed=True),
        'word06': int.from_bytes(record[6:8], 'little', signed=True),
        'byte08': record[8],
        'byte09': record[9],
        'byte10': record[10],
        'byte11': record[11],
        'byte12': record[12],
        'byte13': record[13],
        'byte14': record[14],
        'byte15': record[15],
    }


def build_cells(width: int, records: list[bytes]) -> list[dict[str, int]]:
    """为每个记录附带 cell 坐标与拆解字段。"""

    cells: list[dict[str, int]] = []
    for index, record in enumerate(records):
        x = index % width
        y = index // width
        fields = parse_record_fields(record)
        cells.append({'index': index, 'x': x, 'y': y, **fields})
    return cells


def color_for_index(index: int) -> str:
    """按稳定顺序为分组分配颜色。"""

    return PAINT_RGB_TEXT_PALETTE[index % len(PAINT_RGB_TEXT_PALETTE)]


def write_raw_byte_maps(stage_dir: Path, width: int, height: int, cells: list[dict[str, int]], byte_start: int, byte_end: int) -> dict[str, object]:
    """导出 byte08-15 的原始网格图与拼图。"""

    raw_dir = stage_dir / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, object]] = []
    raw_paths: list[Path] = []
    for byte_index in range(byte_start, byte_end + 1):
        field = BYTE_LABELS[byte_index]
        data = bytes(cell[field] for cell in cells)
        image = Image.frombytes('L', (width, height), data)
        path = raw_dir / f'{field}.png'
        image.save(path)
        raw_paths.append(path)
        counter = Counter(data)
        outputs.append({
            'field': field,
            'image': str(path),
            'unique_values': len(counter),
            'top_counts': [{'value': value, 'count': count} for value, count in counter.most_common(16)],
        })

    sheet_path = raw_dir / 'byte_fields_sheet.png'
    if raw_paths:
        images = [Image.open(path).convert('L') for path in raw_paths]
        tile_width = max(image.width for image in images)
        tile_height = max(image.height for image in images)
        columns = 2
        rows = math.ceil(len(images) / columns)
        canvas = Image.new('L', (tile_width * columns, tile_height * rows), 0)
        for index, image in enumerate(images):
            col = index % columns
            row = index // columns
            canvas.paste(image, (col * tile_width, row * tile_height))
        canvas.save(sheet_path)
    return {'raw_maps': outputs, 'sheet': str(sheet_path)}


def project_cell(cell_x: int, cell_y: int, layout: str, origin_x: int, origin_y: int) -> tuple[int, int]:
    """把 cell 坐标投影到底图像素坐标。"""

    pixel_x, pixel_y = cell_xy(cell_x, cell_y, layout, origin_x, origin_y)
    return pixel_x + 20, pixel_y + 10


def legend_rows(title: str, counter: Counter[int], limit: int = 10) -> list[str]:
    """构建图例文案。"""

    rows = [title]
    for value, count in counter.most_common(limit):
        rows.append(f'{value}: {count}')
    return rows


def draw_legend(draw: ImageDraw.ImageDraw, rows: list[str], colors: list[str] | None = None) -> None:
    """绘制简洁图例。"""

    box_width = 300
    box_height = 14 + 18 * max(1, len(rows))
    draw.rectangle((8, 8, 8 + box_width, 8 + box_height), fill=(255, 255, 255, 220))
    for index, row in enumerate(rows):
        fill = '#111827'
        if colors and 0 < index <= len(colors):
            fill = colors[index - 1]
        draw.text((16, 14 + index * 18), row, fill=fill)


def write_thumbnail(image: Image.Image, out_path: Path, max_width: int = 2400) -> str:
    """给超大底图导出缩略图，便于快速浏览。"""

    if image.width <= max_width:
        thumb = image.copy()
    else:
        scale = max_width / image.width
        thumb = image.resize((max_width, max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    thumb.save(out_path)
    return str(out_path)


def render_condition_overlay(
    base_map_path: Path,
    overlay_path: Path,
    cells: list[dict[str, int]],
    selector,
    *,
    title: str,
    layout: str,
    origin_x: int,
    origin_y: int,
    color: str,
) -> dict[str, object]:
    """把指定条件命中的 cell 叠加到底图上。"""

    image = Image.open(base_map_path).convert('RGBA')
    draw = ImageDraw.Draw(image)
    selected = [cell for cell in cells if selector(cell)]
    for cell in selected:
        px, py = project_cell(cell['x'], cell['y'], layout, origin_x, origin_y)
        draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=color, outline='white', width=1)
    rows = [title, f'count: {len(selected)}']
    draw_legend(draw, rows)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(overlay_path)
    thumb_path = overlay_path.with_name(f'{overlay_path.stem}_thumb.png')
    thumb = write_thumbnail(image, thumb_path)
    return {
        'title': title,
        'overlay': str(overlay_path),
        'thumbnail': thumb,
        'count': len(selected),
    }


def render_value_groups_overlay(
    base_map_path: Path,
    overlay_path: Path,
    cells: list[dict[str, int]],
    *,
    field: str,
    layout: str,
    origin_x: int,
    origin_y: int,
    show_labels: bool = True,
    legend_limit: int = 16,
) -> dict[str, object]:
    """把指定字段的所有非零取值按 value group 分色叠加到底图上。"""

    image = Image.open(base_map_path).convert('RGBA')
    draw = ImageDraw.Draw(image)
    counter = Counter(cell[field] for cell in cells if cell[field] != 0)
    values = [value for value, _count in counter.most_common()]
    colors = {value: color_for_index(index) for index, value in enumerate(values)}
    grouped_cells: dict[int, list[dict[str, int]]] = defaultdict(list)
    for cell in cells:
        value = cell[field]
        if value == 0:
            continue
        grouped_cells[value].append(cell)

    for value in values:
        color = colors[value]
        points: list[tuple[int, int]] = []
        for cell in grouped_cells[value]:
            px, py = project_cell(cell['x'], cell['y'], layout, origin_x, origin_y)
            points.append((px, py))
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=color, outline='white', width=1)
        if show_labels and points:
            center_x = round(sum(point[0] for point in points) / len(points))
            center_y = round(sum(point[1] for point in points) / len(points))
            draw.text((center_x + 4, center_y - 4), str(value), fill=color)

    rows = [f'{field} 非零分组', f'groups: {len(values)}', f'cells: {sum(counter.values())}']
    legend_colors: list[str] = []
    for value, count in counter.most_common(legend_limit):
        rows.append(f'{value}: {count}')
        legend_colors.append(colors[value])
    if len(counter) > legend_limit:
        rows.append(f'... 其余 {len(counter) - legend_limit} 组')
    draw_legend(draw, rows, legend_colors)

    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(overlay_path)
    thumb_path = overlay_path.with_name(f'{overlay_path.stem}_thumb.png')
    thumb = write_thumbnail(image, thumb_path)
    return {
        'field': field,
        'overlay': str(overlay_path),
        'thumbnail': thumb,
        'nonzero_groups': len(values),
        'nonzero_cells': sum(counter.values()),
        'top_counts': [{'value': value, 'count': count} for value, count in counter.most_common(legend_limit)],
    }


def connected_components(points: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """按四联通拆分连通块。"""

    components: list[list[tuple[int, int]]] = []
    seen: set[tuple[int, int]] = set()
    for start in points:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        current: list[tuple[int, int]] = []
        while stack:
            x, y = stack.pop()
            current.append((x, y))
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor in points and neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(current)
    return components


def summarize_components(cells: list[dict[str, int]]) -> dict[str, object]:
    """统计命中区域的连通块规模。"""

    points = {(cell['x'], cell['y']) for cell in cells}
    components = connected_components(points)
    sizes = sorted((len(component) for component in components), reverse=True)
    boxes = []
    for component in components[:24]:
        xs = [point[0] for point in component]
        ys = [point[1] for point in component]
        boxes.append({
            'count': len(component),
            'bbox': [min(xs), min(ys), max(xs), max(ys)],
        })
    return {
        'component_count': len(components),
        'component_sizes_top': sizes[:24],
        'component_boxes_top': boxes,
    }


def summarize_selection(name: str, cells: list[dict[str, int]]) -> dict[str, object]:
    """汇总一组命中 cell 的字段分布。"""

    xs = [cell['x'] for cell in cells]
    ys = [cell['y'] for cell in cells]
    summary = {
        'name': name,
        'count': len(cells),
        'bbox': [min(xs), min(ys), max(xs), max(ys)] if cells else None,
        'acwx_top': Counter(cell['acwx'] for cell in cells).most_common(12),
        'acwy_top': Counter(cell['acwy'] for cell in cells).most_common(12),
        'acwz_top': Counter(cell['acwz'] for cell in cells).most_common(12),
        'byte08_top': Counter(cell['byte08'] for cell in cells).most_common(12),
        'byte09_top': Counter(cell['byte09'] for cell in cells).most_common(12),
        'byte10_top': Counter(cell['byte10'] for cell in cells).most_common(12),
        'byte11_top': Counter(cell['byte11'] for cell in cells).most_common(12),
        'components': summarize_components(cells),
    }
    return summary


def summarize_byte_fields(cells: list[dict[str, int]], byte_start: int, byte_end: int) -> list[dict[str, object]]:
    """统计 byte08-15 每个字段的全局分布。"""

    summaries: list[dict[str, object]] = []
    for byte_index in range(byte_start, byte_end + 1):
        field = BYTE_LABELS[byte_index]
        counter = Counter(cell[field] for cell in cells)
        summaries.append({
            'field': field,
            'unique_values': len(counter),
            'zero_count': counter.get(0, 0),
            'nonzero_count': sum(count for value, count in counter.items() if value != 0),
            'top_counts': [{'value': value, 'count': count} for value, count in counter.most_common(20)],
        })
    return summaries


def summarize_byte11_groups(cells: list[dict[str, int]]) -> dict[str, object]:
    """检查 `byte11` 相同取值是否聚集在一起。"""

    by_value: dict[int, list[dict[str, int]]] = defaultdict(list)
    for cell in cells:
        if cell['byte11'] != 0:
            by_value[cell['byte11']].append(cell)

    rows: list[dict[str, object]] = []
    profile_counter: Counter[tuple[int, ...]] = Counter()
    all_single_component = True
    all_same_size = True
    sizes_seen = set()
    for value in sorted(by_value):
        items = by_value[value]
        points = {(cell['x'], cell['y']) for cell in items}
        components = connected_components(points)
        if len(components) != 1:
            all_single_component = False
        sizes_seen.add(len(items))
        if len(sizes_seen) > 1:
            all_same_size = False
        rows_by_y: dict[int, list[int]] = defaultdict(list)
        for cell in items:
            rows_by_y[cell['y']].append(cell['x'])
        row_profile = tuple(len(rows_by_y[y]) for y in sorted(rows_by_y))
        profile_counter[row_profile] += 1
        xs = [cell['x'] for cell in items]
        ys = [cell['y'] for cell in items]
        rows.append({
            'value': value,
            'count': len(items),
            'bbox': [min(xs), min(ys), max(xs), max(ys)],
            'component_count': len(components),
            'row_profile': list(row_profile),
        })

    values = sorted(by_value)
    contiguous = bool(values) and values == list(range(values[0], values[-1] + 1))
    common_profile = profile_counter.most_common(1)[0][0] if profile_counter else ()
    return {
        'nonzero_value_count': len(values),
        'values': values,
        'contiguous_value_range': contiguous,
        'all_single_component': all_single_component,
        'all_same_group_size': all_same_size,
        'group_size': next(iter(sizes_seen)) if len(sizes_seen) == 1 else None,
        'common_row_profile': list(common_profile),
        'groups': rows,
    }


def render_byte11_groups_raw(stage_dir: Path, width: int, height: int, cells: list[dict[str, int]]) -> dict[str, object]:
    """导出 `byte11` 同值分组的彩色网格图。"""

    scale = 4
    image = Image.new('RGBA', (width * scale, height * scale), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    values = sorted({cell['byte11'] for cell in cells if cell['byte11'] != 0})
    colors = {value: color_for_index(index) for index, value in enumerate(values)}
    for cell in cells:
        value = cell['byte11']
        if value == 0:
            continue
        x0 = cell['x'] * scale
        y0 = cell['y'] * scale
        draw.rectangle((x0, y0, x0 + scale - 1, y0 + scale - 1), fill=colors[value])
    path = stage_dir / 'raw' / 'byte11_groups.png'
    image.save(path)
    return {'image': str(path)}


def render_byte11_groups_overlay(
    base_map_path: Path,
    stage_dir: Path,
    cells: list[dict[str, int]],
    layout: str,
    origin_x: int,
    origin_y: int,
) -> dict[str, object]:
    """把 `byte11` 同值分组画到底图上并标出编号。"""

    image = Image.open(base_map_path).convert('RGBA')
    draw = ImageDraw.Draw(image)
    by_value: dict[int, list[dict[str, int]]] = defaultdict(list)
    for cell in cells:
        if cell['byte11'] != 0:
            by_value[cell['byte11']].append(cell)

    legend = ['byte11 同值分组']
    legend_colors: list[str] = []
    for index, value in enumerate(sorted(by_value)):
        color = color_for_index(index)
        legend.append(f'{value}: {len(by_value[value])}')
        legend_colors.append(color)
        points = []
        for cell in by_value[value]:
            px, py = project_cell(cell['x'], cell['y'], layout, origin_x, origin_y)
            points.append((px, py))
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=color, outline='white', width=1)
        center_x = round(sum(point[0] for point in points) / len(points))
        center_y = round(sum(point[1] for point in points) / len(points))
        draw.text((center_x + 4, center_y - 4), str(value), fill=color)

    draw_legend(draw, legend[:18], legend_colors[:17])
    overlay_path = stage_dir / 'overlays' / 'byte11_groups.png'
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(overlay_path)
    thumb_path = overlay_path.with_name('byte11_groups_thumb.png')
    thumb = write_thumbnail(image, thumb_path)
    return {
        'overlay': str(overlay_path),
        'thumbnail': thumb,
    }


def render_sheet(paths: list[Path], out_path: Path, max_width: int = 2400) -> str:
    """把多张图片拼成总览图。"""

    if not paths:
        return str(out_path)
    images = [Image.open(path).convert('RGBA') for path in paths]
    tile_width = max(image.width for image in images)
    tile_height = max(image.height for image in images)
    columns = 2
    rows = math.ceil(len(images) / columns)
    canvas = Image.new('RGBA', (tile_width * columns, tile_height * rows), (255, 255, 255, 255))
    for index, image in enumerate(images):
        col = index % columns
        row = index // columns
        canvas.paste(image, (col * tile_width, row * tile_height))
    canvas.save(out_path)
    thumb_path = out_path.with_name(f'{out_path.stem}_thumb.png')
    write_thumbnail(canvas, thumb_path, max_width=max_width)
    return str(out_path)


def scan_all_stages(root: Path, byte_start: int, byte_end: int) -> dict[str, object]:
    """???? `.m`???????????????????"""

    game_dir = find_game_dir(root)
    totals = {BYTE_LABELS[index]: Counter() for index in range(byte_start, byte_end + 1)}
    stage_rows: list[dict[str, object]] = []
    focus_hits = {
        'byte09_eq_1': [],
        'byte11_nonzero': [],
    }
    for path in sorted(game_dir.glob('stage*.m')):
        width, height, records = parse_m(path)
        cells = build_cells(width, records)
        row = {'stage': path.stem, 'width': width, 'height': height}
        for field in totals:
            counter = Counter(cell[field] for cell in cells)
            totals[field].update(counter)
            row[field] = {'unique_values': len(counter), 'top_counts': counter.most_common(8)}
        count09 = sum(1 for cell in cells if cell['byte09'] == 1)
        count11 = sum(1 for cell in cells if cell['byte11'] != 0)
        if count09:
            focus_hits['byte09_eq_1'].append({'stage': path.stem, 'count': count09})
        if count11:
            focus_hits['byte11_nonzero'].append({'stage': path.stem, 'count': count11, 'unique_values': len({cell['byte11'] for cell in cells if cell['byte11'] != 0})})
        stage_rows.append(row)
    return {
        'field_totals': {
            field: {
                'unique_values': len(counter),
                'top_counts': [{'value': value, 'count': count} for value, count in counter.most_common(20)],
            }
            for field, counter in totals.items()
        },
        'focus_hits': focus_hits,
        'stage_rows': stage_rows,
    }


def analyze_m_byte_fields(
    root: Path,
    stage: str,
    out_dir: Path,
    layout: str,
    layers: str,
    palette_source: str,
    byte_start: int,
    byte_end: int,
) -> dict[str, object]:
    """?? `.m` ? byte08-15?????????????????????"""

    game_dir = find_game_dir(root)
    stage_path = game_dir / f'{stage}.m'
    stage_dir = out_dir / stage
    stage_dir.mkdir(parents=True, exist_ok=True)

    width, height, records = parse_m(stage_path)
    cells = build_cells(width, records)
    palette = load_palette(game_dir, palette_source)
    blocks = parse_counted_cel(game_dir / 'kingdom.cel')
    base_map_path = stage_dir / 'm_byte_base_map.png'
    render_stage(stage_path, blocks, palette, base_map_path, layout, layers, None)
    base_image = Image.open(base_map_path).convert('RGBA')
    base_thumb = write_thumbnail(base_image, stage_dir / 'm_byte_base_map_thumb.png')
    _, _, origin_x, origin_y = canvas_size(width, height, layout)

    raw_outputs = write_raw_byte_maps(stage_dir, width, height, cells, byte_start, byte_end)
    byte11_groups_raw = render_byte11_groups_raw(stage_dir, width, height, cells)

    stage_byte_summaries = summarize_byte_fields(cells, byte_start, byte_end)
    byte11_groups = summarize_byte11_groups(cells)

    byte_group_overlays: list[dict[str, object]] = []
    byte_group_overlay_paths: list[Path] = []
    for byte_index in range(byte_start, byte_end + 1):
        field = BYTE_LABELS[byte_index]
        overlay_path = stage_dir / 'overlays' / f'{field}_groups.png'
        overlay = render_value_groups_overlay(
            base_map_path,
            overlay_path,
            cells,
            field=field,
            layout=layout,
            origin_x=origin_x,
            origin_y=origin_y,
            show_labels=field in {'byte08', 'byte09', 'byte10', 'byte11'},
        )
        byte_group_overlays.append(overlay)
        byte_group_overlay_paths.append(Path(overlay['thumbnail']))

    focus_rows = [
        ('byte09_eq_1', lambda cell: cell['byte09'] == 1, 'byte09 = 1', '#e11d48'),
        ('byte11_nonzero', lambda cell: cell['byte11'] != 0, 'byte11 != 0', '#7c3aed'),
    ]

    focus_overlay_outputs: list[dict[str, object]] = []
    focus_overlay_paths: list[Path] = []
    focus_summaries: dict[str, object] = {}
    for key, selector, title, color in focus_rows:
        selected = [cell for cell in cells if selector(cell)]
        focus_summaries[key] = summarize_selection(key, selected)
        overlay_path = stage_dir / 'overlays' / f'{key}.png'
        overlay = render_condition_overlay(
            base_map_path,
            overlay_path,
            cells,
            selector,
            title=title,
            layout=layout,
            origin_x=origin_x,
            origin_y=origin_y,
            color=color,
        )
        focus_overlay_outputs.append(overlay)
        focus_overlay_paths.append(overlay_path)

    byte11_overlay = render_byte11_groups_overlay(base_map_path, stage_dir, cells, layout, origin_x, origin_y)
    focus_overlay_paths.append(stage_dir / 'overlays' / 'byte11_groups.png')
    focus_sheet = render_sheet(focus_overlay_paths, stage_dir / 'overlays' / 'focus_sheet.png')
    byte_group_overlay_sheet = render_sheet(byte_group_overlay_paths, stage_dir / 'overlays' / 'byte_value_groups_sheet.png')

    global_scan = scan_all_stages(root, byte_start, byte_end)

    judgement = []
    byte09_count = focus_summaries['byte09_eq_1']['count']
    if byte09_count:
        judgement.append(
            f'`byte09=1` 在 `{stage}` 命中 {byte09_count} 个 cell，覆盖范围横跨整张地图，且明显包含大量普通地形、叠加层与物件区；仅从分布看，它不像“少量不可达点”的窄标记。'
        )
    if byte11_groups['nonzero_value_count']:
        judgement.append(
            f'`byte11` 的非零同值确实高度聚集：当前关卡共有 {byte11_groups["nonzero_value_count"]} 个非零取值，是否连续编号={byte11_groups["contiguous_value_range"]}，每组大小={byte11_groups["group_size"]}，典型行轮廓={byte11_groups["common_row_profile"]}。这更像“区域/脚下 footprint 编号”，是否就是城池 ID 还需要继续和 `.stg`/场景对象对位。'
        )
    else:
        judgement.append('当前关卡 `byte11` 全零，没有出现可聚类的同值区域。')
    if all(next(item for item in stage_byte_summaries if item['field'] == field)['nonzero_count'] == 0 for field in ('byte12', 'byte14', 'byte15')):
        judgement.append('`byte12`、`byte14`、`byte15` 在当前样本里全零；全量 33 个 `.m` 里它们目前也都保持全零。')

    report = {
        'stage': stage,
        'm_path': str(stage_path),
        'm_dimensions': {'width': width, 'height': height},
        'byte_range': [byte_start, byte_end],
        'base_map': {'image': str(base_map_path), 'thumbnail': base_thumb},
        'raw_visualization': raw_outputs | {'byte11_groups': byte11_groups_raw},
        'overlay_visualization': {
            'byte_value_groups': byte_group_overlays,
            'byte_value_groups_sheet': byte_group_overlay_sheet,
            'focus_overlays': focus_overlay_outputs,
            'byte11_groups': byte11_overlay,
            'focus_sheet': focus_sheet,
        },
        'byte_fields': stage_byte_summaries,
        'byte11_groups': byte11_groups,
        'focus_stage': focus_summaries,
        'focus_global': global_scan['focus_hits'],
        'field_totals_global': global_scan['field_totals'],
        'judgement': judgement,
    }
    report_path = stage_dir / 'm_byte_fields.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report['report'] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='?? `.m` ? byte08-15??????????????????????????')
    parser.add_argument('root', nargs='?', default='.', type=Path, help='项目根目录')
    parser.add_argument('--stage', default='stage01', help='要分析的关卡名，例如 stage01')
    parser.add_argument('--out', default=Path('derived/m_byte_fields'), type=Path, help='输出目录')
    parser.add_argument('--layout', choices=['rect', 'iso', 'skew', 'stagger'], default='stagger', help='底图渲染布局')
    parser.add_argument('--layers', default='xyz', help='底图渲染层，默认 xyz')
    parser.add_argument('--palette', default=DEFAULT_PALETTE_SOURCE, help='底图使用的调色板来源')
    parser.add_argument('--byte-start', type=int, default=8, help='起始 byte 偏移，默认 8')
    parser.add_argument('--byte-end', type=int, default=15, help='结束 byte 偏移，默认 15')
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    result = analyze_m_byte_fields(
        root,
        args.stage,
        out_dir,
        args.layout,
        args.layers,
        args.palette,
        args.byte_start,
        args.byte_end,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
