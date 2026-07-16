"""管理用户显式导入文件与系统临时目录中的编辑器运行时会话。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from san_tools.map.editor_content_pack import ContentPackReport


SESSION_FORMAT = "san-map-editor-runtime-session-v1"
SESSION_ROOT_NAME = "SanMapEditor"
SESSION_MARKER_NAME = ".san-map-editor-session.json"
DEFAULT_STALE_SECONDS = 24 * 60 * 60
STAGE_FILE_PATTERN = re.compile(r"^(stage(?P<number>\d+))\.m$", re.IGNORECASE)


@dataclass(frozen=True)
class RuntimeInputSpec:
    """描述一个运行时输入文件及其用途。"""

    role: str
    filename: str
    required: bool
    purpose: str


@dataclass(frozen=True)
class RuntimeInputFile:
    """记录一个已经识别并校验的用户输入文件。"""

    role: str
    path: Path
    required: bool
    purpose: str
    bytes: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        """返回可写入临时会话元数据的序列化结构。"""

        return {
            "role": self.role,
            "path": str(self.path),
            "required": self.required,
            "purpose": self.purpose,
            "bytes": self.bytes,
            "sha256": self.sha256,
        }


@dataclass
class RuntimeInputReport:
    """汇总一次用户输入识别的成功项、缺失项和冲突。"""

    stage: str
    stage_path: Path
    source_dir: Path
    files: list[RuntimeInputFile] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    duplicates: dict[str, list[str]] = field(default_factory=dict)
    mismatched: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """关键文件完整且没有重复、错配或结构错误时返回真。"""

        return not self.missing and not self.duplicates and not self.mismatched and not self.errors

    def to_dict(self) -> dict[str, object]:
        """返回供启动器展示和会话元数据记录的完整校验结果。"""

        return {
            "valid": self.valid,
            "stage": self.stage,
            "stage_path": str(self.stage_path),
            "source_dir": str(self.source_dir),
            "files": [item.to_dict() for item in self.files],
            "missing": self.missing,
            "duplicates": self.duplicates,
            "mismatched": self.mismatched,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def require_valid(self) -> None:
        """在校验失败时抛出包含本报告的可读异常。"""

        if not self.valid:
            raise RuntimeInputError.from_report(self)


class RuntimeInputError(ValueError):
    """表示用户输入清单或运行时会话不满足安全约束。"""

    def __init__(self, message: str, report: RuntimeInputReport | None = None) -> None:
        super().__init__(message)
        self.report = report

    @classmethod
    def from_report(cls, report: RuntimeInputReport) -> RuntimeInputError:
        """按稳定顺序把校验报告转换为启动器可直接显示的错误。"""

        details: list[str] = []
        if report.missing:
            details.append("缺少文件：" + "、".join(report.missing))
        if report.duplicates:
            details.append("重复文件：" + "；".join(f"{name} -> {', '.join(paths)}" for name, paths in report.duplicates.items()))
        if report.mismatched:
            details.append("场景编号不匹配：" + "；".join(f"{name} -> {', '.join(paths)}" for name, paths in report.mismatched.items()))
        details.extend(report.errors)
        return cls("\n".join(details) or "运行时输入校验失败", report)


def runtime_input_specs(stage: str) -> tuple[RuntimeInputSpec, ...]:
    """返回当前场景的必需输入和可选输入定义。"""

    return (
        RuntimeInputSpec("map", f"{stage}.m", True, "地图尺寸和 Cell 数据"),
        RuntimeInputSpec("tiles", "kingdom.cel", True, "地图资源像素"),
        RuntimeInputSpec("doors", f"{stage}.dor", True, "据点城门记录"),
        RuntimeInputSpec("scenario", f"{stage}.stg", True, "势力、据点、武将和士兵"),
        RuntimeInputSpec("minimap_s", f"{stage}.s", True, "小地图 S Sidecar 与尾区"),
        RuntimeInputSpec("minimap_x", f"{stage}.x", True, "小地图 X Sidecar 与尾区"),
        RuntimeInputSpec("stage_ini", "stage.ini", True, "城池和武将母表"),
        RuntimeInputSpec("history", "History.txt", True, "历史武将与加入日期"),
        RuntimeInputSpec("heads", "heads.dat", True, "武将头像像素"),
        RuntimeInputSpec("attributes", "kingdom.atr", False, "资源属性研究数据"),
    )


def sha256_file(path: Path) -> str:
    """以流式读取计算用户输入文件的 SHA-256。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_casefold_index(paths: list[Path]) -> tuple[dict[str, Path], dict[str, list[Path]]]:
    """按不区分大小写的文件名建立唯一索引并报告重复项。"""

    grouped: dict[str, list[Path]] = {}
    for path in paths:
        grouped.setdefault(path.name.casefold(), []).append(path)
    unique = {name: entries[0] for name, entries in grouped.items() if len(entries) == 1}
    duplicates = {name: entries for name, entries in grouped.items() if len(entries) > 1}
    return unique, duplicates


