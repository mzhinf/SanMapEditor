"""验证编辑器模板中的创建者和动态打包日期。"""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from san_tools.map.export_editor_bundle import EDITOR_BUILD_DATE_TOKEN, write_editor_template


ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / "derived" / "test_tmp" / "editor_build_metadata"


class TestEditorBuildMetadata(unittest.TestCase):
    """覆盖模板占位符替换和创建者显示。"""

    def setUp(self) -> None:
        """为每个测试准备固定可写目录。"""

        shutil.rmtree(TEST_TMP, ignore_errors=True)
        TEST_TMP.mkdir(parents=True, exist_ok=True)

    def test_write_editor_template_replaces_build_date(self) -> None:
        """导出 bundle 时必须写入实际日期，不能留下占位符。"""

        template = TEST_TMP / "template.html"
        output = TEST_TMP / "editor.html"
        template.write_text(f"创建者：mzhinf 打包日期：{EDITOR_BUILD_DATE_TOKEN}", encoding="utf-8")

        write_editor_template(template, output, "2026-07-13")

        rendered = output.read_text(encoding="utf-8")
        self.assertEqual(rendered, "创建者：mzhinf 打包日期：2026-07-13")
        self.assertNotIn(EDITOR_BUILD_DATE_TOKEN, rendered)


if __name__ == "__main__":
    unittest.main()
