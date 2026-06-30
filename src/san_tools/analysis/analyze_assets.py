from __future__ import annotations

import argparse
import collections
import math
import re
import struct


INTERESTING = (
    "stage",
    "kingdom",
    "graphic",
    "select",
    "windows",
    "bmp",
    "dat",
    "cel",
    "atr",
    ".m",
    ".s",
    ".x",
    ".stg",
    ".spr",
    ".dor",
    ".evt",
    "wav",
    "txt",
)


def entropy(blob: bytes) -> float:
    if not blob:
        return 0.0
    counts = collections.Counter(blob)
    size = len(blob)
    return -sum((count / size) * math.log2(count / size) for count in counts.values())


def ascii_strings(blob: bytes, min_len: int = 4):
    pattern = rb"[\x20-\x7e]{%d,}" % min_len
    for match in re.finditer(pattern, blob):
        yield match.start(), match.group().decode("latin1", "replace")


def utf16le_strings(blob: bytes, min_len: int = 4):
    pattern = (rb"(?:[\x20-\x7e]\x00){%d,}") % min_len
    for match in re.finditer(pattern, blob):
        try:
            text = match.group().decode("utf-16le")
        except UnicodeDecodeError:
            continue
        yield match.start(), text


def parse_pe(blob: bytes):
    rows = []
    if blob[:2] != b"MZ" or len(blob) < 0x40:
        return ["not an MZ executable"]
    peoff = struct.unpack_from("<I", blob, 0x3C)[0]
    rows.append(f"MZ ok, PE header offset=0x{peoff:x}")
    if blob[peoff : peoff + 4] != b"PE\0\0":
        rows.append("PE signature missing")
        return rows
    machine, nsects, timestamp, ptrsym, nsym, optsize, chars = struct.unpack_from(
        "<HHIIIHH", blob, peoff + 4
    )
    rows.append(
        f"machine=0x{machine:04x} sections={nsects} timestamp=0x{timestamp:08x} "
        f"optional_header={optsize} chars=0x{chars:04x}"
    )
    optoff = peoff + 24
    magic = struct.unpack_from("<H", blob, optoff)[0]
    entry = struct.unpack_from("<I", blob, optoff + 16)[0]
    imagebase = struct.unpack_from("<I", blob, optoff + 28)[0]
    rows.append(f"optional_magic=0x{magic:04x} entry_rva=0x{entry:x} imagebase=0x{imagebase:x}")
    numdirs = struct.unpack_from("<I", blob, optoff + 92)[0]
    for idx, name in [(0, "export"), (1, "import"), (2, "resource"), (5, "reloc")]:
        if idx < numdirs:
            rva, size = struct.unpack_from("<II", blob, optoff + 96 + idx * 8)
            rows.append(f"data_dir[{idx}:{name}] rva=0x{rva:x} size={size}")
    sec_off = optoff + optsize
    for idx in range(nsects):
        off = sec_off + 40 * idx
        name = blob[off : off + 8].rstrip(b"\0").decode("ascii", "replace")
        vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", blob, off + 8)
        sec_chars = struct.unpack_from("<I", blob, off + 36)[0]
        rows.append(
            f"section[{idx}] {name} va=0x{va:x} vsize={vsize} "
            f"raw_ptr={raw_ptr} raw_size={raw_size} chars=0x{sec_chars:08x}"
        )
    return rows


def inspect_file(path: Path, max_head: int = 64) -> str:
    blob = path.read_bytes()
    counts = collections.Counter(blob)
    top = " ".join(f"{byte:02x}:{count}" for byte, count in counts.most_common(10))
    head = blob[:max_head].hex(" ")
    return (
        f"{path.name}: size={len(blob)} unique={len(counts)} entropy={entropy(blob):.3f}\n"
        f"  head={head}\n"
        f"  top={top}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game_dir", type=Path)
    parser.add_argument("--strings-limit", type=int, default=300)
    args = parser.parse_args()
    root = args.game_dir
    exe = root / "Emperor.exe"

    print("== PE ==")
    blob = exe.read_bytes()
    for line in parse_pe(blob):
        print(line)

    print("\n== Interesting strings ==")
    hits = []
    for off, text in ascii_strings(blob):
        if any(term in text.lower() for term in INTERESTING):
            hits.append((off, "ascii", text))
    for off, text in utf16le_strings(blob):
        if any(term in text.lower() for term in INTERESTING):
            hits.append((off, "utf16", text))
    for off, kind, text in hits[: args.strings_limit]:
        print(f"0x{off:06x} {kind:5s} {text}")
    print(f"total_interesting_strings={len(hits)}")

    print("\n== Stage file sizes by extension ==")
    by_ext = collections.defaultdict(list)
    for path in sorted(root.glob("stage*.*")):
        by_ext[path.suffix.lower()].append(path)
    for ext in sorted(by_ext):
        sizes = collections.Counter(path.stat().st_size for path in by_ext[ext])
        summary = ", ".join(f"{size}:{count}" for size, count in sizes.most_common(12))
        print(f"{ext or '<none>'}: count={len(by_ext[ext])} sizes={summary}")

    print("\n== Sample files ==")
    sample_names = ["stage00", "stage01", "stage11", "stage20", "stage39"]
    sample_exts = [".s", ".x", ".m", ".stg", ".spr", ".dor", ".evt"]
    for stem in sample_names:
        print(f"-- {stem} --")
        for ext in sample_exts:
            path = root / f"{stem}{ext}"
            if path.exists():
                print(inspect_file(path))

    print("\n== Container candidates ==")
    for name in [
        "kingdom.cel",
        "kingdom.atr",
        "Graphics.dat",
        "Selects.dat",
        "windows.dat",
        "heads.dat",
        "Emperor3.act",
        "Emperor3.anm",
    ]:
        path = root / name
        if path.exists():
            print(inspect_file(path, max_head=96))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
