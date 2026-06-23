from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from PIL import Image

from extract_kingdom import find_game_dir, load_palette

DIAMOND_ROWS = [
    (19, 0, 2), (17, 2, 6), (15, 8, 10), (13, 18, 14), (11, 32, 18),
    (9, 50, 22), (7, 72, 26), (5, 98, 30), (3, 128, 34), (1, 162, 38),
    (1, 200, 38), (3, 238, 34), (5, 272, 30), (7, 302, 26), (9, 328, 22),
    (11, 350, 18), (13, 368, 14), (15, 382, 10), (17, 392, 6), (19, 398, 2),
]


def parse_counted_cel(path: Path):
    blob = path.read_bytes()
    offset = 0
    blocks = {}
    for code in ["acwx", "acwy", "acwz"]:
        count = struct.unpack_from("<I", blob, offset)[0]
        offset += 4
        entries = []
        for index in range(count):
            marker = blob[offset : offset + 4]
            offset += 4
            if marker == b"\x00\x00\x00\x00":
                entries.append(None)
                continue
            marker_text = marker.decode("ascii", errors="replace")
            if marker_text != code:
                raise ValueError(f"Unexpected marker {marker_text!r} in {code} block at {index}, offset {offset-4:#x}")
            if code in ("acwx", "acwy"):
                pixels = blob[offset : offset + 400]
                offset += 400
                entries.append({"pixels": pixels})
            else:
                x_anchor, y_anchor, width, height, ptr = struct.unpack_from("<IIIII", blob, offset)
                offset += 20
                size = width * height
                pixels = blob[offset : offset + size]
                offset += size
                entries.append({
                    "x_anchor": x_anchor,
                    "y_anchor": y_anchor,
                    "width": width,
                    "height": height,
                    "pixels": pixels,
                })
        blocks[code] = {"count": count, "entries": entries}
    return blocks


def parse_stage_m(path: Path):
    blob = path.read_bytes()
    width, height = struct.unpack_from("<II", blob, 0)
    if blob[8:16] != b"Hello1.0":
        raise ValueError(f"not a stage .m file: {path}")
    return width, height, blob


def make_diamond_tile(pixels: bytes, palette: list[int]) -> Image.Image:
    tile = Image.new("P", (40, 20), 0)
    tile.putpalette(palette)
    for y, (x0, src, length) in enumerate(DIAMOND_ROWS):
        row = Image.frombytes("P", (length, 1), pixels[src : src + length])
        row.putpalette(palette)
        tile.paste(row, (x0, y))
    return tile


def make_object(entry: dict, palette: list[int]) -> Image.Image:
    image = Image.frombytes("P", (entry["width"], entry["height"]), entry["pixels"])
    image.putpalette(palette)
    return image


def mask_nonzero(image: Image.Image) -> Image.Image:
    return image.point(lambda value: 255 if value else 0).convert("L")


def paste_keyed(dst: Image.Image, src: Image.Image, xy: tuple[int, int]) -> None:
    x, y = xy
    left = max(0, x)
    top = max(0, y)
    right = min(dst.width, x + src.width)
    bottom = min(dst.height, y + src.height)
    if right <= left or bottom <= top:
        return
    crop_box = (left - x, top - y, right - x, bottom - y)
    cropped = src.crop(crop_box)
    dst.paste(cropped, (left, top), mask_nonzero(cropped))


def build_tile_cache(block, palette: list[int]) -> list[Image.Image | None]:
    cache = []
    for entry in block["entries"]:
        cache.append(None if entry is None else make_diamond_tile(entry["pixels"], palette))
    return cache


def build_object_cache(block, palette: list[int]) -> list[Image.Image | None]:
    cache = []
    for entry in block["entries"]:
        cache.append(None if entry is None else make_object(entry, palette))
    return cache


def canvas_size(width: int, height: int, layout: str) -> tuple[int, int, int, int]:
    if layout == "rect":
        return width * 40, height * 20, 0, 0
    # Standard diamond isometric placement for comparison.
    ox = (height - 1) * 20 + 64
    oy = 64
    return (width + height) * 20 + 128, (width + height) * 10 + 128, ox, oy


