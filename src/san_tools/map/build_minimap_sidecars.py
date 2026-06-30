from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from extract_kingdom import DEFAULT_PALETTE_SOURCE, find_game_dir, load_palette
except ImportError:
    from san_tools.map.extract_kingdom import DEFAULT_PALETTE_SOURCE, find_game_dir, load_palette

try:
    from minimap_sidecar import (
        ACTIVE_ROWS,
        GRID_SIZE,
        build_active_minimap_bytes,
        byte_same_ratio,
        merge_active_with_reference_tail,
        parse_stage_final_palette,
        save_sidecar_preview,
        validate_sidecar_blob,
    )
except ImportError:
    from san_tools.map.minimap_sidecar import (
        ACTIVE_ROWS,
        GRID_SIZE,
        build_active_minimap_bytes,
        byte_same_ratio,
        merge_active_with_reference_tail,
        parse_stage_final_palette,
        save_sidecar_preview,
        validate_sidecar_blob,
    )


def list_stage_stems(game_dir: Path) -> list[str]:
    """列出同时拥有 `.m/.s/.x` 的关卡。"""

    stems: list[str] = []
    for path in sorted(game_dir.glob("stage*.m")):
        stem = path.stem
        if (game_dir / f"{stem}.s").exists() and (game_dir / f"{stem}.x").exists():
            stems.append(stem)
    return stems


def resolve_stage_path(root: Path, game_dir: Path, stage: str | None, source: Path | None) -> Path:
    """按参数解析要处理的 `.m` 路径。"""

    if source is not None:
        return source if source.is_absolute() else (root / source).resolve()
    if not stage:
        raise ValueError("未指定 --stage 或 --source。")
    return game_dir / f"{stage}.m"


def convert_stage(
    game_dir: Path,
    stage_path: Path,
    out_dir: Path,
    palette_source: str,
    grid_size: int,
    active_rows: int,
    emit_preview: bool,
    preview_scale: int,
) -> dict[str, object]:
    """为单个关卡生成新的 `.s/.x` 文件。"""

    stage_name = stage_path.stem
    if not stage_path.exists():
        raise FileNotFoundError(stage_path)
    width, height, final_palette = parse_stage_final_palette(stage_path)
    active_bytes = build_active_minimap_bytes(width, height, final_palette, grid_size, active_rows)
    stage_out_dir = out_dir / stage_name
    stage_out_dir.mkdir(parents=True, exist_ok=True)
    palette = load_palette(game_dir, palette_source)

    outputs: dict[str, object] = {}
    for suffix in ("s", "x"):
        reference_path = game_dir / f"{stage_name}.{suffix}"
        reference_blob = reference_path.read_bytes()
        validate_sidecar_blob(reference_blob, grid_size)
        merged = merge_active_with_reference_tail(active_bytes, reference_blob, grid_size, active_rows)
        out_path = stage_out_dir / f"{stage_name}.{suffix}"
        out_path.write_bytes(merged)
        entry = {
            "reference": str(reference_path),
            "output": str(out_path),
            "full_match_ratio": byte_same_ratio(merged, reference_blob),
            "active_match_ratio": byte_same_ratio(merged[: grid_size * active_rows], reference_blob[: grid_size * active_rows]),
            "tail_match_ratio": byte_same_ratio(merged[grid_size * active_rows :], reference_blob[grid_size * active_rows :]),
        }
        if emit_preview:
            preview_path = stage_out_dir / f"{stage_name}_{suffix}.png"
            save_sidecar_preview(merged, palette, preview_path, grid_size=grid_size, scale=preview_scale)
            entry["preview"] = str(preview_path)
        outputs[suffix] = entry

    meta = {
        "stage": stage_name,
        "source_m": str(stage_path),
        "width": width,
        "height": height,
        "grid_size": grid_size,
        "active_rows": active_rows,
        "tail_rows": grid_size - active_rows,
        "strategy": {
            "active_area": "使用 .m 的 final_palette 缩放为 160x128（默认）",
            "tail_area": "保留原始 .s/.x 在 y >= 128 的字节副本",
        },
        "outputs": outputs,
    }
    meta_path = stage_out_dir / 'sidecar_build_report.json'
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    meta['report'] = str(meta_path)
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description='根据 .m 重建 .s/.x 的有效区，并保留原始尾区。')
    parser.add_argument('root', nargs='?', default='.', type=Path, help='项目根目录')
    parser.add_argument('--stage', action='append', dest='stages', help='指定关卡，例如 stage11；可重复传入')
    parser.add_argument('--source', type=Path, help='直接指定一个 .m 文件；传入后忽略 --stage')
    parser.add_argument('--all', action='store_true', help='批量处理所有同时拥有 .m/.s/.x 的关卡')
    parser.add_argument('--out', default=Path('derived/minimap_sidecars'), type=Path, help='输出目录')
    parser.add_argument('--palette', default=DEFAULT_PALETTE_SOURCE, help='预览图使用的调色板来源')
    parser.add_argument('--grid-size', type=int, default=GRID_SIZE, help='sidecar 网格尺寸，默认 160')
    parser.add_argument('--active-rows', type=int, default=ACTIVE_ROWS, help='从 .m 派生的有效行数，默认 128')
    parser.add_argument('--preview-scale', type=int, default=3, help='预览图放大倍数')
    parser.add_argument('--no-preview', action='store_true', help='不导出 .png 预览')
    args = parser.parse_args()

    root = args.root.resolve()
    game_dir = find_game_dir(root)
    out_dir = args.out if args.out.is_absolute() else root / args.out

    if args.source is not None:
        stage_paths = [resolve_stage_path(root, game_dir, None, args.source)]
    elif args.all:
        stage_paths = [game_dir / f'{stem}.m' for stem in list_stage_stems(game_dir)]
    else:
        stage_names = args.stages or ['stage11']
        stage_paths = [resolve_stage_path(root, game_dir, stage_name, None) for stage_name in stage_names]

    results = [
        convert_stage(
            game_dir=game_dir,
            stage_path=stage_path,
            out_dir=out_dir,
            palette_source=args.palette,
            grid_size=args.grid_size,
            active_rows=args.active_rows,
            emit_preview=not args.no_preview,
            preview_scale=args.preview_scale,
        )
        for stage_path in stage_paths
    ]
    print(json.dumps({'count': len(results), 'stages': results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
