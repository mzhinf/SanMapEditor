"""构建可交付给地图编辑人员的 Windows 发布包。"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from san_tools.map.export_editor_bundle import export_editor_bundle


EXE_NAME = "SanMapEditor"
RELEASE_CREATOR = "mzhinf"
USER_GUIDE_SOURCE = Path("docs") / "EDITOR_USER_GUIDE.zh.md"


def write_release_guides(root: Path, package_dir: Path, build_time: str) -> None:
    """写入最短启动说明，并把仓库内完整用户指南复制到发布目录。"""

    guide_source = root / USER_GUIDE_SOURCE
    if not guide_source.is_file():
        raise FileNotFoundError(f"缺少编辑器用户指南：{guide_source}")
    shutil.copy2(guide_source, package_dir / "编辑器使用指南.md")
    (package_dir / "使用说明.txt").write_text(
        "三国霸业地图编辑器 2.0\n\n"
        f"创建者：{RELEASE_CREATOR}\n"
        f"打包时间：{build_time}\n\n"
        "1. 请先把整个 ZIP 完整解压。\n"
        "2. 保持 SanMapEditor.exe 与 editor-data 文件夹在同一目录。\n"
        "3. 双击 SanMapEditor.exe，并保持启动器小窗口运行。\n"
        "4. 浏览器未自动打开时，点击启动器中的“打开编辑器”。\n"
        "5. 详细操作请阅读同目录的《编辑器使用指南.md》。\n",
        encoding="utf-8-sig",
    )


def ensure_safe_work_dir(root: Path, work_dir: Path) -> Path:
    """确认构建目录位于项目目录内，避免清理到用户文件。"""

    resolved_root = root.resolve()
    resolved_work = work_dir.resolve()
    if resolved_work == resolved_root or resolved_root not in resolved_work.parents:
        raise ValueError(f"构建目录必须位于项目目录内：{resolved_work}")
    return resolved_work


def build_release(root: Path, stage: str, work_dir: Path, output_dir: Path) -> dict[str, object]:
    """导出关卡 bundle、构建启动器，并压缩成完整发布包。"""

    root = root.resolve()
    work_dir = ensure_safe_work_dir(root, work_dir)
    output_dir = output_dir.resolve()
    bundle_dir = work_dir / "bundle"
    package_dir = work_dir / f"{EXE_NAME}-{stage}"
    pyinstaller_work = work_dir / "pyinstaller"
    pyinstaller_dist = work_dir / "dist"

    # 构建目录只保存可再生文件，每次发布前清空可避免混入旧关卡。
    if work_dir.exists():
        shutil.rmtree(work_dir)
    bundle_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    build_date = date.today().isoformat()
    build_time = datetime.now().isoformat(sep=" ", timespec="seconds")
    export_result = export_editor_bundle(root, stage, bundle_dir, "stagger", "xyz", "SAN_RGB_PALETTE")
    release_info = {"creator": RELEASE_CREATOR, "build_date": build_date, "build_time": build_time, "stage": stage}
    (bundle_dir / "release-info.json").write_text(json.dumps(release_info, ensure_ascii=False, indent=2), encoding="utf-8")
    launcher = root / "src" / "san_tools" / "map" / "editor_desktop_launcher.py"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        EXE_NAME,
        "--distpath",
        str(pyinstaller_dist),
        "--workpath",
        str(pyinstaller_work),
        "--specpath",
        str(work_dir),
        str(launcher),
    ]
    subprocess.run(command, cwd=root, check=True)

    package_dir.mkdir(parents=True)
    shutil.copy2(pyinstaller_dist / f"{EXE_NAME}.exe", package_dir / f"{EXE_NAME}.exe")
    shutil.copytree(bundle_dir, package_dir / "editor-data")
    write_release_guides(root, package_dir, build_time)

    archive_base = output_dir / f"{EXE_NAME}-{stage}-{build_date}"
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", package_dir))
    result = {
        "stage": stage,
        "archive": str(archive_path),
        "package": str(package_dir),
        "archive_bytes": archive_path.stat().st_size,
        "creator": RELEASE_CREATOR,
        "build_date": build_date,
        "build_time": build_time,
        "bundle": export_result,
    }
    (output_dir / f"{EXE_NAME}-{stage}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    """解析发布构建参数。"""

    parser = argparse.ArgumentParser(description="构建三国霸业地图编辑器 Windows 发布包")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", default="stage01")
    parser.add_argument("--work-dir", default="derived/editor-release", type=Path)
    parser.add_argument("--output-dir", default="dist", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    work_dir = args.work_dir if args.work_dir.is_absolute() else root / args.work_dir
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    print(json.dumps(build_release(root, args.stage, work_dir, output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
