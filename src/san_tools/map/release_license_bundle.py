"""根据冻结归档的实际收集清单生成公开发布包许可证文件。"""

from __future__ import annotations

import ast
import importlib.metadata
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


LICENSE_DIR_NAME = "licenses"
PROJECT_LICENSE_NAME = "LICENSE.txt"
THIRD_PARTY_NOTICES_NAME = "THIRD-PARTY-NOTICES.txt"
ENTRY_KINDS = frozenset({"BINARY", "DATA", "EXTENSION", "PYMODULE", "PYSOURCE"})
NATIVE_ENTRY_KINDS = frozenset({"BINARY", "EXTENSION"})


class ReleaseLicenseError(ValueError):
    """表示冻结归档的许可证来源或原生库来源不可安全确认。"""


@dataclass(frozen=True)
class TocEntry:
    """保存 PyInstaller TOC 中一个已经过滤的归档条目。"""

    destination: str
    source: Path
    kind: str


@dataclass(frozen=True)
class TocCatalog:
    """分开保存模块分析清单与最终归档清单，避免只检查其中之一。"""

    analysis_entries: tuple[TocEntry, ...]
    package_entries: tuple[TocEntry, ...]

    @property
    def all_entries(self) -> tuple[TocEntry, ...]:
        """返回去重后的全部最终收集来源。"""

        return tuple(sorted(set(self.analysis_entries + self.package_entries), key=_entry_sort_key))


@dataclass(frozen=True)
class LicenseComponent:
    """描述一个实际进入冻结程序的第三方组件及其许可证文件。"""

    name: str
    version: str
    license_name: str
    license_sources: tuple[tuple[str, Path], ...]
    native_files: tuple[str, ...]


def _entry_sort_key(entry: TocEntry) -> tuple[str, str, str]:
    """让 TOC 解析和声明文件在不同文件系统上保持稳定排序。"""

    return (entry.destination.lower(), str(entry.source).lower(), entry.kind)


def _normalized_path(path: Path | str) -> str:
    """把 Windows 与 POSIX 路径统一为小写斜杠形式用于来源匹配。"""

    return str(path).replace("\\", "/").lower()


def _is_under(path: Path, parent: Path) -> bool:
    """判断路径是否位于指定目录，且不依赖字符串前缀比较。"""

    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _read_toc_entries(toc_path: Path) -> tuple[TocEntry, ...]:
    """从 Python 字面量 TOC 中递归取出真实归档三元组。"""

    try:
        payload = ast.literal_eval(toc_path.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError) as exc:
        raise ReleaseLicenseError(f"无法解析冻结归档清单：{toc_path}") from exc

    entries: set[TocEntry] = set()

    def visit(value: object) -> None:
        if (
            isinstance(value, tuple)
            and len(value) >= 3
            and all(isinstance(item, str) for item in value[:3])
            and value[2] in ENTRY_KINDS
        ):
            entries.add(TocEntry(value[0], Path(value[1]), value[2]))
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(payload)
    return tuple(sorted(entries, key=_entry_sort_key))


def _find_single_toc(work_dir: Path, pattern: str) -> Path:
    """要求每次构建恰有一份目标 TOC，避免误用历史构建记录。"""

    candidates = sorted(work_dir.rglob(pattern))
    if len(candidates) != 1:
        raise ReleaseLicenseError(f"冻结归档清单数量异常（{pattern}）：{work_dir}")
    return candidates[0]


def load_toc_catalog(work_dir: Path) -> TocCatalog:
    """读取模块分析与最终 PKG 清单，作为许可证声明的唯一组件依据。"""

    return TocCatalog(
        analysis_entries=_read_toc_entries(_find_single_toc(work_dir, "Analysis-*.toc")),
        package_entries=_read_toc_entries(_find_single_toc(work_dir, "PKG-*.toc")),
    )


def _distribution_info_dir(distribution_name: str) -> tuple[str, Path, Path]:
    """返回安装分发的版本、元数据目录和 site-packages 根目录。"""

    distribution = importlib.metadata.distribution(distribution_name)
    # importlib.metadata 没有公开的 dist-info 目录属性；该路径由标准库实现维护。
    info_dir = Path(distribution._path)
    return distribution.version, info_dir, info_dir.parent


def _package_entries(catalog: TocCatalog, package_dir_name: str) -> tuple[TocEntry, ...]:
    """返回来自给定 site-packages 包目录的实际分析条目。"""

    marker = f"/site-packages/{package_dir_name.lower()}/"
    return tuple(entry for entry in catalog.all_entries if marker in _normalized_path(entry.source))


def _require_package_entries(catalog: TocCatalog, package_dir_name: str) -> tuple[TocEntry, ...]:
    """要求声明组件真实出现在最终模块图中，避免按开发依赖猜测。"""

    entries = _package_entries(catalog, package_dir_name)
    if not entries:
        raise ReleaseLicenseError(f"冻结归档未收集要求的运行时组件：{package_dir_name}")
    return entries


