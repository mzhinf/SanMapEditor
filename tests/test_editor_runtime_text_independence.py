"""验证运行时 stage.ini 与 CP950 路径不依赖仓库文本母表。"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from san_tools.map.export_editor_bundle import (
    STAGE_INI_CASTLE_HEADERS,
    STAGE_INI_GENERAL_HEADERS,
    build_cp950_char_map,
    build_runtime_stage_ini_patch_model,
    build_stage_ini_patch_model,
)


ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = ROOT / "data" / "game"
TEXT_DIR = ROOT / "data" / "text"


class TestRuntimeCp950Map(unittest.TestCase):
    """覆盖完整字符映射的编码一致性。"""

    def test_cp950_map_contains_all_canonical_printable_characters(self) -> None:
        """映射中的每个字符都必须与 Python CP950 编码器逐字节一致。"""

        char_map = build_cp950_char_map()

        self.assertGreater(len(char_map), 13000)
        for char in "劉飛羽晉臺灣龍馬國":
            self.assertIn(char, char_map)
        for char, raw in char_map.items():
            self.assertEqual(bytes(raw), char.encode("cp950"), char)


@unittest.skipUnless(
    (GAME_DIR / "stage.ini").is_file(),
    "缺少 data/game/stage.ini",
)
class TestRuntimeStageIniModel(unittest.TestCase):
    """覆盖内置格式定义、字段位置和追加布局。"""

    def test_runtime_model_does_not_call_text_directory_locator(self) -> None:
        """即使文本目录定位器强制失败，运行时模型也必须完整可用。"""

        with patch(
            "san_tools.map.export_editor_bundle.find_text_data_dir",
            side_effect=AssertionError("不得读取 data/text"),
        ):
            model = build_runtime_stage_ini_patch_model(GAME_DIR)

        self.assertTrue(model["available"])
        self.assertEqual(model["source"], "user stage.ini + built-in format definitions")
        self.assertEqual(
            model["workbookSheets"][0]["headers"],
            ["row_id", "title", *STAGE_INI_GENERAL_HEADERS],
        )
        self.assertEqual(
            model["workbookSheets"][1]["headers"],
            ["row_id", "title", *STAGE_INI_CASTLE_HEADERS],
        )
        self.assertEqual(len(model["workbookSheets"][0]["rows"]), 277)
        self.assertEqual(len(model["workbookSheets"][1]["rows"]), 42)

    @unittest.skipUnless(
        (TEXT_DIR / "general.txt").is_file() and (TEXT_DIR / "castle.txt").is_file(),
        "缺少用于一次性对照的 data/text 字段表",
    )
    def test_built_in_headers_and_layout_match_legacy_analysis(self) -> None:
        """内置定义必须与旧文本分析产生的稳定回写模型一致。"""

        runtime_model = build_runtime_stage_ini_patch_model(GAME_DIR)
        legacy_model = build_stage_ini_patch_model(ROOT, GAME_DIR)

        for sheet in ("general", "castle"):
            runtime_layout = runtime_model["appendLayout"][sheet]
            legacy_layout = legacy_model["appendLayout"][sheet]
            for key in (
                "countOffset",
                "count",
                "insertOffset",
                "rowBytes",
                "titleBytes",
                "numericCount",
                "numericHeaders",
                "recordSuffixHeaders",
                "recordSuffixValues",
            ):
                self.assertEqual(runtime_layout[key], legacy_layout[key], f"{sheet}.{key}")
        self.assertEqual(
            runtime_model["fieldLocations"]["general"]["1"]["人物編號"],
            legacy_model["fieldLocations"]["general"]["1"]["人物編號"],
        )


if __name__ == "__main__":
    unittest.main()
