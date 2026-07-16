"""验证编辑器用户指南、打包链路文档和索引保持同步。"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestEditorDocumentation(unittest.TestCase):
    """检查面向用户和维护者的关键说明没有从发布链路脱落。"""

    def test_user_guide_covers_layout_workflows_and_shortcuts(self) -> None:
        """发布包用户指南必须覆盖第一次使用所需的完整闭环。"""

        guide = (ROOT / "docs" / "EDITOR_USER_GUIDE.zh.md").read_text(encoding="utf-8")
        for marker in (
            "启动编辑器", "先认识界面", "导入项目", "编辑地图图层", "区域复制",
            "势力管理", "据点和城门管理", "武将管理", "Raw 精确编辑", "校验和导出",
            "Ctrl+C", "Ctrl+X", "Ctrl+V", "Ctrl+Z", "Ctrl+Y", "Ctrl+Shift+Z",
        ):
            self.assertIn(marker, guide)

    def test_packaging_chain_lists_sources_outputs_and_tests(self) -> None:
        """打包文档必须标出入口、核心依赖、产物和验证文件。"""

        chain = (ROOT / "docs" / "EDITOR_PACKAGING_CHAIN.zh.md").read_text(encoding="utf-8")
        for marker in (
            "build_editor_release.py", "export_editor_bundle.py", "editor_desktop_launcher.py",
            "editor_app.html", "stage_ini_codec.py", "m.ksy", "stage.json",
            "SanMapEditor.spec", "SanMapEditor.exe", "编辑器使用指南.md",
            "editor_content_pack.py", "compose_editor_distribution.py", ".sanmap-pack",
            "test_editor_documentation.py",
        ):
            self.assertIn(marker, chain)

    def test_document_index_and_release_script_reference_guides(self) -> None:
        """新增文档必须进入索引，完整指南必须进入发布目录。"""

        index = (ROOT / "docs" / "DOCUMENT_INDEX.zh.md").read_text(encoding="utf-8")
        release = (ROOT / "src" / "san_tools" / "map" / "build_editor_release.py").read_text(encoding="utf-8")
        self.assertIn("EDITOR_USER_GUIDE.zh.md", index)
        self.assertIn("EDITOR_PACKAGING_CHAIN.zh.md", index)
        self.assertIn("EDITOR_CONTENT_PACK.zh.md", index)
        self.assertTrue((ROOT / "docs" / "EDITOR_CONTENT_PACK.zh.md").is_file())
        self.assertIn("write_release_guides", release)
        self.assertIn("编辑器使用指南.md", release)


if __name__ == "__main__":
    unittest.main()
