from __future__ import annotations

import argparse
import collections
import json
import struct
from pathlib import Path

from PIL import Image

from extract_kingdom import find_game_dir, load_palette

BLOCKS = ["acwx", "acwy", "acwz"]


def parse_counted_atr(path: Path):
    blob = path.read_bytes()
    offset = 0
    blocks = []
    for expected in BLOCKS:
        count = struct.unpack_from("<I", blob, offset)[0]
        offset += 4
        entries = []
        present = 0
        for index in range(count):
            marker = blob[offset : offset + 4]
            offset += 4
            if marker == b"\x00\x00\x00\x00":
                entries.append(None)
                continue
            attr_lo = blob[offset]
            attr_hi = blob[offset + 1]
            offset += 2
            code = marker.decode("ascii", errors="replace")
            if code != expected:
                raise ValueError(f"Unexpected ATR marker {code!r} in {expected} block at index {index}")
            entries.append({"code": code, "attr_lo": attr_lo, "attr_hi": attr_hi})
            present += 1
        blocks.append({"code": expected, "count": count, "present": present, "entries": entries})
    return blocks


def parse_stage_m(path: Path):
    blob = path.read_bytes()
    width, height = struct.unpack_from("<II", blob, 0)
    if blob[8:16] != b"Hello1.0":
        raise ValueError(f"{path.name} is not a recognized .m map")
    expected = 16 + width * height * 16
    if len(blob) != expected:
        raise ValueError(f"{path.name} size mismatch: {len(blob)} != {expected}")
    return width, height, blob


def write_i16(path: Path, values) -> None:
    with path.open("wb") as handle:
        for value in values:
            handle.write(struct.pack("<h", value))


def attr_pixels(values, block):
    entries = block["entries"]
    count = block["count"]
    out = bytearray()
    present = 0
    missing = 0
    neg = 0
    oor = 0
    attr_match_counter = collections.Counter()
    for value, final in values:
        if value < 0:
            out.append(0)
            neg += 1
        elif value >= count:
            out.append(0)
            oor += 1
        elif entries[value] is None:
            out.append(0)
            missing += 1
        else:
            attr = entries[value]["attr_hi"]
            out.append(attr)
            present += 1
            attr_match_counter[attr == final] += 1
    return bytes(out), {"neg": neg, "oor": oor, "missing": missing, "present": present, "attr_match": attr_match_counter[True]}


def export_stage(path: Path, out_dir: Path, palette: list[int], atr_blocks) -> dict:
    width, height, blob = parse_stage_m(path)
    count = width * height
    layers = {"acwx": [], "acwy": [], "acwz": []}
    aux = {"byte08": bytearray(), "byte09": bytearray(), "byte10": bytearray(), "byte11": bytearray(), "final_palette": bytearray()}
    field_common = {name: collections.Counter() for name in layers}
    byte_common = {name: collections.Counter() for name in aux}

    for index in range(count):
        offset = 16 + index * 16
        f0, f1, f2 = struct.unpack_from("<hhh", blob, offset)
        values = [f0, f1, f2]
        final = blob[offset + 13]
        for name, value in zip(BLOCKS, values):
            layers[name].append(value)
            field_common[name][value] += 1
        aux["byte08"].append(blob[offset + 8])
        aux["byte09"].append(blob[offset + 9])
        aux["byte10"].append(blob[offset + 10])
        aux["byte11"].append(blob[offset + 11])
        aux["final_palette"].append(final)
        for name in aux:
            byte_common[name][aux[name][-1]] += 1

    stage_dir = out_dir / path.stem
    stage_dir.mkdir(parents=True, exist_ok=True)
    layer_stats = {}
    for name, block in zip(BLOCKS, atr_blocks):
        write_i16(stage_dir / f"{name}.i16", layers[name])
        pixels, stats = attr_pixels(zip(layers[name], aux["final_palette"]), block)
        image = Image.frombytes("P", (width, height), pixels)
        image.putpalette(palette)
        image.save(stage_dir / f"{name}_attr.png")
        layer_stats[name] = stats | {"common": field_common[name].most_common(16)}

    for name, data in aux.items():
        (stage_dir / f"{name}.bin").write_bytes(bytes(data))
        if name == "final_palette":
            image = Image.frombytes("P", (width, height), bytes(data))
            image.putpalette(palette)
            image.save(stage_dir / "final_palette.png")
        else:
            image = Image.frombytes("L", (width, height), bytes(data))
            image.save(stage_dir / f"{name}.png")

    meta = {
        "stage": path.stem,
        "width": width,
        "height": height,
        "record_size": 16,
        "schema": {
            "int16_00": "acwx base tile index; indexes kingdom acwx block, count 6480",
            "int16_02": "acwy overlay/transition index, -1 when absent; indexes kingdom acwy block, count 8640",
            "int16_04": "acwz object/building strip index, -1 when absent; indexes kingdom acwz block, count 17280",
            "bytes_06_07": "observed zero in exported .m files",
            "byte_08": "aux/flag byte, often 0 or terrain/object class",
            "byte_09": "aux/flag byte, commonly 0 or 1",
            "byte_10": "variant/object byte; Emperor.exe uses record+0x0a in acwz variation logic",
            "byte_11": "small group/subindex byte; often repeated in 36-cell blocks",
            "byte_12": "observed zero in exported .m files",
            "byte_13": "final rendered palette index",
            "bytes_14_15": "observed zero in exported .m files; runtime renderer checks related flag bytes in its in-memory record structure",
        },
        "layers": layer_stats,
        "aux_common": {name: byte_common[name].most_common(16) for name in aux},
    }
    (stage_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--out", default="derived/m_layers", type=Path)
    parser.add_argument("--palette", default="stage.bmp")
    args = parser.parse_args()

    root = args.root.resolve()
    game_dir = find_game_dir(root)
    out_dir = args.out if args.out.is_absolute() else root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    palette = load_palette(game_dir, args.palette)
    atr_blocks = parse_counted_atr(game_dir / "kingdom.atr")

    summary_rows = []
    for path in sorted(game_dir.glob("stage*.m")):
        meta = export_stage(path, out_dir, palette, atr_blocks)
        row = [meta["stage"], str(meta["width"]), str(meta["height"])]
        for name in BLOCKS:
            stats = meta["layers"][name]
            total = meta["width"] * meta["height"]
            row.extend(str(stats[key]) for key in ["neg", "oor", "missing", "present", "attr_match"])
            row.append(f"{stats['present'] / total:.6f}")
        summary_rows.append(row)
        print(meta["stage"], meta["width"], meta["height"], {name: meta["layers"][name]["present"] for name in BLOCKS})

    header = ["stage", "width", "height"]
    for name in BLOCKS:
        header.extend([f"{name}_neg", f"{name}_oor", f"{name}_missing", f"{name}_present", f"{name}_attr_match", f"{name}_present_ratio"])
    with (out_dir / "m_record_summary.tsv").open("w", encoding="utf-8") as handle:
        handle.write("\t".join(header) + "\n")
        for row in summary_rows:
            handle.write("\t".join(row) + "\n")

    kingdom_meta = {
        "atr_blocks": [{"code": block["code"], "count": block["count"], "present": block["present"]} for block in atr_blocks],
        "note": "Fields are interpreted from Emperor.exe counted CEL/ATR blocks, not from a mixed acwx/acwy/acwz scan.",
    }
    (out_dir / "kingdom_blocks.json").write_text(json.dumps(kingdom_meta, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
