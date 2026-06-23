from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path

from PIL import Image, ImageDraw

from extract_kingdom import DEFAULT_PALETTE_SOURCE, find_game_dir, load_palette
from render_m_cel_map import canvas_size, make_diamond_tile, make_object, parse_counted_cel, render_stage

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

EDITABLE_LAYERS = ("acwx", "acwy", "acwz")


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
    minimap_name: str,
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
        "editableLayers": list(EDITABLE_LAYERS),
        "palette": palette_source,
        "image": image_name,
        "minimap": {"image": minimap_name, "source": "rendered-map", "sync": "derived-from-m-records"},
        "resources": "resources.json",
        "records": records,
        "render": render_meta,
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def indexed_to_rgba(image: Image.Image, alpha_mask: Image.Image | None = None) -> Image.Image:
    rgba = image.convert("RGBA")
    if alpha_mask is None:
        alpha_mask = image.point(lambda value: 255 if value else 0).convert("L")
    rgba.putalpha(alpha_mask)
    return rgba


def fit_thumbnail(image: Image.Image, box_size: int) -> Image.Image:
    thumb = Image.new("RGBA", (box_size, box_size), (0, 0, 0, 0))
    work = image.copy()
    work.thumbnail((box_size - 8, box_size - 16), Image.Resampling.NEAREST)
    x = (box_size - work.width) // 2
    y = max(2, (box_size - work.height) // 2 - 4)
    thumb.alpha_composite(work, (x, y))
    return thumb


def build_resource_image(layer: str, entry: dict, palette: list[int]) -> tuple[Image.Image, dict]:
    if layer in ("acwx", "acwy"):
        tile, mask = make_diamond_tile(entry["pixels"], palette)
        image = indexed_to_rgba(tile, mask)
        meta = {"width": 40, "height": 20}
        return image, meta
    obj = make_object(entry, palette)
    image = indexed_to_rgba(obj)
    meta = {
        "width": entry["width"],
        "height": entry["height"],
        "xAnchor": entry["x_anchor"],
        "yAnchor": entry["y_anchor"],
    }
    return image, meta


def layer_usage(records: list[list[int]], layer: str) -> dict[int, int]:
    field = FIELD_NAMES.index(layer)
    usage: dict[int, int] = {}
    for record in records:
        value = record[field]
        if value >= 0:
            usage[value] = usage.get(value, 0) + 1
    return usage


def export_resource_catalog(blocks: dict, palette: list[int], stage_dir: Path, records: list[list[int]]) -> dict:
    catalog = {"format": "san-editor-resources-v1", "layers": {}}
    usage_by_layer = {layer: layer_usage(records, layer) for layer in EDITABLE_LAYERS}
    for layer in EDITABLE_LAYERS:
        box = 56 if layer != "acwz" else 72
        cols = 16 if layer != "acwz" else 12
        entries = []
        sprites: list[tuple[int, Image.Image, dict]] = []
        usage = usage_by_layer[layer]
        for index, entry in enumerate(blocks[layer]["entries"]):
            if entry is None:
                continue
            image, meta = build_resource_image(layer, entry, palette)
            meta["used"] = usage.get(index, 0)
            sprites.append((index, fit_thumbnail(image, box), meta))
        sprites.sort(key=lambda item: item[0])
        rows = max(1, (len(sprites) + cols - 1) // cols)
        atlas = Image.new("RGBA", (cols * box, rows * box), (0, 0, 0, 0))
        draw = ImageDraw.Draw(atlas)
        for n, (index, thumb, meta) in enumerate(sprites):
            x = (n % cols) * box
            y = (n // cols) * box
            atlas.alpha_composite(thumb, (x, y))
            draw.text((x + 3, y + box - 12), str(index), fill=(255, 255, 255, 230), stroke_width=1, stroke_fill=(0, 0, 0, 220))
            entries.append({"index": index, "atlas": [x, y, box, box], **meta})
        image_name = f"resources_{layer}.png"
        atlas.save(stage_dir / image_name)
        catalog["layers"][layer] = {"image": image_name, "tileSize": box, "columns": cols, "entries": entries}
    (stage_dir / "resources.json").write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return catalog


def export_minimap(map_path: Path, out_path: Path, max_width: int = 280) -> None:
    image = Image.open(map_path).convert("RGB")
    scale = max_width / image.width
    size = (max_width, max(1, round(image.height * scale)))
    image.resize(size, Image.Resampling.BILINEAR).save(out_path)


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
    map_path = stage_dir / "map.png"
    render_meta = render_stage(stage_path, blocks, palette, map_path, layout, layers, None)
    render_meta["source_output_size"] = [source_w, source_h]

    export_resource_catalog(blocks, palette, stage_dir, records)
    export_minimap(map_path, stage_dir / "minimap.png")
    write_stage_json(stage_dir / "stage.json", stage, width, height, records, layout, (ox, oy), "map.png", "minimap.png", render_meta, palette_source)
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
