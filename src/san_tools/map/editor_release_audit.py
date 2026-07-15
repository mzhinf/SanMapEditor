"""审计地图编辑器发布目录与 ZIP，阻止游戏资源进入交付物。"""

from __future__ import annotations

import fnmatch
import hashlib
import zipfile
from pathlib import Path, PurePosixPath


DEFAULT_EXE_NAME = "SanMapEditor.exe"
RELEASE_ALLOWED_FILES = frozenset(
    {
        DEFAULT_EXE_NAME,
        "editor-data/index.html",
        "editor-data/release-info.json",
        "使用说明.txt",
        "编辑器使用指南.md",
    }
)
FORBIDDEN_FILE_NAMES = frozenset(
    {
        "stage.ini",
        "history.txt",
        "heads.dat",
        "kingdom.cel",
        "kingdom.atr",
        "stage_ini.xlsx",
        "map.png",
        "minimap.png",
        "heads.png",
        "stage.json",
        "resources.json",
    }
)
FORBIDDEN_SUFFIXES = frozenset({".m", ".dor", ".stg", ".s", ".x"})
FORBIDDEN_DERIVED_PATTERNS = ("draw_acw*.png", "resources_acw*.png")


class ReleaseAuditError(ValueError):
    """表示发布结构不满足资源白名单或安全约束。"""


def normalize_release_path(value: str) -> str:
    """把发布路径规范为安全的 POSIX 相对路径。"""

    raw = value.replace("\\", "/").strip()
    path = PurePosixPath(raw)
    if (
        not raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(":" in part for part in path.parts)
    ):
        raise ReleaseAuditError(f"发布路径不是安全相对路径：{value!r}")
    return path.as_posix()


def forbidden_release_reason(value: str) -> str | None:
    """返回路径命中禁用游戏资源规则的原因。"""

    path = PurePosixPath(normalize_release_path(value))
    lower_parts = tuple(part.lower() for part in path.parts)
    name = lower_parts[-1]
    if any(part.startswith("stage") for part in lower_parts[:-1]):
        return "发布目录中禁止存在 stage 关卡目录"
    if name in FORBIDDEN_FILE_NAMES:
        return f"发布包禁止包含 {path.name}"
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return f"发布包禁止包含 {path.suffix} 游戏文件"
    if any(fnmatch.fnmatch(name, pattern) for pattern in FORBIDDEN_DERIVED_PATTERNS):
        return f"发布包禁止包含游戏派生图片 {path.name}"
    return None


def release_allowed_files(exe_name: str = DEFAULT_EXE_NAME) -> frozenset[str]:
    """返回给定启动器文件名对应的完整发布白名单。"""

    if exe_name == DEFAULT_EXE_NAME:
        return RELEASE_ALLOWED_FILES
    return frozenset((RELEASE_ALLOWED_FILES - {DEFAULT_EXE_NAME}) | {normalize_release_path(exe_name)})


def validate_release_paths(paths: list[str], exe_name: str = DEFAULT_EXE_NAME) -> list[str]:
    """校验所有路径恰好命中白名单，并拒绝重复或禁用资源。"""

    normalized = [normalize_release_path(path) for path in paths]
    duplicate_paths = sorted({path for path in normalized if normalized.count(path) > 1})
    if duplicate_paths:
        raise ReleaseAuditError(f"发布包包含重复路径：{', '.join(duplicate_paths)}")

    forbidden = [(path, forbidden_release_reason(path)) for path in normalized]
    forbidden = [(path, reason) for path, reason in forbidden if reason]
    if forbidden:
        details = "；".join(f"{path}：{reason}" for path, reason in forbidden)
        raise ReleaseAuditError(f"发布资源审计失败：{details}")

    allowed = release_allowed_files(exe_name)
    actual = set(normalized)
    missing = sorted(allowed - actual)
    unexpected = sorted(actual - allowed)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"缺少白名单文件：{', '.join(missing)}")
        if unexpected:
            details.append(f"存在非白名单文件：{', '.join(unexpected)}")
        raise ReleaseAuditError("；".join(details))
    return sorted(normalized)


def sha256_bytes(blob: bytes) -> str:
    """计算清单使用的小写 SHA-256。"""

    return hashlib.sha256(blob).hexdigest()


def _manifest_entry(path: str, blob: bytes) -> dict[str, object]:
    """生成一个稳定的发布文件清单项。"""

    return {"path": path, "bytes": len(blob), "sha256": sha256_bytes(blob)}


def audit_release_tree(root: Path, exe_name: str = DEFAULT_EXE_NAME) -> list[dict[str, object]]:
    """审计发布目录并返回全部白名单文件的哈希清单。"""

    root = root.resolve()
    if not root.is_dir():
        raise ReleaseAuditError(f"发布目录不存在：{root}")
    files = [path for path in root.rglob("*") if path.is_file()]
    files.sort(key=lambda path: path.relative_to(root).as_posix())
    relative_paths = [path.relative_to(root).as_posix() for path in files]
    validate_release_paths(relative_paths, exe_name)
    return [_manifest_entry(path.relative_to(root).as_posix(), path.read_bytes()) for path in files]


def audit_release_zip(archive_path: Path, exe_name: str = DEFAULT_EXE_NAME) -> list[dict[str, object]]:
    """审计 ZIP 条目，拒绝路径穿越、重复项和任何非白名单内容。"""

    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise ReleaseAuditError(f"发布 ZIP 不存在：{archive_path}")
    with zipfile.ZipFile(archive_path) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        normalized = [normalize_release_path(info.filename) for info in infos]
        validate_release_paths(normalized, exe_name)
        return [
            _manifest_entry(path, archive.read(info))
            for path, info in sorted(zip(normalized, infos), key=lambda item: item[0])
        ]
