"""构建可交付给地图编辑人员的 Windows 发布包。"""

from __future__ import annotations

import argparse
import hashlib
import re
import json
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from san_tools.map.editor_desktop_launcher import APP_TITLE
from san_tools.map.editor_release_audit import (
    FORBIDDEN_FILE_NAMES,
    FORBIDDEN_SUFFIXES,
    ReleaseAuditError,
    audit_release_tree,
    audit_release_zip,
)


EXE_NAME = "SanMapEditor"
RELEASE_CREATOR = "mzhinf"
USER_GUIDE_SOURCE = Path("docs") / "EDITOR_USER_GUIDE.zh.md"
EDITOR_TEMPLATE_SOURCE = Path("src") / "san_tools" / "map" / "editor_app.html"
EDITOR_TEMPLATE_TARGET = "san_tools/map"
EMPTY_INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>三国霸业地图编辑器 2.0</title>
  <style>
    body { margin: 0; font-family: "Microsoft YaHei UI", sans-serif; background: #f4f2ec; color: #202124; }
    main { max-width: 720px; margin: 12vh auto; padding: 32px; background: #fff; border: 1px solid #d6d3cb; border-radius: 12px; }
    h1 { margin-top: 0; }
    .notice { padding: 14px 16px; background: #fff8df; border-left: 4px solid #b7791f; }
    code { font-family: Consolas, monospace; }
  </style>
</head>
<body>
  <main>
    <h1>尚未导入地图项目</h1>
    <p>请回到桌面启动器，选择 <code>stageXX.m</code> 或包含完整游戏文件的目录。</p>
    <p class="notice">发布包不包含任何游戏地图、头像或资源贴图。请仅导入您有权使用的本机文件。</p>
    <p>资源校验和临时会话生成完成后，启动器会打开实际编辑页面。</p>
  </main>
</body>
</html>
"""


def write_resource_free_editor_data(data_dir: Path, release_info: dict[str, object]) -> None:
    """写入无关卡、无资源请求的发布根页面和版本信息。"""

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "index.html").write_text(EMPTY_INDEX_HTML, encoding="utf-8")
    (data_dir / "release-info.json").write_text(
        json.dumps(release_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def prepare_release_package(
    root: Path,
    package_dir: Path,
    exe_source: Path,
    release_info: dict[str, object],
) -> list[dict[str, object]]:
    """只复制白名单代码产物和文档，并立即执行目录资源审计。"""

    package_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(exe_source, package_dir / f"{EXE_NAME}.exe")
    write_resource_free_editor_data(package_dir / "editor-data", release_info)
    write_release_guides(root, package_dir, str(release_info["build_time"]))
    return audit_release_tree(package_dir, f"{EXE_NAME}.exe")


def pure_path_name(value: str) -> str:
    """跨平台取得 TOC 路径末段的小写文件名。"""

    return value.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower()


def audit_pyinstaller_collection(work_dir: Path) -> list[str]:
    """检查 PyInstaller TOC，防止构建机游戏目录或文件被收集进 EXE。"""

    toc_files = sorted(work_dir.rglob("*.toc"))
    if not toc_files:
        raise ReleaseAuditError(f"找不到 PyInstaller 收集清单：{work_dir}")
    violations: list[str] = []
    quoted_path = re.compile(r"['\"]([^'\"]+)['\"]")
    for toc_path in toc_files:
        text = toc_path.read_text(encoding="utf-8", errors="replace")
        for candidate in quoted_path.findall(text):
            normalized = candidate.replace("\\", "/").lower()
            name = pure_path_name(candidate)
            if "/data/game/" in f"/{normalized}/" or "/data/text/" in f"/{normalized}/":
                violations.append(f"{toc_path.name}: {candidate}")
            elif name in FORBIDDEN_FILE_NAMES or Path(name).suffix.lower() in FORBIDDEN_SUFFIXES:
                violations.append(f"{toc_path.name}: {candidate}")
    if violations:
        raise ReleaseAuditError("PyInstaller 收集到游戏资源：" + "；".join(sorted(set(violations))))
    return [path.as_posix() for path in toc_files]



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
        "3. 双击 SanMapEditor.exe，并保持启动器窗口运行。\n"
        "4. 在启动器中选择 stageXX.m，或选择只含一个目标地图的完整资源目录。\n"
        "5. 资源校验完成后再打开编辑器；运行时数据只写入系统临时目录。\n"
        "6. 浏览器未自动打开时点击“打开编辑器”，详细操作请阅读《编辑器使用指南.md》。\n"
        "7. 请仅使用您有权使用的本机游戏文件，发布包本身不包含游戏素材。\n",
        encoding="utf-8-sig",
    )


def ensure_safe_work_dir(root: Path, work_dir: Path) -> Path:
    """确认构建目录位于项目目录内，避免清理到用户文件。"""

    resolved_root = root.resolve()
    resolved_work = work_dir.resolve()
    if resolved_work == resolved_root or resolved_root not in resolved_work.parents:
        raise ValueError(f"构建目录必须位于项目目录内：{resolved_work}")
    return resolved_work


def sha256_file(path: Path) -> str:
    """以流式读取计算大型发布文件的 SHA-256。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def editor_template_data_spec(root: Path) -> str:
    """生成 PyInstaller 模板映射，并在构建前拒绝缺失的代码资产。"""

    template = (root / EDITOR_TEMPLATE_SOURCE).resolve()
    if not template.is_file():
        raise FileNotFoundError(f"缺少编辑器运行时模板：{template}")
    # 冻结模块的 __file__ 位于 _MEIPASS/san_tools/map，模板必须映射到同一目录。
    return f"{template}:{EDITOR_TEMPLATE_TARGET}"



def build_release(root: Path, work_dir: Path, output_dir: Path) -> dict[str, object]:
    """在不读取任何游戏数据的情况下构建、审计并压缩发布包。"""

    root = root.resolve()
    work_dir = ensure_safe_work_dir(root, work_dir)
    output_dir = output_dir.resolve()
    package_dir = work_dir / EXE_NAME
    pyinstaller_work = work_dir / "pyinstaller"
    pyinstaller_dist = work_dir / "dist"

    # 构建目录只保存可再生代码产物，每次发布前清空以避免旧资源残留。
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    build_date = date.today().isoformat()
    build_time = datetime.now().isoformat(sep=" ", timespec="seconds")
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
        "--add-data",
        editor_template_data_spec(root),
        str(launcher),
    ]
    subprocess.run(command, cwd=root, check=True)
    toc_files = audit_pyinstaller_collection(pyinstaller_work)

    # 发布元数据不包含默认关卡，明确声明运行时数据来源和临时会话策略。
    release_info = {
        "app_title": APP_TITLE,
        "creator": RELEASE_CREATOR,
        "build_date": build_date,
        "build_time": build_time,
        "resource_policy": "user-import-only",
        "runtime_session": "system-temp",
        "palette_policy": "保留 SAN_RGB_PALETTE，公开发布前确认权利边界",
    }
    file_manifest = prepare_release_package(
        root,
        package_dir,
        pyinstaller_dist / f"{EXE_NAME}.exe",
        release_info,
    )

    archive_base = output_dir / f"{EXE_NAME}-{build_date}"
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", package_dir))
    zip_manifest = audit_release_zip(archive_path, f"{EXE_NAME}.exe")
    if zip_manifest != file_manifest:
        raise ReleaseAuditError("发布目录与 ZIP 的文件清单或哈希不一致")

    manifest_payload = {
        "format": "san-map-editor-release-manifest-v1",
        "build_date": build_date,
        "build_time": build_time,
        "files": file_manifest,
        "archive": {
            "path": archive_path.name,
            "bytes": archive_path.stat().st_size,
            "sha256": sha256_file(archive_path),
        },
        "pyinstaller_toc": toc_files,
    }
    manifest_path = output_dir / f"{EXE_NAME}-{build_date}-manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {
        "archive": str(archive_path),
        "package": str(package_dir),
        "manifest": str(manifest_path),
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": manifest_payload["archive"]["sha256"],
        "creator": RELEASE_CREATOR,
        "build_date": build_date,
        "build_time": build_time,
        "file_count": len(file_manifest),
    }
    (output_dir / f"{EXE_NAME}-release.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def main() -> int:
    """解析发布构建参数。"""

    parser = argparse.ArgumentParser(description="构建不含游戏资源的地图编辑器 Windows 发布包")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--work-dir", default="derived/editor-release", type=Path)
    parser.add_argument("--output-dir", default="dist", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    work_dir = args.work_dir if args.work_dir.is_absolute() else root / args.work_dir
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    print(json.dumps(build_release(root, work_dir, output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