def _native_destinations(entries: tuple[TocEntry, ...], predicate: object) -> tuple[str, ...]:
    """提取最终 PKG 内属于某组件的原生文件名。"""

    matcher = predicate
    names = {
        entry.destination.replace("\\", "/")
        for entry in entries
        if entry.kind in NATIVE_ENTRY_KINDS and callable(matcher) and matcher(entry)
    }
    return tuple(sorted(names, key=str.lower))


def _is_tcl_tk_entry(entry: TocEntry) -> bool:
    """识别 Tcl/Tk 脚本、DLL 与 `_tkinter` 扩展的来源。"""

    source = _normalized_path(entry.source)
    destination = entry.destination.replace("\\", "/").lower()
    return "/tcl/" in source or destination in {"tcl86t.dll", "tk86t.dll", "_tkinter.pyd"}


def _assert_known_native_origins(catalog: TocCatalog) -> None:
    """拒绝开发机 PATH 等位置注入的未知原生文件，防止遗漏许可证。"""

    runtime_root = Path(sys.base_prefix)
    _, _, site_packages = _distribution_info_dir("Pillow")
    unknown = [
        entry
        for entry in catalog.package_entries
        if entry.kind in NATIVE_ENTRY_KINDS
        and entry.source
        and not _is_under(entry.source, runtime_root)
        and not _is_under(entry.source, site_packages)
    ]
    if unknown:
        details = "；".join(f"{entry.destination} <- {entry.source}" for entry in sorted(unknown, key=_entry_sort_key))
        raise ReleaseLicenseError(f"冻结归档包含未映射的原生库来源：{details}")


def _tcl_tk_license_source(catalog: TocCatalog) -> tuple[str, Path]:
    """从实际 Tcl/Tk 数据条目寻找随运行时分发的原始 license.terms。"""

    candidates = [
        entry.source
        for entry in catalog.analysis_entries
        if entry.source.name.lower() == "license.terms" and "/tcl/tk" in _normalized_path(entry.source)
    ]
    if len(candidates) != 1:
        raise ReleaseLicenseError("无法从冻结归档确认唯一的 Tcl/Tk license.terms")
    source = candidates[0]
    version_match = re.search(r"/tk(\d+\.\d+)/", _normalized_path(source))
    if not version_match:
        raise ReleaseLicenseError(f"无法从 Tcl/Tk 路径取得版本号：{source}")
    return version_match.group(1), source


def collect_license_components(work_dir: Path) -> tuple[LicenseComponent, ...]:
    """按最终 TOC 收集固定运行时组件，并返回原文复制计划。"""

    catalog = load_toc_catalog(work_dir)
    _assert_known_native_origins(catalog)
    runtime_root = Path(sys.base_prefix)
    python_license = runtime_root / "LICENSE.txt"
    if not python_license.is_file():
        raise ReleaseLicenseError(f"缺少 Python 完整许可证栈：{python_license}")

    python_entries = [
        entry
        for entry in catalog.analysis_entries
        if entry.destination.lower().startswith("python") and entry.destination.lower().endswith(".dll")
    ]
    if not python_entries:
        raise ReleaseLicenseError("冻结归档未收集 Python 运行时 DLL")

    tcl_version, tcl_license = _tcl_tk_license_source(catalog)
    _require_package_entries(catalog, "openpyxl")
    _require_package_entries(catalog, "et_xmlfile")
    _require_package_entries(catalog, "pil")
    openpyxl_version, openpyxl_info, _ = _distribution_info_dir("openpyxl")
    et_xmlfile_version, et_xmlfile_info, _ = _distribution_info_dir("et_xmlfile")
    pillow_version, pillow_info, site_packages = _distribution_info_dir("Pillow")

    required_files = (
        openpyxl_info / "LICENCE.rst",
        et_xmlfile_info / "LICENCE.python",
        et_xmlfile_info / "LICENCE.rst",
        et_xmlfile_info / "AUTHORS.txt",
        pillow_info / "licenses" / "LICENSE",
    )
    missing = [path for path in required_files if not path.is_file()]
    if missing:
        raise ReleaseLicenseError("缺少运行时组件许可证原文：" + "；".join(str(path) for path in missing))

    python_native = _native_destinations(
        catalog.package_entries,
        lambda entry: _is_under(entry.source, runtime_root) and not _is_tcl_tk_entry(entry),
    )
    tcl_native = _native_destinations(catalog.package_entries, _is_tcl_tk_entry)
    pillow_native = _native_destinations(
        catalog.package_entries,
        lambda entry: _is_under(entry.source, site_packages / "PIL"),
    )
    return (
        LicenseComponent(
            "Python",
            sys.version.split()[0],
            "Python Software Foundation License Version 2 and accompanying license stack",
            ((f"Python-{sys.version.split()[0]}-LICENSE.txt", python_license),),
            python_native,
        ),
        LicenseComponent(
            "Tcl/Tk",
            tcl_version,
            "Tcl/Tk License Terms",
            ((f"Tcl-Tk-{tcl_version}-license.terms", tcl_license),),
            tcl_native,
        ),
        LicenseComponent(
            "openpyxl",
            openpyxl_version,
            "MIT License",
            ((f"openpyxl-{openpyxl_version}-LICENCE.rst", openpyxl_info / "LICENCE.rst"),),
            (),
        ),
        LicenseComponent(
            "et_xmlfile",
            et_xmlfile_version,
            "MIT License and accompanying Python license information",
            (
                (f"et_xmlfile-{et_xmlfile_version}-LICENCE.rst", et_xmlfile_info / "LICENCE.rst"),
                (f"et_xmlfile-{et_xmlfile_version}-LICENCE.python", et_xmlfile_info / "LICENCE.python"),
                (f"et_xmlfile-{et_xmlfile_version}-AUTHORS.txt", et_xmlfile_info / "AUTHORS.txt"),
            ),
            (),
        ),
        LicenseComponent(
            "Pillow",
            pillow_version,
            "MIT-CMU; the license text also covers bundled image codec native components",
            ((f"Pillow-{pillow_version}-LICENSE.txt", pillow_info / "licenses" / "LICENSE"),),
            pillow_native,
        ),
    )


