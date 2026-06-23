from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path

from extract_kingdom import DEFAULT_PALETTE_SOURCE, find_game_dir, load_palette
from render_m_cel_map import canvas_size, parse_counted_cel, render_stage

FIELD_NAMES = [
    "acwx",
    "acwy",
    "acwz",
    "word06",
    "byte08",
    "byte09",
    "byte10",
    "byte11",
    "byte12",
    "final_palette",
    "byte14",
    "byte15",
]


def read_stage_records(stage_path: Path) -> tuple[int, int, list[list[int]]]:
    blob = stage_path.read_bytes()
    width, height = struct.unpack_from("<II", blob, 0)
    if blob[8:16] != b"Hello1.0":
        raise ValueError(f"not a stage .m file: {stage_path}")
    records: list[list[int]] = []
    for i in range(width * height):
        off = 16 + i * 16
        records.append([
            struct.unpack_from("<h", blob, off)[0],
            struct.unpack_from("<h", blob, off + 2)[0],
            struct.unpack_from("<h", blob, off + 4)[0],
            struct.unpack_from("<h", blob, off + 6)[0],
            blob[off + 8],
            blob[off + 9],
            blob[off + 10],
            blob[off + 11],
            blob[off + 12],
            blob[off + 13],
            blob[off + 14],
            blob[off + 15],
        ])
    return width, height, records


def write_stage_json(
    out_path: Path,
    stage_name: str,
    width: int,
    height: int,
    records: list[list[int]],
    layout: str,
    origin: tuple[int, int],
    image_name: str,
    render_meta: dict,
    palette_source: str,
) -> None:
    data = {
        "format": "san-editor-stage-v1",
        "stage": stage_name,
        "width": width,
        "height": height,
        "layout": layout,
        "origin": list(origin),
        "tile": {"width": 40, "height": 20, "row_step": 10, "odd_row_x": 20},
        "fields": FIELD_NAMES,
        "palette": palette_source,
        "image": image_name,
        "records": records,
        "render": render_meta,
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def export_editor_bundle(root: Path, stage: str, out_dir: Path, layout: str, layers: str, palette_source: str) -> dict:
    game_dir = find_game_dir(root)
    stage_path = game_dir / f"{stage}.m"
    if not stage_path.exists():
        raise FileNotFoundError(stage_path)

    width, height, records = read_stage_records(stage_path)
    source_w, source_h, ox, oy = canvas_size(width, height, layout)
    stage_dir = out_dir / stage
    stage_dir.mkdir(parents=True, exist_ok=True)

    palette = load_palette(game_dir, palette_source)
    blocks = parse_counted_cel(game_dir / "kingdom.cel")
    render_meta = render_stage(stage_path, blocks, palette, stage_dir / "map.png", layout, layers, None)
    render_meta["source_output_size"] = [source_w, source_h]

    write_stage_json(stage_dir / "stage.json", stage, width, height, records, layout, (ox, oy), "map.png", render_meta, palette_source)
    template = Path(__file__).with_name("editor_app.html")
    shutil.copyfile(template, stage_dir / "editor.html")

    index_path = out_dir / "index.json"
    existing = {"stages": []}
    if index_path.exists():
        existing = json.loads(index_path.read_text(encoding="utf-8"))
    stages = {entry["stage"]: entry for entry in existing.get("stages", [])}
    stages[stage] = {"stage": stage, "path": f"{stage}/editor.html", "width": width, "height": height}
    existing["stages"] = sorted(stages.values(), key=lambda item: item["stage"])
    index_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    return {"stage": stage, "width": width, "height": height, "out": str(stage_dir), "records": len(records)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", default="stage11")
    parser.add_argument("--out", default="derived/editor", type=Path)
    parser.add_argument("--layout", choices=["stagger"], default="stagger")
    parser.add_argument("--layers", default="xyz")
    parser.add_argument("--palette", default=DEFAULT_PALETTE_SOURCE)
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    result = export_editor_bundle(root, args.stage, out_dir, args.layout, args.layers, args.palette)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
