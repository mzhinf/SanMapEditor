from __future__ import annotations

import unittest
from pathlib import Path

from san_tools.analysis.analyze_stg_field_values import collect_field_rows, filter_uncertain_rows, summarize_rows
from san_tools.codecs.stg_stream_codec_refactored import load_txt_tables, parse_stage_file
from tests.sample_support import require_game_data


class TestStgFieldValues(unittest.TestCase):
    """验证 `.stg` 字段统计脚本的基础展开逻辑。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.game_dir = require_game_data(Path(__file__).resolve().parents[1])
        cls.stage_path = cls.game_dir / "stage01.stg"
        if not cls.stage_path.exists():
            raise unittest.SkipTest("缺少 stage01.stg，跳过字段统计测试。")
        cls.tables = load_txt_tables(cls.game_dir)
        cls.doc = parse_stage_file(cls.stage_path, tables=cls.tables, strict=True, detect_tail_entities=True)

    def test_collect_field_rows_contains_core_context(self) -> None:
        rows = collect_field_rows(self.doc, self.stage_path, self.game_dir)
        self.assertTrue(rows)
        root_title_rows = [row for row in rows if row["field_name"] == "scenario_title"]
        self.assertTrue(root_title_rows)
        self.assertEqual(root_title_rows[0]["stage_file"], "stage01.stg")
        force_rows = [row for row in rows if row["force_name"]]
        self.assertTrue(force_rows)

    def test_uncertain_rows_and_summary(self) -> None:
        rows = collect_field_rows(self.doc, self.stage_path, self.game_dir)
        uncertain_rows = filter_uncertain_rows(rows, {"candidate", "unknown"})
        self.assertTrue(uncertain_rows)
        summary_rows = summarize_rows(uncertain_rows)
        self.assertTrue(summary_rows)
        self.assertIn("occurrence_count", summary_rows[0])