def audit_editor_template_assets(root: Path) -> None:
    """拒绝未登记的前端外部脚本、样式、字体和 SVG 图标资产。"""

    template = root / "src" / "san_tools" / "map" / "editor_app.html"
    source = template.read_text(encoding="utf-8")
    forbidden_patterns = {
        "外链 JavaScript": r"<script\b[^>]*\bsrc\s*=",
        "外链 CSS 或图标": r"<link\b[^>]*\bhref\s*=",
        "外链图片或媒体": r"<(?:img|source|video|audio)\b[^>]*\bsrc\s*=",
        "SVG 图标引用": r"<(?:svg|use)\b",
    }
    style_blocks = "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style\s*>", source, flags=re.IGNORECASE | re.DOTALL))
    if re.search(r"@font-face|url\s*\(", style_blocks, flags=re.IGNORECASE):
        raise ReleaseLicenseError("编辑器页面包含未登记的 Web 字体或 CSS 外部资源")
    for asset_type, pattern in forbidden_patterns.items():
        if re.search(pattern, source, flags=re.IGNORECASE):
            raise ReleaseLicenseError(f"编辑器页面包含未登记的{asset_type}")


def _render_notices(components: tuple[LicenseComponent, ...]) -> str:
    """生成供最终用户查阅的英文平铺式第三方组件声明。"""

    display_names = {
        "Python": "Python Runtime and Standard Libraries",
        "Tcl/Tk": "Tcl/Tk Graphics Kit",
        "Pillow": "Pillow (PIL Fork)",
    }
    separator = "========================================================================"
    lines = [
        separator,
        "THIRD-PARTY SOFTWARE NOTICES AND INFORMATION",
        separator,
        "",
        "This application incorporates third-party open-source software and components.",
        "The original software and source code remain the property of their respective owners.",
        "",
        'The full license texts for these third-party components can be found in the',
        '"licenses/" directory included with this distribution.',
        "",
    ]
    for index, component in enumerate(components, start=1):
        lines.extend(
            (
                separator,
                f"{index}. {display_names.get(component.name, component.name)}",
                separator,
                f"Component Name:  {component.name}",
                f"Version:         {component.version}",
                f"License Type:    {component.license_name}",
                "License File:",
            )
        )
        lines.extend(f"                 {LICENSE_DIR_NAME}/{file_name}" for file_name, _ in component.license_sources)
        if component.native_files:
            lines.append("Bundled Native Files:")
            lines.extend(f"                 {file_name}" for file_name in component.native_files)
        lines.append("")
    lines.extend(
        (
            separator,
            f"{len(components) + 1}. Front-End Static Asset Audit",
            separator,
            "Component Name:  editor_app.html",
            "Status:          No third-party JavaScript, CSS, web font, or SVG icon is included.",
            "",
        )
    )
    return "\n".join(lines)

def write_release_license_bundle(root: Path, package_dir: Path, work_dir: Path) -> tuple[LicenseComponent, ...]:
    """复制项目与第三方许可证原文，并写入最终发布包的声明文件。"""

    audit_editor_template_assets(root)
    components = collect_license_components(work_dir)
    project_license = root / "LICENSE"
    if not project_license.is_file():
        raise FileNotFoundError(f"缺少项目许可证：{project_license}")
    shutil.copy2(project_license, package_dir / PROJECT_LICENSE_NAME)
    licenses_dir = package_dir / LICENSE_DIR_NAME
    licenses_dir.mkdir()
    copied_names: set[str] = set()
    for component in components:
        for file_name, source in component.license_sources:
            if file_name in copied_names:
                raise ReleaseLicenseError(f"许可证文件名重复：{file_name}")
            shutil.copy2(source, licenses_dir / file_name)
            copied_names.add(file_name)
    (package_dir / THIRD_PARTY_NOTICES_NAME).write_text(_render_notices(components), encoding="utf-8-sig")
    return components
