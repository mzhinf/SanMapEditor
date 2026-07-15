"""验证地图编辑器桌面启动器与发布脚本。"""

from __future__ import annotations

import shutil
import threading
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from san_tools.map.build_editor_release import ensure_safe_work_dir, write_release_guides
from san_tools.map.editor_desktop_launcher import (
    APP_TITLE,
    LAUNCHER_FAILED,
    LAUNCHER_LOADED,
    LauncherRuntimeController,
    ReplaceCurrentSessionError,
    check_editor_data,
    create_editor_server,
    editor_entry_path,
    find_editor_data_dir,
    load_release_info,
)
from san_tools.map.editor_runtime_session import RuntimeInputError


ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / 'derived' / 'test_tmp' / 'editor_desktop_launcher'


class TestEditorDesktopLauncher(unittest.TestCase):
    """覆盖发布包路径识别和本机服务器约束。"""

    @classmethod
    def setUpClass(cls) -> None:
        """准备位于项目可写目录内的测试临时根目录。"""

        shutil.rmtree(TEST_TMP, ignore_errors=True)
        TEST_TMP.mkdir(parents=True, exist_ok=True)

    def test_finds_explicit_editor_data_and_stage_entry(self) -> None:
        """显式数据目录有效时优先打开指定关卡。"""

        root = TEST_TMP / "explicit-data"
        root.mkdir()
        (root / "index.html").write_text("index", encoding="utf-8")
        (root / "index.json").write_text("{}", encoding="utf-8")
        (root / "release-info.json").write_text('{"app_title": "三国霸业地图编辑器 2.0", "creator": "mzhinf", "build_date": "2026-07-13", "build_time": "2026-07-13 17:30:00"}', encoding="utf-8")
        stage_dir = root / "stage01"
        stage_dir.mkdir()
        (stage_dir / "editor.html").write_text("editor", encoding="utf-8")
        self.assertEqual(find_editor_data_dir(root), root.resolve())
        self.assertEqual(editor_entry_path(root, "stage01"), "/stage01/editor.html")
        self.assertEqual(check_editor_data(root, "stage01"), 0)
        self.assertEqual(load_release_info(root), {'app_title': APP_TITLE, 'creator': 'mzhinf', 'build_date': '2026-07-13', 'build_time': '2026-07-13 17:30:00'})

    def test_resource_free_data_does_not_require_index_json(self) -> None:
        """无资源发布目录只有空入口和版本信息也必须可启动。"""

        root = TEST_TMP / "resource-free-data"
        root.mkdir()
        (root / "index.html").write_text("尚未导入", encoding="utf-8")
        (root / "release-info.json").write_text('{"app_title": "测试编辑器"}', encoding="utf-8")
        self.assertEqual(find_editor_data_dir(root), root.resolve())
        self.assertEqual(editor_entry_path(root), "/index.html")
        self.assertEqual(check_editor_data(root, "stage01"), 0)

    def test_release_check_rejects_missing_runtime_editor_template(self) -> None:
        """发布检查必须覆盖选择地图后才会读取的冻结 HTML 模板。"""

        root = TEST_TMP / "missing-template-data"
        root.mkdir()
        (root / "index.html").write_text("尚未导入", encoding="utf-8")
        with patch(
            "san_tools.map.export_editor_bundle.resolve_editor_template",
            side_effect=FileNotFoundError("找不到编辑器模板"),
        ):
            self.assertEqual(check_editor_data(root, "stage01"), 4)


    def test_server_only_listens_on_loopback(self) -> None:
        """桌面服务必须使用本机随机端口，不能暴露到局域网。"""

        server = create_editor_server(TEST_TMP)
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            self.assertGreater(server.server_address[1], 0)
        finally:
            server.server_close()

    def test_release_package_contains_full_user_guide(self) -> None:
        """发布目录必须同时包含短说明和完整用户指南。"""

        root = TEST_TMP / "guide-root"
        docs = root / "docs"
        package = root / "package"
        docs.mkdir(parents=True)
        package.mkdir()
        (docs / "EDITOR_USER_GUIDE.zh.md").write_text("# 测试指南\n\n先导出再关闭。\n", encoding="utf-8")

        write_release_guides(root, package, "2026-07-14 12:00:00")

        self.assertEqual((package / "编辑器使用指南.md").read_text(encoding="utf-8"), "# 测试指南\n\n先导出再关闭。\n")
        short_guide = (package / "使用说明.txt").read_text(encoding="utf-8-sig")
        self.assertIn("完整解压", short_guide)
        self.assertIn("编辑器使用指南.md", short_guide)

    def test_release_work_dir_must_stay_inside_project(self) -> None:
        """发布脚本不得清理项目外部目录或项目根目录。"""

        root = TEST_TMP.resolve()
        self.assertEqual(ensure_safe_work_dir(root, root / "derived" / "release"), root / "derived" / "release")
        with self.assertRaises(ValueError):
            ensure_safe_work_dir(root, root)
        with self.assertRaises(ValueError):
            ensure_safe_work_dir(root, root.parent / "outside")


    def test_server_switches_runtime_content_on_same_loopback_port(self) -> None:
        """会话成功后应在同一端口把后续请求切换到临时目录。"""

        first = TEST_TMP / "switch-first"
        second = TEST_TMP / "switch-second"
        first.mkdir()
        second.mkdir()
        (first / "index.html").write_text("空项目", encoding="utf-8")
        (second / "index.html").write_text("已加载", encoding="utf-8")
        server = create_editor_server(first)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/index.html"
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                self.assertEqual(response.read().decode("utf-8"), "空项目")
            server.switch_data_dir(second)
            with urllib.request.urlopen(url, timeout=2) as response:
                self.assertEqual(response.read().decode("utf-8"), "已加载")
            self.assertEqual(server.current_data_dir(), second.resolve())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_runtime_controller_tracks_success_confirmation_and_failed_reimport(self) -> None:
        """控制器必须覆盖空项目、成功、替换确认和失败保留旧会话。"""

        manager = Mock()
        manager.current = None
        manager.cleanup_stale.return_value = []
        report = SimpleNamespace(files=[object()] * 9, warnings=["可选文件未提供"])
        session = SimpleNamespace(
            stage="stage01",
            report=report,
            data_dir=TEST_TMP / "runtime-data",
            entry_path="/stage01/editor.html",
        )

        def create_session(*_args, **_kwargs):
            manager.current = session
            return session

        manager.create_from_stage.side_effect = create_session
        controller = LauncherRuntimeController(
            {"app_title": "测试编辑器"},
            manager=manager,
        )
        self.assertEqual(controller.cleanup_stale(), [])
        loaded = controller.import_stage(TEST_TMP / "stage01.m")
        self.assertIs(loaded, session)
        self.assertEqual(controller.state, LAUNCHER_LOADED)
        self.assertIn("9 个输入文件", controller.message)

        with self.assertRaises(ReplaceCurrentSessionError):
            controller.import_stage(TEST_TMP / "stage02.m")
        self.assertEqual(manager.create_from_stage.call_count, 1)

        manager.create_from_stage.side_effect = RuntimeInputError("缺少文件：stage02.x")
        with self.assertRaisesRegex(RuntimeInputError, "stage02.x"):
            controller.import_stage(TEST_TMP / "stage02.m", replace_confirmed=True)
        self.assertEqual(controller.state, LAUNCHER_FAILED)
        self.assertIs(controller.current, session)
        controller.close()
        manager.close.assert_called_once_with()

if __name__ == "__main__":
    unittest.main()
