"""把无资源编辑器基础目录与独立内容包组合为可选带关卡分发包。"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from san_tools.map.build_editor_release import EXE_NAME, sha256_file
from san_tools.map.editor_content_pack import CONTENT_PACK_SUFFIX, inspect_content_pack
from san_tools.map.editor_release_audit import audit_release_tree


def compose_editor_distribution(
    release_dir: Path,
    content_packs: list[Path],
    output_path: Path,
) -> dict[str, object]:
    """审计基础五文件目录和内容包，并生成不改变内部边界的组合 ZIP。"""

    release_dir = release_dir.expanduser().resolve()
    base_manifest = audit_release_tree(release_dir, f"{EXE_NAME}.exe")
    reports = [inspect_content_pack(path) for path in content_packs]
    stages = [report.stage for report in reports]
    if not reports:
        raise ValueError("组合分发至少需要一个独立内容包")
    if len(stages) != len(set(stages)):
        raise ValueError("组合分发不能包含重复关卡内容包")
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for item in base_manifest:
                archive.write(release_dir / str(item["path"]), str(item["path"]))
            for report in reports:
                archive.write(report.archive_path, f"content-packs/{report.stage}{CONTENT_PACK_SUFFIX}")
        # 重新读取组合 ZIP，确保基础文件和嵌套内容包均未在写入时发生变化。
        with zipfile.ZipFile(temp_path) as archive:
            names = {info.filename for info in archive.infolist() if not info.is_dir()}
            expected = {str(item["path"]) for item in base_manifest} | {
                f"content-packs/{report.stage}{CONTENT_PACK_SUFFIX}" for report in reports
            }
            if names != expected:
                raise ValueError("组合 ZIP 文件集合与预期不一致")
            for report in reports:
                name = f"content-packs/{report.stage}{CONTENT_PACK_SUFFIX}"
                with tempfile.NamedTemporaryFile(suffix=CONTENT_PACK_SUFFIX, delete=False) as handle:
                    handle.write(archive.read(name))
                    nested_path = Path(handle.name)
                try:
                    nested = inspect_content_pack(nested_path)
                    if nested.archive_sha256 != report.archive_sha256:
                        raise ValueError(f"组合 ZIP 中的内容包哈希变化：{report.stage}")
                finally:
                    nested_path.unlink(missing_ok=True)
        shutil.move(temp_path, output_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return {
        "format": "san-map-editor-composed-distribution-v1",
        "archive": str(output_path),
        "bytes": output_path.stat().st_size,
        "sha256": sha256_file(output_path),
        "stages": stages,
        "base_file_count": len(base_manifest),
        "content_pack_count": len(reports),
    }


def main() -> int:
    """解析组合分发命令参数。"""

    parser = argparse.ArgumentParser(description="组合无资源编辑器基础目录与独立内容包")
    parser.add_argument("release_dir", type=Path, help="已经通过审计的五文件发布目录")
    parser.add_argument("content_pack", type=Path, nargs="+", help="一个或多个 .sanmap-pack 内容包")
    parser.add_argument("--output", type=Path, required=True, help="组合分发 ZIP 输出路径")
    args = parser.parse_args()
    print(json.dumps(
        compose_editor_distribution(args.release_dir, args.content_pack, args.output),
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
