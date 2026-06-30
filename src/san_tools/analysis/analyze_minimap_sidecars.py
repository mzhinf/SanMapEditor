from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from san_tools.analysis.analyze_stage_sidecars import find_game_dir
from san_tools.map.minimap_sidecar import (
    ACTIVE_ROWS,
    GRID_SIZE,
    build_active_minimap_bytes,
    byte_same_ratio,
    merge_active_with_reference_tail,
    parse_stage_final_palette,
)


def list_stage_stems(game_dir: Path) -> list[str]:
    """列出同时拥有 `.m/.s/.x` 的关卡。"""

    stems: list[str] = []
    for path in sorted(game_dir.glob('stage*.m')):
        stem = path.stem
        if (game_dir / f'{stem}.s').exists() and (game_dir / f'{stem}.x').exists():
            stems.append(stem)
    return stems


def row_dominance_scores(grids: list[bytes]) -> list[float]:
    """统计每一行跨关卡的“静态程度”，越高说明越像公共缓存尾巴。"""

    if not grids:
        return []
    stage_count = len(grids)
    scores: list[float] = []
    for row in range(GRID_SIZE):
        dominance_sum = 0.0
        base = row * GRID_SIZE
        for col in range(GRID_SIZE):
            counter = Counter(grid[base + col] for grid in grids)
            dominance_sum += counter.most_common(1)[0][1] / stage_count
        scores.append(round(dominance_sum / GRID_SIZE, 6))
    return scores


def build_report(root: Path, stages: list[str] | None = None) -> dict[str, object]:
    """构建 `.s/.x` 与 `.m` 调色板层的比对报告。"""

    game_dir = find_game_dir(root.resolve())
    selected_stages = stages or list_stage_stems(game_dir)
    stage_rows: list[dict[str, object]] = []
    s_grids: list[bytes] = []
    x_grids: list[bytes] = []
    x_better = 0
    s_better = 0

    for stem in selected_stages:
        width, height, final_palette = parse_stage_final_palette(game_dir / f'{stem}.m')
        active_scaled = build_active_minimap_bytes(width, height, final_palette, GRID_SIZE, ACTIVE_ROWS)
        s_grid = (game_dir / f'{stem}.s').read_bytes()
        x_grid = (game_dir / f'{stem}.x').read_bytes()
        merged_s = merge_active_with_reference_tail(active_scaled, s_grid, GRID_SIZE, ACTIVE_ROWS)
        merged_x = merge_active_with_reference_tail(active_scaled, x_grid, GRID_SIZE, ACTIVE_ROWS)
        s_ratio = byte_same_ratio(merged_s[: GRID_SIZE * ACTIVE_ROWS], s_grid[: GRID_SIZE * ACTIVE_ROWS])
        x_ratio = byte_same_ratio(merged_x[: GRID_SIZE * ACTIVE_ROWS], x_grid[: GRID_SIZE * ACTIVE_ROWS])
        sx_ratio = byte_same_ratio(s_grid, x_grid)
        if x_ratio > s_ratio:
            x_better += 1
        elif s_ratio > x_ratio:
            s_better += 1
        s_grids.append(s_grid)
        x_grids.append(x_grid)
        stage_rows.append(
            {
                'stage': stem,
                'width': width,
                'height': height,
                'active_rows': ACTIVE_ROWS,
                'tail_rows': GRID_SIZE - ACTIVE_ROWS,
                'scaled_final_palette_active_vs_s': s_ratio,
                'scaled_final_palette_active_vs_x': x_ratio,
                'merged_full_vs_s': byte_same_ratio(merged_s, s_grid),
                'merged_full_vs_x': byte_same_ratio(merged_x, x_grid),
                's_vs_x': sx_ratio,
                's_top_values': Counter(s_grid).most_common(12),
                'x_top_values': Counter(x_grid).most_common(12),
            }
        )

    s_rows = row_dominance_scores(s_grids)
    x_rows = row_dominance_scores(x_grids)
    return {
        'game_dir': str(game_dir),
        'stage_count': len(stage_rows),
        'summary': {
            'x_better_count': x_better,
            's_better_count': s_better,
            'active_rows': ACTIVE_ROWS,
            'tail_rows': GRID_SIZE - ACTIVE_ROWS,
            'avg_scaled_final_palette_active_vs_s': round(sum(item['scaled_final_palette_active_vs_s'] for item in stage_rows) / max(1, len(stage_rows)), 6),
            'avg_scaled_final_palette_active_vs_x': round(sum(item['scaled_final_palette_active_vs_x'] for item in stage_rows) / max(1, len(stage_rows)), 6),
            'avg_merged_full_vs_s': round(sum(item['merged_full_vs_s'] for item in stage_rows) / max(1, len(stage_rows)), 6),
            'avg_merged_full_vs_x': round(sum(item['merged_full_vs_x'] for item in stage_rows) / max(1, len(stage_rows)), 6),
            'avg_s_vs_x': round(sum(item['s_vs_x'] for item in stage_rows) / max(1, len(stage_rows)), 6),
        },
        'row_consensus': {
            's': {
                'top_40_avg': round(sum(s_rows[:40]) / max(1, len(s_rows[:40])), 6),
                'middle_80_avg': round(sum(s_rows[40:120]) / max(1, len(s_rows[40:120])), 6),
                'bottom_40_avg': round(sum(s_rows[120:]) / max(1, len(s_rows[120:])), 6),
                'rows_ge_0_95': [index for index, value in enumerate(s_rows) if value >= 0.95],
                'sample_rows': {str(index): s_rows[index] for index in (0, 20, 40, 60, 80, 100, 120, 127, 128, 140, 150, 159) if index < len(s_rows)},
            },
            'x': {
                'top_40_avg': round(sum(x_rows[:40]) / max(1, len(x_rows[:40])), 6),
                'middle_80_avg': round(sum(x_rows[40:120]) / max(1, len(x_rows[40:120])), 6),
                'bottom_40_avg': round(sum(x_rows[120:]) / max(1, len(x_rows[120:])), 6),
                'rows_ge_0_95': [index for index, value in enumerate(x_rows) if value >= 0.95],
                'sample_rows': {str(index): x_rows[index] for index in (0, 20, 40, 60, 80, 100, 120, 127, 128, 140, 150, 159) if index < len(x_rows)},
            },
        },
        'stages': stage_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='统计 `.s/.x` 与 `.m` 调色板层的关系。')
    parser.add_argument('root', nargs='?', default='.', type=Path, help='工作区根目录')
    parser.add_argument('--stage', action='append', dest='stages', help='指定关卡，例如 stage11')
    parser.add_argument('--out', default=Path('derived/sidecar_analysis/minimap_sidecar_analysis.json'), type=Path, help='输出 JSON 路径')
    parser.add_argument('--indent', type=int, default=2, help='JSON 缩进')
    args = parser.parse_args()

    payload = build_report(args.root, args.stages)
    out_path = args.out if args.out.is_absolute() else args.root.resolve() / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=args.indent), encoding='utf-8')
    print(json.dumps({
        'out': str(out_path),
        'stage_count': payload['stage_count'],
        'summary': payload['summary'],
        'row_consensus': payload['row_consensus'],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
