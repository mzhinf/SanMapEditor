from __future__ import annotations

import argparse
import base64
import json
import shutil
import struct
from pathlib import Path

from PIL import Image, ImageDraw

from extract_kingdom import DEFAULT_PALETTE_SOURCE, find_game_dir, load_palette
from render_m_cel_map import canvas_size, make_diamond_tile, make_object, parse_counted_cel, render_stage

try:
    from palette import PAINT_RGB_FLAG_PALETTE
except ImportError:
    from san_tools.map.palette import PAINT_RGB_FLAG_PALETTE

try:
    from minimap_sidecar import ACTIVE_ROWS, GRID_SIZE, validate_sidecar_blob
except ImportError:
    from san_tools.map.minimap_sidecar import ACTIVE_ROWS, GRID_SIZE, validate_sidecar_blob

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
    "byte13",
    "byte14",
    "byte15",
]

EDITABLE_LAYERS = ("acwx", "acwy", "acwz")
POINT_LAYER_FIELDS = ("byte08", "byte09", "byte10", "byte11")
FIELD_META = [
    {"name": "acwx", "alias": "terrain_base", "label": "底层地表", "editable": True, "reserved": False},
    {"name": "acwy", "alias": "terrain_overlay", "label": "叠加地表", "editable": True, "reserved": False},
    {"name": "acwz", "alias": "object_overlay", "label": "物件层", "editable": True, "reserved": False},
    {"name": "word06", "alias": "", "label": "保留字段", "editable": False, "reserved": True},
    {"name": "byte08", "alias": "land_water_hint", "label": "水陆切换提示", "editable": True, "reserved": False},
    {"name": "byte09", "alias": "blocked", "label": "阻挡标记", "editable": True, "reserved": False},
    {"name": "byte10", "alias": "site_trigger", "label": "据点触发", "editable": True, "reserved": False},
    {"name": "byte11", "alias": "site_area", "label": "据点区域", "editable": True, "reserved": False},
    {"name": "byte12", "alias": "reserved1", "label": "保留字段 1", "editable": False, "reserved": True},
    {"name": "byte13", "alias": "minimap_color", "label": "小地图颜色", "editable": True, "reserved": False, "sidecarSource": True},
    {"name": "byte14", "alias": "reserved2", "label": "保留字段 2", "editable": False, "reserved": True},
    {"name": "byte15", "alias": "reserved3", "label": "保留字段 3", "editable": False, "reserved": True},
]
EDITABLE_RECORD_FIELDS = [entry["name"] for entry in FIELD_META if entry.get("editable")]


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
    sidecar_meta: dict,
    point_palette: list[str],
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
        "fieldMeta": FIELD_META,
        "editableLayers": list(EDITABLE_LAYERS),
        "resourceLayers": list(EDITABLE_LAYERS),
        "pointLayers": list(POINT_LAYER_FIELDS),
        "editableRecordFields": EDITABLE_RECORD_FIELDS,
        "palette": palette_source,
        "pointPalette": point_palette,
        "image": image_name,
        "minimap": {"image": minimap_name, "source": "rendered-map", "sync": "derived-from-m-records"},
        "sidecars": sidecar_meta,
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
        tile, diamond_mask = make_diamond_tile(entry["pixels"], palette)
        alpha = diamond_mask if layer == "acwx" else None
        image = indexed_to_rgba(tile, alpha)
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


