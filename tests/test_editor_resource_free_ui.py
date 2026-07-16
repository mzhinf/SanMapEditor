"""验证无资源发布的启动器状态与浏览器替换边界。"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR_HTML = ROOT / "src" / "san_tools" / "map" / "editor_app.html"
LAUNCHER = ROOT / "src" / "san_tools" / "map" / "editor_desktop_launcher.py"


class TestResourceFreeEditorUi(unittest.TestCase):
    """覆盖空项目导入、替换确认和 Sidecar 完整导出约束。"""

    def test_launcher_contains_all_runtime_import_states(self) -> None:
        """桌面启动器必须明确呈现空、导入中、失败和已加载状态。"""

        source = LAUNCHER.read_text(encoding="utf-8")

        for value in (
            "LAUNCHER_EMPTY",
            "LAUNCHER_IMPORTING",
            "LAUNCHER_FAILED",
            "LAUNCHER_LOADED",
            "选择 stageNN.m",
            "选择资源目录",
            "cleanup_stale",
            "switch_data_dir",
        ):
            self.assertIn(value, source)

    def test_browser_reimport_requires_explicit_replacement_confirmation(self) -> None:
        """浏览器重新导入 .m 前必须确认会替换当前项目。"""

        html = EDITOR_HTML.read_text(encoding="utf-8")

        self.assertIn("window.confirm(", html)
        self.assertIn("替换当前浏览器会话中的地图与管理数据", html)
        self.assertIn("已取消替换当前项目", html)

    def test_browser_export_never_zero_fills_missing_sidecar_tail(self) -> None:
        """缺少用户 .s/.x 尾区时必须阻止导出，不得静默补零。"""

        html = EDITOR_HTML.read_text(encoding="utf-8")

        self.assertIn("用户原始尾区，已阻止导出", html)
        self.assertNotIn("new Uint8Array(tailLength)", html)
        self.assertNotIn("usedFallbackTail", html)
        self.assertNotIn("0 填充", html)


if __name__ == "__main__":
    unittest.main()
