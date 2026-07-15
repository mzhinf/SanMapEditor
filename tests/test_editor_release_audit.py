"""验证无资源地图编辑器发布白名单与 ZIP 审计。"""

from __future__ import annotations

import warnings
import shutil
import unittest
import zipfile
from pathlib import Path

from san_tools.map.editor_release_audit import (
    RELEASE_ALLOWED_FILES,
    ReleaseAuditError,
    audit_release_tree,
    audit_release_zip,
    forbidden_release_reason,
    sha256_bytes,
    validate_release_paths,
)


ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / "derived" / "test_tmp" / "editor_release_audit"


class TestEditorReleaseAudit(unittest.TestCase):
    """覆盖发布目录、ZIP 和禁用资源路径。"""

    def setUp(self) -> None:
        """为每项测试创建干净的可写目录。"""

        shutil.rmtree(TEST_TMP, ignore_errors=True)
        TEST_TMP.mkdir(parents=True)

    def _write_allowed_tree(self, root: Path) -> None:
        """写入最小无资源发布结构。"""

        for relative in RELEASE_ALLOWED_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"测试文件：{relative}".encode("utf-8"))

    def test_tree_manifest_records_path_size_and_sha256(self) -> None:
        """目录审计必须覆盖全部白名单文件并记录稳定哈希。"""

        package = TEST_TMP / "package"
        self._write_allowed_tree(package)

        manifest = audit_release_tree(package)

        self.assertEqual([item["path"] for item in manifest], sorted(RELEASE_ALLOWED_FILES))
        expected = "测试文件：editor-data/index.html".encode("utf-8")
        index_entry = next(item for item in manifest if item["path"] == "editor-data/index.html")
        self.assertEqual(index_entry["bytes"], len(expected))
        self.assertEqual(index_entry["sha256"], sha256_bytes(expected))

    def test_tree_rejects_stage_directory_and_derived_resource(self) -> None:
        """即使其他文件完整，也必须拒绝关卡目录和派生资源。"""

        package = TEST_TMP / "package"
        self._write_allowed_tree(package)
        stage_json = package / "editor-data" / "stage01" / "stage.json"
        stage_json.parent.mkdir(parents=True)
        stage_json.write_text("{}", encoding="utf-8")

        with self.assertRaisesRegex(ReleaseAuditError, "stage"):
            audit_release_tree(package)

    def test_forbidden_rules_cover_original_and_generated_files(self) -> None:
        """禁用规则覆盖计划列出的原始文件、Sidecar 与图集。"""

        forbidden = (
            "editor-data/stage01/editor.html",
            "stage01.m",
            "stage01.dor",
            "stage01.stg",
            "stage01.s",
            "stage01.x",
            "stage.ini",
            "History.txt",
            "heads.dat",
            "kingdom.cel",
            "kingdom.atr",
            "stage_ini.xlsx",
            "map.png",
            "minimap.png",
            "heads.png",
            "draw_acwx.png",
            "resources_acwz.png",
            "stage.json",
            "resources.json",
        )
        self.assertTrue(all(forbidden_release_reason(path) for path in forbidden))

    def test_exact_whitelist_rejects_unknown_ui_file(self) -> None:
        """普通图片也不能只凭扩展名放行，必须显式加入白名单。"""

        paths = list(RELEASE_ALLOWED_FILES) + ["editor-data/logo.png"]
        with self.assertRaisesRegex(ReleaseAuditError, "非白名单"):
            validate_release_paths(paths)

    def test_zip_audit_rejects_duplicate_and_path_traversal(self) -> None:
        """ZIP 审计必须在读取内容前拒绝重复项与路径穿越。"""

        duplicate = TEST_TMP / "duplicate.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("editor-data/index.html", "a")
                archive.writestr("editor-data/index.html", "b")
        with self.assertRaisesRegex(ReleaseAuditError, "重复路径"):
            audit_release_zip(duplicate)

        traversal = TEST_TMP / "traversal.zip"
        with zipfile.ZipFile(traversal, "w") as archive:
            archive.writestr("../stage01.m", "bad")
        with self.assertRaisesRegex(ReleaseAuditError, "安全相对路径"):
            audit_release_zip(traversal)

        drive_path = TEST_TMP / "drive-path.zip"
        with zipfile.ZipFile(drive_path, "w") as archive:
            archive.writestr("C:/stage01.m", "bad")
        with self.assertRaisesRegex(ReleaseAuditError, "安全相对路径"):
            audit_release_zip(drive_path)

    def test_zip_manifest_matches_clean_tree(self) -> None:
        """干净 ZIP 的条目清单必须与目录清单一致。"""

        package = TEST_TMP / "package"
        self._write_allowed_tree(package)
        archive_path = Path(shutil.make_archive(str(TEST_TMP / "release"), "zip", package))

        self.assertEqual(audit_release_zip(archive_path), audit_release_tree(package))


if __name__ == "__main__":
    unittest.main()