def validate_stage_map(path: Path) -> str | None:
    """检查 .m 头、尺寸和 Cell 数据长度，返回错误文本或空值。"""

    try:
        with path.open("rb") as handle:
            header = handle.read(16)
    except OSError as exc:
        return f"无法读取 {path.name}：{exc}"
    if len(header) < 16 or header[8:16] != b"Hello1.0":
        return f"{path.name} 不是有效的 stage .m 文件"
    width, height = struct.unpack_from("<II", header, 0)
    if width <= 0 or height <= 0 or width > 4096 or height > 4096:
        return f"{path.name} 地图尺寸无效：{width}x{height}"
    expected = 16 + width * height * 16
    actual = path.stat().st_size
    if actual < expected:
        return f"{path.name} 数据长度不足：需要至少 {expected} 字节，实际 {actual} 字节"
    return None


def _stage_mismatch_candidates(source_dir: Path, expected_name: str) -> list[str]:
    """在缺少当前场景文件时列出同扩展名的其他 stage 文件。"""

    suffix = Path(expected_name).suffix.casefold()
    return sorted(
        path.name
        for path in source_dir.iterdir()
        if path.is_file()
        and path.suffix.casefold() == suffix
        and path.stem.casefold().startswith("stage")
        and path.name.casefold() != expected_name.casefold()
    )


def validate_runtime_inputs(stage_path: Path, source_dir: Path | None = None) -> RuntimeInputReport:
    """只从用户显式路径识别同组文件，不读取环境变量或仓库默认数据。"""

    stage_path = stage_path.expanduser().resolve()
    source_dir = (source_dir or stage_path.parent).expanduser().resolve()
    match = STAGE_FILE_PATTERN.fullmatch(stage_path.name)
    if match is None:
        raise RuntimeInputError(f"地图文件名必须符合 stageXX.m：{stage_path.name}")
    stage = match.group(1).lower()
    report = RuntimeInputReport(stage=stage, stage_path=stage_path, source_dir=source_dir)
    if not source_dir.is_dir():
        report.errors.append(f"资源目录不存在：{source_dir}")
        return report
    if not stage_path.is_file():
        report.missing.append(stage_path.name)
        return report

    directory_files = [path.resolve() for path in source_dir.iterdir() if path.is_file()]
    unique, duplicates = build_casefold_index(directory_files)
    specs = runtime_input_specs(stage)
    expected_names = {spec.filename.casefold() for spec in specs}
    report.duplicates = {
        name: [str(path) for path in entries]
        for name, entries in sorted(duplicates.items())
        if name in expected_names
    }

    for spec in specs:
        if spec.role == "map":
            path = stage_path
        else:
            path = unique.get(spec.filename.casefold())
        if path is None:
            if spec.required:
                report.missing.append(spec.filename)
                candidates = _stage_mismatch_candidates(source_dir, spec.filename)
                if candidates:
                    report.mismatched[spec.filename] = candidates
            else:
                report.warnings.append(f"可选文件未提供：{spec.filename}")
            continue
        if spec.filename.casefold() in report.duplicates:
            continue
        try:
            report.files.append(
                RuntimeInputFile(
                    role=spec.role,
                    path=path,
                    required=spec.required,
                    purpose=spec.purpose,
                    bytes=path.stat().st_size,
                    sha256=sha256_file(path),
                )
            )
        except OSError as exc:
            report.errors.append(f"无法读取 {path.name}：{exc}")

    map_error = validate_stage_map(stage_path)
    if map_error:
        report.errors.append(map_error)
    return report


