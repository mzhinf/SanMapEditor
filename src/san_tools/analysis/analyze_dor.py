from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

RECORD_SIZE = 0x3C
MAGIC = b"Door    Data"


def parse_dor(dor_file: str | Path) -> list[dict[str, object]]:
    """解析 `.dor`，返回按据点分组的完整城门数据。"""

    dor_path = Path(dor_file)
    data = dor_path.read_bytes()

    magic = data[:12]
    if magic != MAGIC:
        raise ValueError(f"不是有效的 Door Data 文件：{magic!r}")

    record_size = struct.unpack_from("<I", data, 0x0C)[0]
    if record_size != RECORD_SIZE:
        raise ValueError(f"记录长度异常：{record_size}")

    offset = 0x10
    group_index = 0
    door_groups: list[dict[str, object]] = []

    while offset + 4 <= len(data):
        count_offset = offset
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        if count == 0:
            break

        group_size = count * record_size
        if offset + group_size > len(data):
            raise ValueError(
                f"第 {group_index} 组数据越界：count={count}, "
                f"count_offset={count_offset:#x}, records_start={offset:#x}"
            )

        door_group: list[dict[str, object]] = []
        for index in range(count):
            record_offset = offset + index * record_size
            values = struct.unpack_from("<15i", data, record_offset)
            door_group.append(
                {
                    "group": group_index,           #
                    "index": index,                 #
                    "record_offset": record_offset, #
                    "door_x": values[0],            # 城门 x 轴坐标
                    "door_y": values[1] * 2 + 4,    # 城门 y 轴坐标
                    "dir": values[2],               # 门朝向
                    "site_x": values[12],           # 据点 x 轴坐标
                    "site_y": values[13],           # 据点 y 轴坐标
                    "unk_28": values[10],           #
                    "unk_2c": values[11],           #
                    "extra": values[14],            #
                    "raw": list(values),            #
                }
            )

        door_groups.append(
            {
                "group": group_index,
                "count": count,
                "count_offset": count_offset,
                "records_start": offset,
                "records_end": offset + group_size,
                "doors": door_group,
            }
        )

        offset += group_size
        group_index += 1

    return door_groups


def export_dor_json(dor_file: str | Path, out_dir: Path) -> Path:
    """把 `.dor` 解析结果写出为 JSON。"""

    dor_path = Path(dor_file)
    door_groups = parse_dor(dor_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{dor_path.stem}.json"
    json_path.write_text(
        json.dumps(door_groups, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return json_path


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="解析 `.dor` 中按据点分组的城门数据。")
    parser.add_argument("dor_file", type=Path, help="要解析的 `.dor` 文件路径")
    parser.add_argument(
        "--out",
        default=Path("derived/dor_analysis"),
        type=Path,
        help="输出 JSON 的目录",
    )
    return parser


def main() -> int:
    """命令行入口。"""

    parser = build_parser()
    args = parser.parse_args()

    door_groups = parse_dor(args.dor_file)
    json_path = export_dor_json(args.dor_file, args.out)
    summary = {
        "dor_file": str(args.dor_file),
        "json_path": str(json_path),
        "group_count": len(door_groups),
        "door_count": sum(group["count"] for group in door_groups),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