def pack_fixed_atlas(items: list[tuple[int, Image.Image, dict]], cell_size: tuple[int, int]) -> tuple[Image.Image, dict[int, list[int]]]:
    cell_w, cell_h = cell_size
    cols = 32
    rows = max(1, (len(items) + cols - 1) // cols)
    atlas = Image.new("RGBA", (cols * cell_w, rows * cell_h), (0, 0, 0, 0))
    rects: dict[int, list[int]] = {}
    for n, (index, image, _meta) in enumerate(items):
        x = (n % cols) * cell_w
        y = (n // cols) * cell_h
        atlas.alpha_composite(image, (x, y))
        rects[index] = [x, y, image.width, image.height]
    return atlas, rects


def pack_shelf_atlas(items: list[tuple[int, Image.Image, dict]], max_width: int = 4096, pad: int = 1) -> tuple[Image.Image, dict[int, list[int]]]:
    shelves: list[tuple[int, int, list[tuple[int, int, Image.Image]]]] = []
    x = 0
    y = 0
    shelf_h = 0
    current: list[tuple[int, int, Image.Image]] = []
    rects: dict[int, list[int]] = {}
    for index, image, _meta in items:
        w, h = image.size
        if x and x + w > max_width:
            shelves.append((y, shelf_h, current))
            y += shelf_h + pad
            x = 0
            shelf_h = 0
            current = []
        current.append((x, index, image))
        rects[index] = [x, y, w, h]
        x += w + pad
        shelf_h = max(shelf_h, h)
    if current:
        shelves.append((y, shelf_h, current))
    height = max(1, y + shelf_h)
    atlas = Image.new("RGBA", (max_width, height), (0, 0, 0, 0))
    for shelf_y, _shelf_h, shelf_items in shelves:
        for item_x, _index, image in shelf_items:
            atlas.alpha_composite(image, (item_x, shelf_y))
    used_width = max((rect[0] + rect[2] for rect in rects.values()), default=1)
    return atlas.crop((0, 0, used_width, height)), rects


def layer_usage(records: list[list[int]], layer: str) -> dict[int, int]:
    field = FIELD_NAMES.index(layer)
    usage: dict[int, int] = {}
    for record in records:
        value = record[field]
        if value >= 0:
            usage[value] = usage.get(value, 0) + 1
    return usage


def export_resource_catalog(blocks: dict, palette: list[int], stage_dir: Path, records: list[list[int]]) -> dict:
    catalog = {"format": "san-editor-resources-v2", "layers": {}}
    usage_by_layer = {layer: layer_usage(records, layer) for layer in EDITABLE_LAYERS}
    for layer in EDITABLE_LAYERS:
        box = 56 if layer != "acwz" else 72
        cols = 16 if layer != "acwz" else 12
        entries = []
        sprites: list[tuple[int, Image.Image, dict]] = []
        draw_items: list[tuple[int, Image.Image, dict]] = []
        usage = usage_by_layer[layer]
        for index, entry in enumerate(blocks[layer]["entries"]):
            if entry is None:
                continue
            image, meta = build_resource_image(layer, entry, palette)
            meta["used"] = usage.get(index, 0)
            sprites.append((index, fit_thumbnail(image, box), meta.copy()))
            draw_items.append((index, image, meta.copy()))
        sprites.sort(key=lambda item: item[0])
        draw_items.sort(key=lambda item: item[0])
        if layer in ("acwx", "acwy"):
            draw_atlas, draw_rects = pack_fixed_atlas(draw_items, (40, 20))
        else:
            draw_atlas, draw_rects = pack_shelf_atlas(draw_items)
        draw_image_name = f"draw_{layer}.png"
        draw_atlas.save(stage_dir / draw_image_name)
        rows = max(1, (len(sprites) + cols - 1) // cols)
        atlas = Image.new("RGBA", (cols * box, rows * box), (0, 0, 0, 0))
        draw = ImageDraw.Draw(atlas)
        for n, (index, thumb, meta) in enumerate(sprites):
            x = (n % cols) * box
            y = (n // cols) * box
            atlas.alpha_composite(thumb, (x, y))
            draw.text((x + 3, y + box - 12), str(index), fill=(255, 255, 255, 230), stroke_width=1, stroke_fill=(0, 0, 0, 220))
            entries.append({"index": index, "atlas": [x, y, box, box], "draw": draw_rects[index], **meta})
        image_name = f"resources_{layer}.png"
        atlas.save(stage_dir / image_name)
        catalog["layers"][layer] = {"image": image_name, "drawImage": draw_image_name, "tileSize": box, "columns": cols, "entries": entries}
    (stage_dir / "resources.json").write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return catalog


def export_minimap(map_path: Path, out_path: Path, max_width: int = 280) -> None:
    image = Image.open(map_path).convert("RGB")
    scale = max_width / image.width
    size = (max_width, max(1, round(image.height * scale)))
    image.resize(size, Image.Resampling.BILINEAR).save(out_path)


def build_sidecar_export_meta(
    game_dir: Path,
    stage_name: str,
    grid_size: int = GRID_SIZE,
    active_rows: int = ACTIVE_ROWS,
) -> dict:
    """为编辑页导出 `.s/.x` 准备参考尾区。"""

    cut = grid_size * active_rows
    tails: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    for suffix in ("s", "x"):
        reference_path = game_dir / f"{stage_name}.{suffix}"
        if not reference_path.exists():
            missing.append(suffix)
            continue
        blob = reference_path.read_bytes()
        validate_sidecar_blob(blob, grid_size)
        tail = blob[cut:]
        tails[suffix] = {
            "reference": str(reference_path),
            "tailBase64": base64.b64encode(tail).decode("ascii"),
            "tailBytes": len(tail),
        }
    available = len(tails) == 2 and not missing
    meta = {
        "available": available,
        "gridSize": grid_size,
        "activeRows": active_rows,
        "tailRows": grid_size - active_rows,
        "referenceStem": stage_name,
        "tails": tails,
    }
    if not available:
        missing_text = ", ".join(f".{suffix}" for suffix in missing) if missing else "参考尾区"
        meta["reason"] = f"当前关卡缺少完整的 {missing_text} 参考文件，编辑页导出 `.s/.x` 时会对尾区使用 0 填充。"
    return meta


def resolve_editor_template(root: Path) -> Path:
    """只使用源码目录内的编辑器模板，避免继续依赖 tools 包装层。"""

    candidate = Path(__file__).with_name("editor_app.html")
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"找不到编辑器模板：{candidate}")


def write_editor_index(out_dir: Path, stages: list[dict]) -> None:
    options = "\n".join(
        f'<option value="{entry["path"]}">{entry["stage"]} ({entry["width"]}x{entry["height"]})</option>'
        for entry in stages
    )
    html = (
        '<!doctype html>\n<html lang="zh-CN">\n<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>San 地图编辑器索引</title>'
        '<style>body{font-family:Segoe UI,Arial,sans-serif;margin:32px;background:#f4f2ec;color:#202124}'
        'main{max-width:720px}select,button{height:32px;font:inherit}select{min-width:260px}a{color:#0f766e}</style></head>'
        '<body><main><h1>San 地图编辑器</h1><p>选择已经导出的关卡编辑页。</p>'
        f'<select id="stage">{options}</select> <button id="open">打开</button>'
        '<p><a href="index.json">index.json</a></p></main>'
        "<script>document.getElementById('open').onclick=()=>{const v=document.getElementById('stage').value;if(v) location.href=v;};</script>"
        '</body></html>\n'
    )
    (out_dir / "index.html").write_text(html, encoding="utf-8")


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
    sidecar_meta = build_sidecar_export_meta(game_dir, stage, GRID_SIZE, ACTIVE_ROWS)

    export_resource_catalog(blocks, palette, stage_dir, records)
    export_minimap(map_path, stage_dir / "minimap.png")
    write_stage_json(
        stage_dir / "stage.json",
        stage,
        width,
        height,
        records,
        layout,
        (ox, oy),
        "map.png",
        "minimap.png",
        render_meta,
        palette_source,
        sidecar_meta,
        PAINT_RGB_FLAG_PALETTE,
    )
    template = resolve_editor_template(root)
    shutil.copyfile(template, stage_dir / "editor.html")

    index_path = out_dir / "index.json"
    existing = {"stages": []}
    if index_path.exists():
        existing = json.loads(index_path.read_text(encoding="utf-8"))
    stages = {entry["stage"]: entry for entry in existing.get("stages", [])}
    stages[stage] = {"stage": stage, "path": f"{stage}/editor.html", "width": width, "height": height}
    existing["stages"] = sorted(stages.values(), key=lambda item: item["stage"])
    index_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    write_editor_index(out_dir, existing["stages"])

    return {"stage": stage, "width": width, "height": height, "out": str(stage_dir), "records": len(records)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", default="stage11")
    parser.add_argument("--all", action="store_true", help="Export editor bundles for every stage*.m file")
    parser.add_argument("--out", default="derived/editor", type=Path)
    parser.add_argument("--layout", choices=["stagger"], default="stagger")
    parser.add_argument("--layers", default="xyz")
    parser.add_argument("--palette", default=DEFAULT_PALETTE_SOURCE)
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    if args.all:
        game_dir = find_game_dir(root)
        results = []
        for stage_path in sorted(game_dir.glob("stage*.m")):
            results.append(export_editor_bundle(root, stage_path.stem, out_dir, args.layout, args.layers, args.palette))
        print(json.dumps({"count": len(results), "stages": results}, ensure_ascii=False))
    else:
        result = export_editor_bundle(root, args.stage, out_dir, args.layout, args.layers, args.palette)
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
