from __future__ import annotations

import unittest
from pathlib import Path

from tools.analyze_stage_sidecars import find_game_dir
from tools.export_stg_city_troop_analysis import build_troop_rows, choose_troop_rotation
from tools.export_stg_hierarchy import build_hierarchy
from tools.export_stg_raw_chain import build_rows as build_raw_chain


class StgTroopAnalysisTest(unittest.TestCase):
    """验证 `.stg` 士兵候选字段导出的当前稳定结论。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        try:
            cls.game_dir = find_game_dir(cls.root)
        except FileNotFoundError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        if not (cls.game_dir / 'stage01.stg').exists():
            raise unittest.SkipTest('缺少 stage01.stg，跳过士兵候选分析测试。')

    def test_choose_troop_rotation_prefers_layout_matching_soldier_codes(self) -> None:
        words = [0] * 38
        words[0] = 224
        words[12] = 224
        words[14] = 121
        words[22] = 24
        words[24] = 1
        words[26] = 50
        words[32] = 50

        soldier_by_name = {'小投石車': {'soldier_id': 24}}
        rotated, anchor, method, score = choose_troop_rotation(words, '投石車', soldier_by_name)

        self.assertEqual(0, anchor)
        self.assertEqual('best_224_match', method)
        self.assertGreaterEqual(score, 20)
        self.assertEqual(224, rotated[0])
        self.assertEqual(224, rotated[12])
        self.assertEqual(121, rotated[14])
        self.assertEqual(24, rotated[22])

    def test_stage01_troop_rows_export_named_soldier_id_cluster(self) -> None:
        raw_payload = build_raw_chain(self.root, 'stage01')
        hierarchy = build_hierarchy(self.root, 'stage01')
        rows = build_troop_rows(self.root, list(raw_payload['records']), hierarchy)

        self.assertEqual(42, len(rows))
        self.assertEqual(42, sum(1 for row in rows if row.get('expected_soldier_id_from_text') is not None))
        self.assertGreaterEqual(sum(1 for row in rows if row.get('candidate_soldier_id_matches_text')), 17)
        self.assertGreaterEqual(sum(1 for row in rows if row.get('candidate_soldier_code_cluster_consistent')), 25)

        matched_rows = [row for row in rows if row.get('candidate_soldier_id_matches_text')]
        self.assertTrue(matched_rows)
        for row in matched_rows:
            soldier_id = int(row['candidate_soldier_id_t22'])
            self.assertEqual(soldier_id + 200, int(row['candidate_soldier_code_plus200_t12']))


if __name__ == '__main__':
    unittest.main()
