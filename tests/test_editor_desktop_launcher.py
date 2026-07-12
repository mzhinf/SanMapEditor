"""验证地图编辑器桌面启动器与发布脚本。"""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from san_tools.map.build_editor_release import ensure_safe_work_dir
from san_tools.map.editor_desktop_launcher import check_editor_data, create_editor_server, editor_entry_path, find_editor_data_dir


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
        stage_dir = root / "stage01"
        stage_dir.mkdir()
        (stage_dir / "editor.html").write_text("editor", encoding="utf-8")
        self.assertEqual(find_editor_data_dir(root), root.resolve())
        self.assertEqual(editor_entry_path(root, "stage01"), "/stage01/editor.html")
        self.assertEqual(check_editor_data(root, "stage01"), 0)

    def test_server_only_listens_on_loopback(self) -> None:
        """桌面服务必须使用本机随机端口，不能暴露到局域网。"""

        server = create_editor_server(TEST_TMP)
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            self.assertGreater(server.server_address[1], 0)
        finally:
            server.server_close()

    def test_release_work_dir_must_stay_inside_project(self) -> None:
        """发布脚本不得清理项目外部目录或项目根目录。"""

        root = TEST_TMP.resolve()
        self.assertEqual(ensure_safe_work_dir(root, root / "derived" / "release"), root / "derived" / "release")
        with self.assertRaises(ValueError):
            ensure_safe_work_dir(root, root)
        with self.assertRaises(ValueError):
            ensure_safe_work_dir(root, root.parent / "outside")


if __name__ == "__main__":
    unittest.main()