RuntimeExporter = Callable[[RuntimeInputReport, Path], dict[str, object]]


def default_runtime_exporter(report: RuntimeInputReport, out_dir: Path) -> dict[str, object]:
    """延迟导入真实导出器，避免会话模块与 Bundle 模块循环依赖。"""

    from san_tools.map.export_editor_bundle import export_runtime_editor_bundle

    return export_runtime_editor_bundle(report, out_dir)


def input_fingerprint(report: RuntimeInputReport) -> tuple[tuple[object, ...], ...]:
    """按来源路径和内容哈希生成可复用会话的稳定指纹。"""

    return tuple(
        (
            item.role,
            os.path.normcase(str(item.path)),
            item.bytes,
            item.sha256,
        )
        for item in report.files
    )


@dataclass
class RuntimeSession:
    """表示一次已经成功生成且可以提供 HTTP 服务的临时会话。"""

    root: Path
    data_dir: Path
    stage: str
    entry_path: str
    report: RuntimeInputReport | ContentPackReport
    created_at: float
    persistent: bool = False


class RuntimeSessionManager:
    """以事务方式创建、替换和清理编辑器临时会话。"""

    def __init__(
        self,
        exporter: RuntimeExporter | None = None,
        session_base: Path | None = None,
        stale_seconds: int = DEFAULT_STALE_SECONDS,
    ) -> None:
        self.exporter = exporter or default_runtime_exporter
        self.session_base = (session_base or Path(tempfile.gettempdir()) / SESSION_ROOT_NAME).resolve()
        self.stale_seconds = stale_seconds
        self.current: RuntimeSession | None = None

    def _safe_session_path(self, path: Path) -> Path:
        """确认目标是会话根的直接子目录，防止清理路径越界。"""

        resolved = path.resolve()
        if resolved.parent != self.session_base or resolved == self.session_base:
            raise RuntimeInputError(f"临时会话路径越界：{resolved}")
        return resolved

    def _write_marker(self, session_dir: Path, created_at: float) -> None:
        """写入清理所需的专用标记，未标记目录永不自动删除。"""

        marker = {
            "format": SESSION_FORMAT,
            "created_at": created_at,
            "pid": os.getpid(),
        }
        (session_dir / SESSION_MARKER_NAME).write_text(
            json.dumps(marker, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _discard_session(self, session: RuntimeSession | None) -> None:
        """只清理临时会话；内容包哈希缓存跨启动保留。"""

        if session is not None and not session.persistent:
            self.cleanup_session_dir(session.root)

    def cleanup_session_dir(self, path: Path) -> bool:
        """只删除路径安全且具有本程序标记的会话目录。"""

        resolved = self._safe_session_path(path)
        marker = resolved / SESSION_MARKER_NAME
        if not resolved.is_dir() or not marker.is_file():
            return False
        shutil.rmtree(resolved)
        return True

    def cleanup_stale(self, now: float | None = None) -> list[Path]:
        """清理上次异常退出遗留且超过有效期的已标记会话。"""

        now = time.time() if now is None else now
        removed: list[Path] = []
        if not self.session_base.is_dir():
            return removed
        current_root = self.current.root.resolve() if self.current else None
        for candidate in self.session_base.iterdir():
            if not candidate.is_dir() or candidate.resolve() == current_root:
                continue
            marker = candidate / SESSION_MARKER_NAME
            if not marker.is_file():
                continue
            age = now - marker.stat().st_mtime
            if age >= self.stale_seconds and self.cleanup_session_dir(candidate):
                removed.append(candidate.resolve())
        return removed

    def create_from_directory(
        self,
        source_dir: Path,
        release_info: dict[str, object] | None = None,
    ) -> RuntimeSession:
        """从只含一个 stageXX.m 的用户目录创建会话。"""

        source_dir = source_dir.expanduser().resolve()
        if not source_dir.is_dir():
            raise RuntimeInputError(f"资源目录不存在：{source_dir}")
        stages = sorted(
            path for path in source_dir.iterdir()
            if path.is_file() and STAGE_FILE_PATTERN.fullmatch(path.name)
        )
        if not stages:
            raise RuntimeInputError(f"资源目录中没有 stageXX.m：{source_dir}")
        if len(stages) > 1:
            raise RuntimeInputError("资源目录包含多个地图，请改为直接选择一个 .m 文件：" + "、".join(path.name for path in stages))
        return self.create_from_stage(stages[0], source_dir, release_info)

    def create_from_stage(
        self,
        stage_path: Path,
        source_dir: Path | None = None,
        release_info: dict[str, object] | None = None,
    ) -> RuntimeSession:
        """校验输入并先完整生成新会话，成功后才替换旧会话。"""

        report = validate_runtime_inputs(stage_path, source_dir)
        report.require_valid()
        if (
            self.current is not None
            and not self.current.persistent
            and self.current.root.is_dir()
            and input_fingerprint(self.current.report) == input_fingerprint(report)
        ):
            return self.current

        self.session_base.mkdir(parents=True, exist_ok=True)
        created_at = time.time()
        session_dir = self._safe_session_path(
            self.session_base / f"{report.stage}-{uuid.uuid4().hex}"
        )
        session_dir.mkdir()
        self._write_marker(session_dir, created_at)
        data_dir = session_dir / "editor-data"
        try:
            export_result = self.exporter(report, data_dir)
            entry_path = f"/{report.stage}/editor.html"
            if not (data_dir / report.stage / "editor.html").is_file():
                raise RuntimeInputError("运行时导出器未生成编辑器入口", report)
            metadata = {
                "format": SESSION_FORMAT,
                "created_at": created_at,
                "stage": report.stage,
                "entry_path": entry_path,
                "inputs": report.to_dict(),
                "export": export_result,
            }
            (session_dir / "session-info.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            runtime_release_info = dict(release_info or {})
            runtime_release_info["active_stage"] = report.stage
            runtime_release_info["runtime_session"] = "system-temp"
            (data_dir / "release-info.json").write_text(
                json.dumps(runtime_release_info, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            session = RuntimeSession(
                root=session_dir,
                data_dir=data_dir,
                stage=report.stage,
                entry_path=entry_path,
                report=report,
                created_at=created_at,
            )
        except Exception:
            self.cleanup_session_dir(session_dir)
            raise

        previous = self.current
        self.current = session
        self._discard_session(previous)
        return session

    def create_from_content_pack(
        self,
        archive_path: Path,
        release_info: dict[str, object] | None = None,
        cache_base: Path | None = None,
    ) -> RuntimeSession:
        """校验独立内容包并切换到可复用的持久哈希缓存。"""

        from san_tools.map.editor_content_pack import load_content_pack

        loaded = load_content_pack(archive_path, release_info, cache_base)
        if (
            self.current is not None
            and self.current.persistent
            and self.current.root.resolve() == loaded.root.resolve()
        ):
            return self.current
        session = RuntimeSession(
            root=loaded.root,
            data_dir=loaded.data_dir,
            stage=loaded.stage,
            entry_path=loaded.entry_path,
            report=loaded.report,
            created_at=loaded.created_at,
            persistent=True,
        )
        previous = self.current
        self.current = session
        self._discard_session(previous)
        return session

    def close(self) -> None:
        """清理当前临时会话；内容包哈希缓存跨启动保留。"""

        if self.current is None:
            return
        current = self.current
        self.current = None
        self._discard_session(current)
