"""验证正式发布构建不读取或打包任何游戏资源。"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from san_tools.map.build_editor_release import (
    EDITOR_TEMPLATE_SOURCE,
    EDITOR_TEMPLATE_TARGET,
    EXE_NAME,
    audit_pyinstaller_collection,
    prepare_release_package,
    editor_template_data_spec,
    sha256_file,
)
from san_tools.map.editor_release_audit import RELEASE_ALLOWED_FILES, ReleaseAuditError


ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / "derived" / "test_tmp" / "editor_resource_free_build"


class TestEditorResourceFreeBuild(unittest.TestCase):
    """覆盖干净目录组包、空入口与 PyInstaller 收集审计。"""

    def setUp(self) -> None:
        """为每项测试准备不含 data/game 和 data/text 的根目录。"""

        shutil.rmtree(TEST_TMP, ignore_errors=True)
        TEST_TMP.mkdir(parents=True)
        self.clean_root = TEST_TMP / "clean-root"
        docs = self.clean_root / "docs"
        docs.mkdir(parents=True)
        (docs / "EDITOR_USER_GUIDE.zh.md").write_text("# 无资源使用指南\n", encoding="utf-8")
        self.exe_source = TEST_TMP / f"{EXE_NAME}.exe"
        self.exe_source.write_bytes(b"fake-launcher")
        self.release_info = {
            "app_title": "三国霸业地图编辑器 2.0",
            "creator": "mzhinf",
            "build_date": "2026-07-16",
            "build_time": "2026-07-16 12:00:00",
            "resource_policy": "user-import-only",
            "runtime_session": "system-temp",
        }

    def test_clean_root_prepares_exact_resource_free_package(self) -> None:
        """没有任何游戏目录时仍能生成恰好命中白名单的发布结构。"""

        package = TEST_TMP / "package"
        manifest = prepare_release_package(
            self.clean_root,
            package,
            self.exe_source,
            self.release_info,
        )

        self.assertEqual({item["path"] for item in manifest}, set(RELEASE_ALLOWED_FILES))
        self.assertFalse(any(path.is_dir() and path.name.lower().startswith("stage") for path in package.rglob("*")))
        index = (package / "editor-data" / "index.html").read_text(encoding="utf-8")
        self.assertIn("尚未导入地图项目", index)
        self.assertNotIn("stage.json", index)
        self.assertNotIn("fetch(", index)
        release = json.loads((package / "editor-data" / "release-info.json").read_text(encoding="utf-8"))
        self.assertNotIn("stage", release)
        self.assertEqual(release["resource_policy"], "user-import-only")

    def test_release_builder_has_no_bundle_or_stage_argument(self) -> None:
        """正式发布脚本不得导入关卡导出器或保留 --stage 构建参数。"""

        source = (ROOT / "src" / "san_tools" / "map" / "build_editor_release.py").read_text(encoding="utf-8")
        self.assertNotIn("export_editor_bundle", source)
        self.assertNotIn('add_argument("--stage"', source)
        self.assertIn("audit_release_tree", source)
        self.assertIn("audit_release_zip", source)

    def test_pyinstaller_explicitly_embeds_runtime_editor_template(self) -> None:
        """冻结程序必须在模块同目录携带选择地图后使用的 HTML 模板。"""

        template = ROOT / EDITOR_TEMPLATE_SOURCE
        self.assertEqual(
            editor_template_data_spec(ROOT),
            f"{template.resolve()}:{EDITOR_TEMPLATE_TARGET}",
        )
        source = (ROOT / "src" / "san_tools" / "map" / "build_editor_release.py").read_text(encoding="utf-8")
        self.assertIn('"--add-data"', source)
        self.assertIn("editor_template_data_spec(root)", source)
        with self.assertRaisesRegex(FileNotFoundError, "运行时模板"):
            editor_template_data_spec(self.clean_root)

    def test_pyinstaller_toc_accepts_code_and_rejects_game_data(self) -> None:
        """PyInstaller 清单可包含代码模块，但不能引用构建机游戏数据。"""

        work = TEST_TMP / "pyinstaller"
        work.mkdir()
        safe_toc = work / "Analysis-00.toc"
        safe_toc.write_text(
            "[('editor_desktop_launcher', 'H:/repo/src/san_tools/map/editor_desktop_launcher.py', 'PYMODULE')]",
            encoding="utf-8",
        )
        self.assertEqual(audit_pyinstaller_collection(work), [safe_toc.as_posix()])

        bad_toc = work / "PKG-00.toc"
        bad_toc.write_text(
            "[('stage01.m', 'H:/repo/data/game/stage01.m', 'DATA')]",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ReleaseAuditError, "游戏资源"):
            audit_pyinstaller_collection(work)

    def test_sha256_file_uses_stable_content_hash(self) -> None:
        """外部构建清单的 ZIP 哈希必须由文件内容决定。"""

        payload = TEST_TMP / "payload.bin"
        payload.write_bytes(b"abc")
        self.assertEqual(
            sha256_file(payload),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )


if __name__ == "__main__":
    unittest.main()
