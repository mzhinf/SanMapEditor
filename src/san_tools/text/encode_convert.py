from __future__ import annotations

import argparse
from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".py", ".html", ".xml"}


def convert_file(src_path: Path, dst_path: Path, mode: str) -> None:
    """按指定编码方向转换单个文件。"""

    raw = src_path.read_bytes()
    if mode == "big5_to_utf8":
        text = raw.decode("big5", errors="replace")
        out_bytes = text.encode("utf-8")
    elif mode == "utf8_to_big5":
        text = raw.decode("utf-8", errors="replace")
        out_bytes = text.encode("big5", errors="replace")
    else:
        raise ValueError(f"不支持的转换模式：{mode}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(out_bytes)


def should_process(path: Path) -> bool:
    """只转换文本型文件，避免误处理二进制资源。"""

    return path.suffix.lower() in TEXT_EXTENSIONS


def process_folder(input_dir: Path, output_dir: Path, mode: str) -> None:
    """递归转换目录内的可处理文件。"""

    for src_path in input_dir.rglob("*"):
        if not src_path.is_file() or not should_process(src_path):
            continue
        dst_path = output_dir / src_path.relative_to(input_dir)
        try:
            convert_file(src_path, dst_path, mode)
            print(f"[OK] {src_path} -> {dst_path}")
        except Exception as exc:  # pragma: no cover - 保留命令行可见错误即可。
            print(f"[FAIL] {src_path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="批量转换文本文件编码。")
    parser.add_argument("input_dir", type=Path, help="源目录")
    parser.add_argument("output_dir", type=Path, help="输出目录")
    parser.add_argument("mode", choices=["big5_to_utf8", "utf8_to_big5"], help="转换方向")
    args = parser.parse_args()

    process_folder(args.input_dir.resolve(), args.output_dir.resolve(), args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())