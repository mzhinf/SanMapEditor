"""生成、审计并缓存地图编辑器独立内容包。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


CONTENT_PACK_FORMAT = "san-map-editor-content-pack-v1"
CONTENT_PACK_SCHEMA = 1
CONTENT_PACK_SUFFIX = ".sanmap-pack"
CONTENT_PACK_MANIFEST = "manifest.json"
CONTENT_CACHE_MARKER = "content-pack-cache.json"
MAX_CONTENT_FILES = 256
MAX_CONTENT_BYTES = 1024 * 1024 * 1024
MAX_SINGLE_FILE_BYTES = 512 * 1024 * 1024


class ContentPackError(ValueError):
    """表示内容包格式、完整性或兼容性不符合要求。"""


@dataclass(frozen=True)
class ContentPackFile:
    """记录内容包中一个经过哈希校验的文件。"""

    path: str
    bytes: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        """返回可写入 Manifest 的稳定字典。"""

        return {"path": self.path, "bytes": self.bytes, "sha256": self.sha256}


@dataclass
class ContentPackReport:
    """描述一个已经通过完整审计的独立内容包。"""

    stage: str
    archive_path: Path
    archive_sha256: str
    files: list[ContentPackFile]
    manifest: dict[str, object]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """返回不包含本机缓存路径的审计摘要。"""

        return {
            "format": CONTENT_PACK_FORMAT,
            "stage": self.stage,
            "archive": self.archive_path.name,
            "archive_sha256": self.archive_sha256,
            "files": [item.to_dict() for item in self.files],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class LoadedContentPack:
    """表示已经准备为 HTTP 数据目录的缓存内容包。"""

    root: Path
    data_dir: Path
    stage: str
    entry_path: str
    report: ContentPackReport
    created_at: float
    reused: bool


def sha256_file(path: Path) -> str:
    """以流式读取计算大型文件的 SHA-256。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_zip_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    """流式计算 ZIP 条目的 SHA-256，避免把地图图片整体载入内存。"""

    digest = hashlib.sha256()
    with archive.open(info) as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_pack_path(value: str) -> str:
    """规范内容包内部路径并拒绝绝对路径、反斜杠和路径穿越。"""

    if not isinstance(value, str) or not value or "\\" in value:
        raise ContentPackError(f"内容包路径无效：{value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ":" in path.parts[0] or any(part in {"", ".", ".."} for part in path.parts):
        raise ContentPackError(f"内容包路径越界：{value}")
    return path.as_posix()


def content_path(stage: str, name: str) -> str:
    """返回某个关卡文件在内容包中的规范路径。"""

    return f"content/{stage}/{name}"


def _manifest_files(payload: dict[str, object], stage: str) -> list[ContentPackFile]:
    """解析并校验 Manifest 文件清单。"""

    raw_files = payload.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ContentPackError("内容包 Manifest 缺少文件清单")
    if len(raw_files) > MAX_CONTENT_FILES:
        raise ContentPackError(f"内容包文件数量超过上限：{len(raw_files)}")
    files: list[ContentPackFile] = []
    seen: set[str] = set()
    prefix = f"content/{stage}/"
    for raw in raw_files:
        if not isinstance(raw, dict):
            raise ContentPackError("内容包文件清单项必须是对象")
        path = normalize_pack_path(str(raw.get("path") or ""))
        if not path.startswith(prefix) or path == prefix:
            raise ContentPackError(f"内容文件不在当前关卡目录：{path}")
        if path.casefold().endswith(("/editor.html", "/index.html", "/index.json", "/release-info.json")):
            raise ContentPackError(f"内容包不得携带编辑器代码或入口：{path}")
        folded = path.casefold()
        if folded in seen:
            raise ContentPackError(f"内容包文件清单重复：{path}")
        seen.add(folded)
        try:
            size = int(raw.get("bytes"))
        except (TypeError, ValueError) as exc:
            raise ContentPackError(f"内容包文件大小无效：{path}") from exc
        digest = str(raw.get("sha256") or "").lower()
        if size < 0 or size > MAX_SINGLE_FILE_BYTES or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ContentPackError(f"内容包文件元数据无效：{path}")
        files.append(ContentPackFile(path, size, digest))
    if sum(item.bytes for item in files) > MAX_CONTENT_BYTES:
        raise ContentPackError("内容包展开大小超过上限")
    required = {content_path(stage, "stage.json"), content_path(stage, "resources.json")}
    missing = sorted(required - {item.path for item in files})
    if missing:
        raise ContentPackError("内容包缺少编辑器核心文件：" + "、".join(missing))
    return sorted(files, key=lambda item: item.path)


def _validate_local_reference(stage: str, value: object, declared: set[str], label: str) -> None:
    """确认浏览器资源引用是当前关卡目录中的已声明本地文件。"""

    if not isinstance(value, str) or not value:
        raise ContentPackError(f"内容包缺少资源引用：{label}")
    path = normalize_pack_path(value)
    if len(PurePosixPath(path).parts) != 1:
        raise ContentPackError(f"内容包资源引用必须位于关卡根目录：{label} -> {value}")
    packed = content_path(stage, path)
    if packed not in declared:
        raise ContentPackError(f"内容包资源引用未声明：{label} -> {value}")


def _validate_browser_references(
    stage: str,
    stage_payload: dict[str, object],
    resources_payload: dict[str, object],
    files: list[ContentPackFile],
) -> None:
    """校验 stage.json 和 resources.json 中会被浏览器请求的本地路径。"""

    declared = {item.path for item in files}
    _validate_local_reference(stage, stage_payload.get("image"), declared, "stage.image")
    _validate_local_reference(stage, stage_payload.get("resources"), declared, "stage.resources")
    minimap = stage_payload.get("minimap")
    if not isinstance(minimap, dict):
        raise ContentPackError("内容包缺少 minimap 模型")
    _validate_local_reference(stage, minimap.get("image"), declared, "stage.minimap.image")
    scenario_files = stage_payload.get("scenarioFiles")
    if isinstance(scenario_files, dict):
        for key, entry in scenario_files.items():
            if isinstance(entry, dict) and entry.get("available") is True:
                _validate_local_reference(stage, entry.get("path"), declared, f"scenarioFiles.{key}")
    common_model = stage_payload.get("commonModel")
    if isinstance(common_model, dict):
        heads = common_model.get("heads")
        if isinstance(heads, dict) and heads.get("available") is True:
            _validate_local_reference(stage, heads.get("path"), declared, "commonModel.heads.path")
            _validate_local_reference(stage, heads.get("image"), declared, "commonModel.heads.image")
    layers = resources_payload.get("layers")
    if not isinstance(layers, dict):
        raise ContentPackError("内容包 resources.json 缺少图层")
    for layer, entry in layers.items():
        if not isinstance(entry, dict):
            raise ContentPackError(f"内容包资源图层无效：{layer}")
        _validate_local_reference(stage, entry.get("image"), declared, f"resources.{layer}.image")
        _validate_local_reference(stage, entry.get("drawImage"), declared, f"resources.{layer}.drawImage")


def inspect_content_pack(archive_path: Path) -> ContentPackReport:
    """审计内容包路径、Manifest、大小和每个文件的内容哈希。"""

    archive_path = archive_path.expanduser().resolve()
    if not archive_path.is_file():
        raise ContentPackError(f"内容包不存在：{archive_path}")
    archive_sha256 = sha256_file(archive_path)
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ContentPackError(f"内容包不是有效 ZIP：{archive_path.name}") from exc
    with archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        normalized = [normalize_pack_path(info.filename) for info in infos]
        folded = [path.casefold() for path in normalized]
        if len(folded) != len(set(folded)):
            raise ContentPackError("内容包包含重复 ZIP 条目")
        info_by_path = dict(zip(normalized, infos))
        manifest_info = info_by_path.get(CONTENT_PACK_MANIFEST)
        if manifest_info is None:
            raise ContentPackError("内容包缺少 manifest.json")
        if manifest_info.file_size > 1024 * 1024:
            raise ContentPackError("内容包 Manifest 过大")
        try:
            payload = json.loads(archive.read(manifest_info).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContentPackError("内容包 Manifest 不是有效 UTF-8 JSON") from exc
        if not isinstance(payload, dict) or payload.get("format") != CONTENT_PACK_FORMAT:
            raise ContentPackError("内容包格式标识不受支持")
        if payload.get("content_schema") != CONTENT_PACK_SCHEMA:
            raise ContentPackError(f"内容包 Schema 不受支持：{payload.get('content_schema')}")
        stage = str(payload.get("stage") or "").lower()
        if not stage.startswith("stage") or not stage[5:].isdigit():
            raise ContentPackError(f"内容包关卡名称无效：{stage}")
        files = _manifest_files(payload, stage)
        expected = {CONTENT_PACK_MANIFEST, *(item.path for item in files)}
        actual = set(normalized)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            details = []
            if missing:
                details.append("缺少：" + "、".join(missing))
            if extra:
                details.append("未声明：" + "、".join(extra))
            raise ContentPackError("内容包 ZIP 与 Manifest 不一致；" + "；".join(details))
        for item in files:
            info = info_by_path[item.path]
            if info.file_size != item.bytes:
                raise ContentPackError(f"内容包文件大小不一致：{item.path}")
            if sha256_zip_entry(archive, info) != item.sha256:
                raise ContentPackError(f"内容包文件哈希不一致：{item.path}")
        try:
            stage_payload = json.loads(
                archive.read(info_by_path[content_path(stage, "stage.json")]).decode("utf-8")
            )
            resources_payload = json.loads(
                archive.read(info_by_path[content_path(stage, "resources.json")]).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContentPackError("内容包关卡描述不是有效 UTF-8 JSON") from exc
        if not isinstance(stage_payload, dict) or str(stage_payload.get("stage") or "").lower() != stage:
            raise ContentPackError("stage.json 与内容包关卡名称不一致")
        if not isinstance(resources_payload, dict):
            raise ContentPackError("resources.json 不是对象")
        _validate_browser_references(stage, stage_payload, resources_payload, files)

    return ContentPackReport(stage, archive_path, archive_sha256, files, payload)


def _source_manifest(report: object) -> list[dict[str, object]]:
    """生成不泄露本机绝对路径的来源文件摘要。"""

    return [
        {
            "role": str(item.role),
            "name": Path(item.path).name,
            "bytes": int(item.bytes),
            "sha256": str(item.sha256),
        }
        for item in report.files
    ]


def write_content_pack(stage_dir: Path, output_path: Path, source_inputs: list[dict[str, object]] | None = None) -> dict[str, object]:
    """把已生成关卡 Bundle 写为不携带 editor.html 的独立内容包。"""

    stage_dir = stage_dir.resolve()
    stage = stage_dir.name.lower()
    if not stage.startswith("stage") or not stage[5:].isdigit():
        raise ContentPackError(f"关卡目录名称无效：{stage_dir.name}")
    candidates = sorted(path for path in stage_dir.rglob("*") if path.is_file() and path.name.casefold() != "editor.html")
    files = [
        ContentPackFile(
            content_path(stage, path.relative_to(stage_dir).as_posix()),
            path.stat().st_size,
            sha256_file(path),
        )
        for path in candidates
    ]
    payload = {
        "format": CONTENT_PACK_FORMAT,
        "content_schema": CONTENT_PACK_SCHEMA,
        "stage": stage,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "editor_template_policy": "runtime-current",
        "source_policy": "user-generated",
        "source_inputs": list(source_inputs or []),
        "files": [item.to_dict() for item in files],
    }
    _manifest_files(payload, stage)
    try:
        stage_payload = json.loads((stage_dir / "stage.json").read_text(encoding="utf-8"))
        resources_payload = json.loads((stage_dir / "resources.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContentPackError("关卡 Bundle 描述不是有效 UTF-8 JSON") from exc
    if not isinstance(stage_payload, dict) or str(stage_payload.get("stage") or "").lower() != stage:
        raise ContentPackError("stage.json 与关卡目录名称不一致")
    if not isinstance(resources_payload, dict):
        raise ContentPackError("resources.json 不是对象")
    _validate_browser_references(stage, stage_payload, resources_payload, files)
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr(CONTENT_PACK_MANIFEST, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
            for item, source in zip(files, candidates):
                archive.write(source, item.path)
        report = inspect_content_pack(temp_path)
        os.replace(temp_path, output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return {
        "format": CONTENT_PACK_FORMAT,
        "stage": report.stage,
        "archive": str(output_path),
        "bytes": output_path.stat().st_size,
        "sha256": report.archive_sha256,
        "file_count": len(report.files),
    }


def build_content_pack(stage_path: Path, output_dir: Path) -> dict[str, object]:
    """校验用户原始文件，生成一次 Bundle 后封装为独立内容包。"""

    from san_tools.map.editor_runtime_session import validate_runtime_inputs
    from san_tools.map.export_editor_bundle import export_runtime_editor_bundle

    stage_path = stage_path.expanduser().resolve()
    report = validate_runtime_inputs(stage_path, stage_path.parent)
    report.require_valid()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / f".content-pack-build-{uuid.uuid4().hex}"
    work_dir.mkdir()
    try:
        data_dir = work_dir / "editor-data"
        export_runtime_editor_bundle(report, data_dir)
        return write_content_pack(
            data_dir / report.stage,
            output_dir / f"{report.stage}{CONTENT_PACK_SUFFIX}",
            _source_manifest(report),
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def default_content_cache_dir() -> Path:
    """返回用户级持久内容缓存目录；缺少本地数据目录时回退到系统临时目录。"""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "SanMapEditor" / "content-cache"
    return Path(tempfile.gettempdir()) / "SanMapEditor" / "content-cache"


def _safe_cache_child(cache_base: Path, candidate: Path) -> Path:
    """确认缓存目标是缓存根的直接子目录。"""

    base = cache_base.expanduser().resolve()
    resolved = candidate.expanduser().resolve()
    if resolved.parent != base or resolved == base:
        raise ContentPackError(f"内容缓存路径越界：{resolved}")
    return resolved


def _cache_is_reusable(cache_dir: Path, report: ContentPackReport) -> bool:
    """以缓存标记、文件大小和当前编辑器入口判断缓存能否复用。"""

    marker = cache_dir / CONTENT_CACHE_MARKER
    entry = cache_dir / "editor-data" / report.stage / "editor.html"
    if not marker.is_file() or not entry.is_file():
        return False
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if payload.get("archive_sha256") != report.archive_sha256 or payload.get("stage") != report.stage:
        return False
    stage_dir = cache_dir / "editor-data" / report.stage
    return all(
        (stage_dir / PurePosixPath(item.path).relative_to(PurePosixPath("content") / report.stage)).is_file()
        and (stage_dir / PurePosixPath(item.path).relative_to(PurePosixPath("content") / report.stage)).stat().st_size
        == item.bytes
        for item in report.files
    )


def load_content_pack(
    archive_path: Path,
    release_info: dict[str, object] | None = None,
    cache_base: Path | None = None,
) -> LoadedContentPack:
    """审计内容包并事务写入按归档哈希复用的持久缓存。"""

    from san_tools.map.export_editor_bundle import resolve_editor_template, write_editor_index, write_editor_template

    report = inspect_content_pack(archive_path)
    cache_base = (cache_base or default_content_cache_dir()).expanduser().resolve()
    cache_base.mkdir(parents=True, exist_ok=True)
    cache_dir = _safe_cache_child(cache_base, cache_base / report.archive_sha256)
    reused = _cache_is_reusable(cache_dir, report)
    created_at = time.time()
    if not reused:
        temp_dir = _safe_cache_child(cache_base, cache_base / f".{report.archive_sha256}.{uuid.uuid4().hex}")
        temp_dir.mkdir()
        try:
            data_dir = temp_dir / "editor-data"
            stage_dir = data_dir / report.stage
            stage_dir.mkdir(parents=True)
            with zipfile.ZipFile(report.archive_path) as archive:
                for item in report.files:
                    relative = PurePosixPath(item.path).relative_to(PurePosixPath("content") / report.stage)
                    target = stage_dir.joinpath(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item.path) as source, target.open("wb") as destination:
                        shutil.copyfileobj(source, destination, length=1024 * 1024)
            stage_payload = json.loads((stage_dir / "stage.json").read_text(encoding="utf-8"))
            write_editor_template(resolve_editor_template(data_dir), stage_dir / "editor.html")
            write_editor_index(
                data_dir,
                [{
                    "stage": report.stage,
                    "path": f"{report.stage}/editor.html",
                    "width": int(stage_payload.get("width") or 0),
                    "height": int(stage_payload.get("height") or 0),
                }],
            )
            runtime_info = dict(release_info or {})
            runtime_info.update({
                "active_stage": report.stage,
                "runtime_session": "content-pack-cache",
                "content_pack_sha256": report.archive_sha256,
            })
            (data_dir / "release-info.json").write_text(
                json.dumps(runtime_info, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (temp_dir / CONTENT_CACHE_MARKER).write_text(
                json.dumps({
                    "format": CONTENT_PACK_FORMAT,
                    "stage": report.stage,
                    "archive_sha256": report.archive_sha256,
                    "created_at": created_at,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            os.replace(temp_dir, cache_dir)
        except Exception:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise
    data_dir = cache_dir / "editor-data"
    # 每次载入都刷新当前程序模板和发布元数据，避免持久素材缓存固化旧编辑器代码。
    write_editor_template(resolve_editor_template(data_dir), data_dir / report.stage / "editor.html")
    runtime_info = dict(release_info or {})
    runtime_info.update({
        "active_stage": report.stage,
        "runtime_session": "content-pack-cache",
        "content_pack_sha256": report.archive_sha256,
    })
    (data_dir / "release-info.json").write_text(
        json.dumps(runtime_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return LoadedContentPack(
        root=cache_dir,
        data_dir=data_dir,
        stage=report.stage,
        entry_path=f"/{report.stage}/editor.html",
        report=report,
        created_at=created_at,
        reused=reused,
    )


def main() -> int:
    """解析独立内容包构建参数。"""

    parser = argparse.ArgumentParser(description="从用户合法游戏文件生成地图编辑器独立内容包")
    parser.add_argument("stage", type=Path, help="目标 stageXX.m 文件")
    parser.add_argument("--output-dir", type=Path, default=Path("dist/content-packs"), help="内容包输出目录")
    args = parser.parse_args()
    print(json.dumps(build_content_pack(args.stage, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
