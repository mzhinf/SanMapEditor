from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw


def find_game_dir(root: Path) -> Path:
    if (root / "Emperor.exe").exists():
        return root
    for child in root.iterdir():
        if child.is_dir() and (child / "Emperor.exe").exists():
            return child
    raise FileNotFoundError("Could not find game directory containing Emperor.exe")


def load_palette(game_dir: Path, palette_source: str) -> list[int]:
    image = Image.open(game_dir / palette_source)
    palette = image.getpalette()
    if not palette:
        raise ValueError(f"{palette_source} does not contain a palette")
    return (palette + [0] * 768)[:768]


def save_indexed_image(width: int, height: int, pixels: bytes, palette: list[int], out: Path, scale: int = 1) -> None:
    image = Image.frombytes("P", (width, height), pixels)
    image.putpalette(palette)
    if scale != 1:
        image = image.resize((width * scale, height * scale), Image.Resampling.NEAREST)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)


def export_m_file(path: Path, palette: list[int], out_dir: Path) -> dict[str, int]:
    blob = path.read_bytes()
    width, height = struct.unpack_from("<II", blob, 0)
    magic = blob[8:16]
    if magic != b"Hello1.0":
        raise ValueError(f"{path.name}: unexpected .m magic {magic!r}")
    expected = 16 + width * height * 16
    if expected != len(blob):
        raise ValueError(f"{path.name}: size mismatch expected {expected}, got {len(blob)}")
    pixels = bytes(blob[16 + i * 16 + 13] for i in range(width * height))
    save_indexed_image(width, height, pixels, palette, out_dir / f"{path.stem}_m.png")
    return {"width": width, "height": height, "records": width * height}


def export_grid(path: Path, palette: list[int], out_dir: Path) -> None:
    blob = path.read_bytes()
    if len(blob) != 160 * 160:
        return
    save_indexed_image(160, 160, blob, palette, out_dir / f"{path.stem}_{path.suffix[1:]}.png", scale=3)


def dat_offsets(blob: bytes) -> list[int]:
    first = struct.unpack_from("<I", blob, 0)[0]
    if first <= 0 or first % 4 or first > len(blob):
        raise ValueError("not an offset-table DAT")
    table_count = first // 4
    raw = list(struct.unpack_from("<" + "I" * table_count, blob, 0))
    offsets = []
    last = -1
    for value in raw:
        if value <= last or value >= len(blob) or value == 0:
            break
        offsets.append(value)
        last = value
    if not offsets:
        raise ValueError("empty offset table")
    return offsets


def parse_dat_images(path: Path) -> list[Image.Image]:
    blob = path.read_bytes()
    offsets = dat_offsets(blob)
    images = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(blob)
        chunk = blob[start:end]
        if len(chunk) < 4:
            continue
        width, height = struct.unpack_from("<HH", chunk, 0)
        expected = 4 + width * height
        if width <= 0 or height <= 0 or expected > len(chunk):
            continue
        img = Image.frombytes("P", (width, height), chunk[4:expected])
        images.append(img)
    return images


def export_dat_sheet(path: Path, palette: list[int], out_dir: Path, limit: int = 80) -> dict[str, int]:
    images = parse_dat_images(path)
    selected = images[:limit]
    if not selected:
        return {"images": 0}
    pad = 2
    label_h = 10
    cell_w = max(img.width for img in selected) + pad * 2
    cell_h = max(img.height for img in selected) + pad * 2 + label_h
    cols = max(1, min(10, math.ceil(math.sqrt(len(selected)))))
    rows = math.ceil(len(selected) / cols)
    sheet = Image.new("P", (cols * cell_w, rows * cell_h), 0)
    sheet.putpalette(palette)
    draw = ImageDraw.Draw(sheet)
    for i, img in enumerate(selected):
        img.putpalette(palette)
        x = (i % cols) * cell_w + pad
        y = (i // cols) * cell_h + pad + label_h
        sheet.paste(img, (x, y))
        draw.text((x, y - label_h), str(i), fill=255)
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(out_dir / f"{path.stem}_sheet.png")
    return {"images": len(images), "exported": len(selected)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--palette", default="stage.bmp")
    parser.add_argument("--out", default="derived", type=Path)
    parser.add_argument("--stage", action="append", help="stage stem such as stage20; can be repeated")
    args = parser.parse_args()

    game_dir = find_game_dir(args.root.resolve())
    out_dir = (args.root.resolve() / args.out) if not args.out.is_absolute() else args.out
    palette = load_palette(game_dir, args.palette)
    stages = args.stage or sorted({path.stem for path in game_dir.glob("stage*.m")})

    print(f"game_dir={game_dir}")
    print(f"out_dir={out_dir}")
    for stem in stages:
        m_path = game_dir / f"{stem}.m"
        if m_path.exists():
            meta = export_m_file(m_path, palette, out_dir / "maps")
            print(f"exported {stem}.m {meta}")
        for suffix in [".s", ".x"]:
            grid = game_dir / f"{stem}{suffix}"
            if grid.exists():
                export_grid(grid, palette, out_dir / "grids")
                print(f"exported {grid.name} grid")

    for name in ["Graphics.dat", "Selects.dat", "windows.dat", "heads.dat"]:
        path = game_dir / name
        if path.exists():
            meta = export_dat_sheet(path, palette, out_dir / "dat_sheets")
            print(f"exported {name} {meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

