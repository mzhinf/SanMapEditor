from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image

GRID_SIZE = 160
ACTIVE_ROWS = 128


def parse_stage_final_palette(stage_path: Path) -> tuple[int, int, bytes]:
    """读取 `.m` 中每个 cell 的 `final_palette` 字节。"""

    blob = stage_path.read_bytes()
    if len(blob) < 16:
        raise ValueError(f"{stage_path} 过小，不是合法的 .m 文件。")
    width, height = struct.unpack_from("<II", blob, 0)
    if blob[8:16] != b"Hello1.0":
        raise ValueError(f"{stage_path} 不是 Hello1.0 地图文件。")
    expected = 16 + width * height * 16
    if len(blob) < expected:
        raise ValueError(f"{stage_path} 长度不足，期望至少 {expected} 字节，实际 {len(blob)} 字节。")
    final_palette = bytes(blob[16 + index * 16 + 13] for index in range(width * height))
    return width, height, final_palette


def build_active_minimap_bytes(
    width: int,
    height: int,
    final_palette: bytes,
    grid_size: int = GRID_SIZE,
    active_rows: int = ACTIVE_ROWS,
) -> bytes:
    """把 `.m` 的 `final_palette` 缩放成小地图有效区字节流。"""

    if len(final_palette) != width * height:
        raise ValueError("final_palette 长度与 width * height 不一致。")
    if not (0 < active_rows <= grid_size):
        raise ValueError("active_rows 必须落在 1..grid_size 范围内。")
    image = Image.new("L", (width, height))
    image.putdata(final_palette)
    return image.resize((grid_size, active_rows), Image.Resampling.NEAREST).tobytes()


def validate_sidecar_blob(blob: bytes, grid_size: int = GRID_SIZE) -> None:
    """校验 `.s/.x` 是否为固定网格。"""

    expected = grid_size * grid_size
    if len(blob) != expected:
        raise ValueError(f"sidecar 长度应为 {expected} 字节，实际 {len(blob)} 字节。")


def merge_active_with_reference_tail(
    active_bytes: bytes,
    reference_blob: bytes,
    grid_size: int = GRID_SIZE,
    active_rows: int = ACTIVE_ROWS,
) -> bytes:
    """用派生有效区覆盖顶部，并保留原始 `.s/.x` 的尾区。"""

    validate_sidecar_blob(reference_blob, grid_size)
    expected_active = grid_size * active_rows
    if len(active_bytes) != expected_active:
        raise ValueError(f"active_bytes 长度应为 {expected_active} 字节，实际 {len(active_bytes)} 字节。")
    return active_bytes + reference_blob[expected_active:]


def build_sidecar_from_stage(
    stage_path: Path,
    reference_path: Path,
    grid_size: int = GRID_SIZE,
    active_rows: int = ACTIVE_ROWS,
) -> bytes:
    """根据 `.m` 与原始 `.s/.x` 参考文件生成新的 sidecar。"""

    width, height, final_palette = parse_stage_final_palette(stage_path)
    active_bytes = build_active_minimap_bytes(width, height, final_palette, grid_size, active_rows)
    return merge_active_with_reference_tail(active_bytes, reference_path.read_bytes(), grid_size, active_rows)


def byte_same_ratio(left: bytes, right: bytes) -> float:
    """返回两个等长字节序列的逐字节相等比例。"""

    if len(left) != len(right):
        raise ValueError("两个字节序列长度不一致，无法比较。")
    same = sum(1 for a, b in zip(left, right) if a == b)
    return round(same / len(left), 6)


def save_sidecar_preview(
    blob: bytes,
    palette: list[int],
    out_path: Path,
    grid_size: int = GRID_SIZE,
    scale: int = 3,
) -> None:
    """把 `.s/.x` 字节流导出成可视化 PNG。"""

    validate_sidecar_blob(blob, grid_size)
    image = Image.frombytes("P", (grid_size, grid_size), blob)
    image.putpalette((palette + [0] * 768)[:768])
    if scale != 1:
        image = image.resize((grid_size * scale, grid_size * scale), Image.Resampling.NEAREST)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