def cell_xy(x: int, y: int, layout: str, ox: int, oy: int) -> tuple[int, int]:
    if layout == "rect":
        return x * 40, y * 20
    return ox + (x - y) * 20, oy + (x + y) * 10


def render_stage(stage_path: Path, blocks, palette: list[int], out_path: Path, layout: str, layers: str, max_cells: int | None) -> dict:
    width, height, blob = parse_stage_m(stage_path)
    if max_cells is not None:
        height = min(height, max_cells // max(1, width))
    out_w, out_h, ox, oy = canvas_size(width, height, layout)
    image = Image.new("P", (out_w, out_h), 0)
    image.putpalette(palette)

    acwx = build_tile_cache(blocks["acwx"], palette)
    acwy = build_tile_cache(blocks["acwy"], palette)
    acwz = build_object_cache(blocks["acwz"], palette)
    stats = {"acwx": 0, "acwy": 0, "acwz": 0, "acwz_missing": 0}

    # Pass 1: base terrain.
    if "x" in layers:
        for y in range(height):
            for x in range(width):
                record = 16 + (y * width + x) * 16
                idx = struct.unpack_from("<h", blob, record)[0]
                if 0 <= idx < len(acwx) and acwx[idx] is not None:
                    px, py = cell_xy(x, y, layout, ox, oy)
                    paste_keyed(image, acwx[idx], (px, py))
                    stats["acwx"] += 1

    # Pass 2: overlay/transition.
    if "y" in layers:
        for y in range(height):
            for x in range(width):
                record = 16 + (y * width + x) * 16
                idx = struct.unpack_from("<h", blob, record + 2)[0]
                if 0 <= idx < len(acwy) and acwy[idx] is not None:
                    px, py = cell_xy(x, y, layout, ox, oy)
                    paste_keyed(image, acwy[idx], (px, py))
                    stats["acwy"] += 1

    # Pass 3: objects. This is still first-pass placement; exact z-order/footprints need more exe work.
    if "z" in layers:
        for y in range(height):
            for x in range(width):
                record = 16 + (y * width + x) * 16
                idx = struct.unpack_from("<h", blob, record + 4)[0]
                if idx < 0:
                    continue
                if not (0 <= idx < len(acwz)) or acwz[idx] is None:
                    stats["acwz_missing"] += 1
                    continue
                entry = blocks["acwz"]["entries"][idx]
                obj = acwz[idx]
                px, py = cell_xy(x, y, layout, ox, oy)
                # Emperor.exe uses dest_x = screen_x - header0, dest_y = screen_y - header1.
                paste_keyed(image, obj, (px + 20 - entry["x_anchor"], py + 20 - entry["y_anchor"]))
                stats["acwz"] += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    meta = {"stage": stage_path.stem, "width_cells": width, "height_cells": height, "layout": layout, "layers": layers, "output_size": [out_w, out_h], "stats": stats}
    out_path.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", default="stage20")
    parser.add_argument("--layout", choices=["rect", "iso"], default="rect")
    parser.add_argument("--layers", default="xyz", help="Include x=acwx, y=acwy, z=acwz")
    parser.add_argument("--out", default="derived/cel_maps", type=Path)
    parser.add_argument("--palette", default="stage.bmp")
    parser.add_argument("--max-cells", type=int, default=None, help="Optional crop by maximum number of records from top of map")
    args = parser.parse_args()

    root = args.root.resolve()
    game_dir = find_game_dir(root)
    palette = load_palette(game_dir, args.palette)
    blocks = parse_counted_cel(game_dir / "kingdom.cel")
    stage_path = game_dir / f"{args.stage}.m"
    out_dir = args.out if args.out.is_absolute() else root / args.out
    suffix = f"{args.stage}_{args.layout}_{args.layers}"
    if args.max_cells:
        suffix += f"_crop{args.max_cells}"
    meta = render_stage(stage_path, blocks, palette, out_dir / f"{suffix}.png", args.layout, args.layers, args.max_cells)
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

