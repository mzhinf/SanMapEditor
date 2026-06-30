from __future__ import annotations

import argparse
import collections
import math
import struct

from PIL import Image, ImageDraw

try:
    from palette import SAN_RGB_PALETTE
except ImportError:
    from san_tools.map.palette import SAN_RGB_PALETTE

DEFAULT_PALETTE_SOURCE = "SAN_RGB_PALETTE"

VALID_CODES = {b"acwx", b"acwy", b"acwz"}


def find_game_dir(root: Path) -> Path:
    if (root / "Emperor.exe").exists():
        return root
    for child in root.iterdir():
        if child.is_dir() and (child / "Emperor.exe").exists():
            return child
    raise FileNotFoundError("Could not find game directory containing Emperor.exe")


def load_palette(game_dir: Path, palette_source: str | None = DEFAULT_PALETTE_SOURCE) -> list[int]:
    if palette_source in (None, "", DEFAULT_PALETTE_SOURCE, "san", "SAN"):
        return [c for rgb in SAN_RGB_PALETTE for c in rgb]
    palette = Image.open(game_dir / palette_source).getpalette()
    if not palette:
        raise ValueError(f"{palette_source} has no palette")
    return (palette + [0] * 768)[:768]


def parse_atr(path: Path) -> list[dict[str, int | str]]:
    blob = path.read_bytes()
    records = []
    offset = 4
    while offset + 6 <= len(blob):
        code = blob[offset : offset + 4]
        if code in VALID_CODES:
            records.append(
                {
                    "code": code.decode("ascii"),
                    "offset": offset,
                    "attr_lo": blob[offset + 4],
                    "attr_hi": blob[offset + 5],
                }
            )
            offset += 6
        else:
            offset += 1
    return records


def parse_cel(path: Path) -> list[dict[str, int | str]]:
    blob = path.read_bytes()
    chunks = []
    offset = 4
    while offset + 4 <= len(blob):
        code = blob[offset : offset + 4]
        if code in (b"acwx", b"acwy") and offset + 404 <= len(blob):
            chunks.append(
                {
                    "code": code.decode("ascii"),
                    "offset": offset,
                    "width": 20,
                    "height": 20,
                    "data_offset": offset + 4,
                    "size": 404,
                }
            )
            offset += 404
            continue
        if code == b"acwz" and offset + 24 <= len(blob):
            x0, y0, width, height, ptr = struct.unpack_from("<IIIII", blob, offset + 4)
            size = 24 + width * height
            if 0 < width <= 500 and 0 < height <= 500 and offset + size <= len(blob):
                chunks.append(
                    {
                        "code": "acwz",
                        "offset": offset,
                        "x0": x0,
                        "y0": y0,
                        "width": width,
                        "height": height,
                        "data_offset": offset + 24,
                        "size": size,
                        "ptr": ptr,
                    }
                )
                offset += size
                continue
        offset += 1
    return chunks


def save_sheet(
    blob: bytes,
    chunks: list[dict[str, int | str]],
    code: str,
    palette: list[int],
    out_path: Path,
    limit: int,
) -> None:
    selected = [chunk for chunk in chunks if chunk["code"] == code][:limit]
    if not selected:
        return
    max_w = max(int(chunk["width"]) for chunk in selected)
    max_h = max(int(chunk["height"]) for chunk in selected)
    cols = 30 if code in ("acwx", "acwy") else 12
    pad = 2
    label_h = 8
    rows = math.ceil(len(selected) / cols)
    sheet = Image.new("P", (cols * (max_w + pad * 2), rows * (max_h + pad * 2 + label_h)), 0)
    sheet.putpalette(palette)
    draw = ImageDraw.Draw(sheet)
    for index, chunk in enumerate(selected):
        width = int(chunk["width"])
        height = int(chunk["height"])
        data_offset = int(chunk["data_offset"])
        pixels = blob[data_offset : data_offset + width * height]
        image = Image.frombytes("P", (width, height), pixels)
        image.putpalette(palette)
        x = (index % cols) * (max_w + pad * 2) + pad
        y = (index // cols) * (max_h + pad * 2 + label_h) + pad + label_h
        sheet.paste(image, (x, y))
        draw.text((x, y - label_h), str(index), fill=255)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def export_field0_maps(game_dir: Path, atr_records: list[dict[str, int | str]], palette: list[int], out_dir: Path) -> None:
    attrs = [int(record["attr_hi"]) for record in atr_records]
    for path in sorted(game_dir.glob("stage*.m")):
        blob = path.read_bytes()
        width, height = struct.unpack_from("<II", blob, 0)
        if blob[8:16] != b"Hello1.0":
            continue
        pixels = bytearray()
        same = 0
        for index in range(width * height):
            record = blob[16 + index * 16 : 32 + index * 16]
            tile_id = struct.unpack_from("<h", record, 0)[0]
            value = attrs[tile_id] if 0 <= tile_id < len(attrs) else 0
            pixels.append(value)
            if value == record[13]:
                same += 1
        image = Image.frombytes("P", (width, height), bytes(pixels))
        image.putpalette(palette)
        image.save(out_dir / f"{path.stem}_field0_attr.png")
        print(f"{path.stem}: field0_attr_match={same}/{width * height} ({same/(width*height):.3f})")


def write_tables(out_dir: Path, atr_records: list[dict[str, int | str]], cel_chunks: list[dict[str, int | str]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "kingdom_atr_records.tsv").open("w", encoding="ascii") as handle:
        handle.write("index\tcode\toffset\tattr_lo\tattr_hi\n")
        for index, record in enumerate(atr_records):
            handle.write(
                f"{index}\t{record['code']}\t{record['offset']}\t{record['attr_lo']}\t{record['attr_hi']}\n"
            )
    with (out_dir / "kingdom_cel_chunks.tsv").open("w", encoding="ascii") as handle:
        handle.write("index\tcode\toffset\twidth\theight\tdata_offset\tsize\n")
        for index, chunk in enumerate(cel_chunks):
            handle.write(
                f"{index}\t{chunk['code']}\t{chunk['offset']}\t{chunk['width']}\t{chunk['height']}\t{chunk['data_offset']}\t{chunk['size']}\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--out", default="derived/kingdom", type=Path)
    parser.add_argument("--palette", default="SAN_RGB_PALETTE")
    parser.add_argument("--sheet-limit", type=int, default=240)
    args = parser.parse_args()

    game_dir = find_game_dir(args.root.resolve())
    out_dir = args.out if args.out.is_absolute() else args.root.resolve() / args.out
    palette = load_palette(game_dir, args.palette)
    cel_blob = (game_dir / "kingdom.cel").read_bytes()
    atr_records = parse_atr(game_dir / "kingdom.atr")
    cel_chunks = parse_cel(game_dir / "kingdom.cel")

    print("ATR records", len(atr_records), collections.Counter(record["code"] for record in atr_records))
    print("CEL chunks", len(cel_chunks), collections.Counter(chunk["code"] for chunk in cel_chunks))
    write_tables(out_dir, atr_records, cel_chunks)
    save_sheet(cel_blob, cel_chunks, "acwx", palette, out_dir / "cel_acwx_sheet.png", args.sheet_limit)
    save_sheet(cel_blob, cel_chunks, "acwy", palette, out_dir / "cel_acwy_sheet.png", args.sheet_limit)
    save_sheet(cel_blob, cel_chunks, "acwz", palette, out_dir / "cel_acwz_sheet.png", min(args.sheet_limit, 120))
    export_field0_maps(game_dir, atr_records, palette, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
