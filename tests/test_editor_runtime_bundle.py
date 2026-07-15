"""使用只读 stage01 样本验证真实运行时资源生成链路。"""

from __future__ import annotations

import json
import shutil
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from san_tools.map.editor_runtime_session import RuntimeSessionManager, runtime_input_specs


ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = ROOT / "data" / "game"
TEST_TMP = ROOT / "derived" / "test_tmp" / "editor_runtime_bundle"
REQUIRED_SAMPLE_FILES = tuple(
    spec.filename
    for spec in runtime_input_specs("stage01")
    if spec.required
)


@unittest.skipUnless(
    all((GAME_DIR / name).is_file() for name in REQUIRED_SAMPLE_FILES),
    "缺少完整 data/game/stage01 运行时样本",
)
class TestEditorRuntimeBundle(unittest.TestCase):
    """验证地图、图集、小地图、头像和原始参考文件均来自显式样本。"""

    def setUp(self) -> None:
        """为真实 Bundle 生成准备可清理的临时会话根。"""

        shutil.rmtree(TEST_TMP, ignore_errors=True)
        TEST_TMP.mkdir(parents=True)

    def test_default_exporter_builds_complete_temporary_bundle(self) -> None:
        """默认导出器应在临时会话中生成完整编辑页所需资源。"""

        manager = RuntimeSessionManager(session_base=TEST_TMP / "sessions")
        try:
            with warnings.catch_warnings(), patch(
                "san_tools.map.export_editor_bundle.find_text_data_dir",
                side_effect=AssertionError("运行时不得查找 data/text"),
            ), patch(
                "san_tools.map.export_editor_bundle.find_game_dir",
                side_effect=AssertionError("运行时不得查找仓库游戏目录"),
            ):
                warnings.simplefilter("ignore", Image.DecompressionBombWarning)
                session = manager.create_from_stage(
                    GAME_DIR / "stage01.m",
                    GAME_DIR,
                    {"app_title": "运行时集成测试"},
                )
            stage_dir = session.data_dir / "stage01"
            expected = (
                "editor.html",
                "stage.json",
                "resources.json",
                "map.png",
                "minimap.png",
                "heads.png",
                "stage01.dor",
                "stage01.stg",
                "stage.ini",
                "History.txt",
                "heads.dat",
                "stage_ini.xlsx",
            )
            missing = [name for name in expected if not (stage_dir / name).is_file()]
            self.assertEqual(missing, [])
            self.assertTrue((session.data_dir / "index.html").is_file())
            stage_payload = json.loads((stage_dir / "stage.json").read_text(encoding="utf-8"))
            self.assertEqual(stage_payload["stage"], "stage01")
            self.assertTrue(stage_payload["commonModel"]["heads"]["available"])
            self.assertTrue(stage_payload["commonModel"]["stageIniPatchModel"]["available"])
            self.assertGreater(len(stage_payload["commonModel"]["big5CharMap"]), 13000)
            self.assertTrue(stage_payload["sidecars"]["available"])
            metadata = json.loads((session.root / "session-info.json").read_text(encoding="utf-8"))
            self.assertTrue(metadata["export"]["runtime"])
            self.assertEqual(Path(metadata["export"]["source_dir"]), GAME_DIR.resolve())
            self.assertTrue(
                all(Path(item["path"]).parent == GAME_DIR.resolve() for item in metadata["inputs"]["files"])
            )
        finally:
            manager.close()
        self.assertEqual(list((TEST_TMP / "sessions").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
