"""验证统一项目数据路径的优先级与标准目录规则。"""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from san_tools.project_paths import find_game_data_dir, find_text_data_dir


ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / "derived" / "test_tmp"
TEST_TMP.mkdir(parents=True, exist_ok=True)


class TestProjectPaths(unittest.TestCase):
    """确保代码不再依赖固定盘符或旧项目目录名。"""

    def setUp(self) -> None:
        """为每个测试准备固定、可写且可清理的目录。"""

        self.root = TEST_TMP / "project_paths"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_standard_data_directories_are_detected(self) -> None:
        game_dir = self.root / "data" / "game"
        text_dir = self.root / "data" / "text"
        game_dir.mkdir(parents=True)
        text_dir.mkdir(parents=True)
        (game_dir / "stage.ini").write_bytes(b"sample")
        (text_dir / "castle.txt").write_text("sample", encoding="utf-8")

        self.assertEqual(find_game_data_dir(self.root), game_dir.resolve())
        self.assertEqual(find_text_data_dir(self.root), text_dir.resolve())

    def test_environment_variables_take_priority(self) -> None:
        game_dir = self.root / "external-game"
        text_dir = self.root / "external-text"
        game_dir.mkdir()
        text_dir.mkdir()
        (game_dir / "heads.dat").write_bytes(b"sample")
        (text_dir / "History.txt").write_text("sample", encoding="utf-8")

        values = {"SAN_GAME_DATA_DIR": str(game_dir), "SAN_GAME_TEXT_DIR": str(text_dir)}
        with patch.dict(os.environ, values, clear=False):
            self.assertEqual(find_game_data_dir(self.root), game_dir.resolve())
            self.assertEqual(find_text_data_dir(self.root), text_dir.resolve())


if __name__ == "__main__":
    unittest.main()
