from __future__ import annotations

import argparse

from PIL import Image, ImageDraw

from extract_kingdom import find_game_dir, load_palette, parse_cel


DEFAULT_ACWZ_GROUPS = [
    (0, 12),
    (12, 22),
    (22, 33),
    (33, 45),
    (45, 55),
    (55, 67),
    (67, 77),
    (77, 87),
    (87, 98),
    (98, 109),
    (109, 120),
    (120, 131),
    (131, 145),
    (145, 154),
    (154, 164),
]


def chunk_image(blob: bytes, chunk: dict[str, int | str], palette: list[int]) -> Image.Image:
    width = int(chunk["width"])
    height = int(chunk["height"])
    data_offset = int(chunk["data_offset"])
    image = Image.frombytes("P", (width, height), blob[data_offset : data_offset + width * height])
    image.putpalette(palette)
    return image


def compose_acwz(
    blob: bytes,
    chunks: list[dict[str, int | str]],
    group: tuple[int, int],
    palette: list[int],
    align: str,
) -> Image.Image:
    selected = chunks[group[0] : group[1]]
    widths = [int(chunk["width"]) for chunk in selected]
    heights = [int(chunk["height"]) for chunk in selected]
    total_width = sum(widths)
    max_height = max(heights)
    image = Image.new("P", (total_width, max_height), 0)
    image.putpalette(palette)

    x = 0
    for chunk, width, height in zip(selected, widths, heights):
        strip = chunk_image(blob, chunk, palette)
        if align == "bottom":
            y = max_height - height
        elif align == "top":
            y = 0
        else:
            y = (max_height - height) // 2
        image.paste(strip, (x, y))
        x += width
    return image


def save_acwz_sheet(
    blob: bytes,
    chunks: list[dict[str, int | str]],
    groups: list[tuple[int, int]],
    palette: list[int],
    out_path: Path,
    align: str,
) -> None:
    sprites = [compose_acwz(blob, chunks, group, palette, align) for group in groups]
    cols = 3
    cell_w = max(sprite.width for sprite in sprites) + 32
    cell_h = max(sprite.height for sprite in sprites) + 24
    rows = (len(sprites) + cols - 1) // cols
    sheet = Image.new("P", (cols * cell_w, rows * cell_h), 0)
    sheet.putpalette(palette)
    draw = ImageDraw.Draw(sheet)
    for index, (group, sprite) in enumerate(zip(groups, sprites)):
        col = index % cols
        row = index // cols
        x = col * cell_w + (cell_w - sprite.width) // 2
        y = row * cell_h + 16 + (cell_h - 16 - sprite.height) // 2
        sheet.paste(sprite, (x, y))
        draw.text((col * cell_w + 4, row * cell_h + 2), f"{index}: {group[0]}:{group[1]}", fill=255)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def save_meta_sheet(
    blob: bytes,
    chunks: list[dict[str, int | str]],
    code: str,
    palette: list[int],
    out_path: Path,
    block: int,
) -> None:
    selected = [chunk for chunk in chunks if chunk["code"] == code]
    tile_count = block * block
    groups = [selected[index : index + tile_count] for index in range(0, len(selected), tile_count)]
    groups = [group for group in groups if len(group) == tile_count]
    if not groups:
        return
    tile_w = int(groups[0][0]["width"])
    tile_h = int(groups[0][0]["height"])
    meta_w = tile_w * block
    meta_h = tile_h * block
    cols = 6
    label_h = 10
    rows = (len(groups) + cols - 1) // cols
    sheet = Image.new("P", (cols * meta_w, rows * (meta_h + label_h)), 0)
    sheet.putpalette(palette)
    draw = ImageDraw.Draw(sheet)
    for index, group in enumerate(groups):
        x0 = (index % cols) * meta_w
        y0 = (index // cols) * (meta_h + label_h)
        draw.text((x0, y0), str(index), fill=255)
        for tile_index, chunk in enumerate(group):
            image = chunk_image(blob, chunk, palette)
            x = x0 + (tile_index % block) * tile_w
            y = y0 + label_h + (tile_index // block) * tile_h
            sheet.paste(image, (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--out", default="derived/kingdom", type=Path)
    parser.add_argument("--palette", default="SAN_RGB_PALETTE")
    parser.add_argument("--acwz-align", choices=["center", "bottom", "top"], default="center")
    args = parser.parse_args()

    root = args.root.resolve()
    game_dir = find_game_dir(root)
    out_dir = args.out if args.out.is_absolute() else root / args.out
    palette = load_palette(game_dir, args.palette)
    blob = (game_dir / "kingdom.cel").read_bytes()
    chunks = parse_cel(game_dir / "kingdom.cel")
    acwz_chunks = [chunk for chunk in chunks if chunk["code"] == "acwz"]

    save_acwz_sheet(
        blob,
        acwz_chunks,
        DEFAULT_ACWZ_GROUPS,
        palette,
        out_dir / f"acwz_stitched_city_{args.acwz_align}.png",
        args.acwz_align,
    )
    save_meta_sheet(blob, chunks, "acwx", palette, out_dir / "acwx_meta_6x6_sheet.png", 6)
    save_meta_sheet(blob, chunks, "acwy", palette, out_dir / "acwy_meta_6x6_sheet.png", 6)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
