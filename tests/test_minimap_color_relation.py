"""验证 xyz 到 minimap_color 的统计分析与近似预测函数。"""

from __future__ import annotations

import unittest

from san_tools.analysis.analyze_minimap_color_relation import (
    MinimapColorPredictor,
    build_minimap_color_function,
    leave_one_stage_out,
    predictor_statistics,
)


class TestMinimapColorRelation(unittest.TestCase):
    """覆盖冲突、分级回退和跨关卡验证。"""

    def test_predictor_uses_majority_and_hierarchical_fallback(self) -> None:
        """相同 xyz 冲突时取众数，未知组合按 z、y、x 优先级回退。"""

        rows = [
            (1, 2, 3, 10),
            (1, 2, 3, 10),
            (1, 2, 3, 11),
            (1, 2, 4, 12),
            (1, 5, 8, 20),
            (9, 9, 7, 30),
            (8, 8, 7, 30),
        ]
        predictor = MinimapColorPredictor(rows)

        exact = predictor.predict_detail(1, 2, 3)
        self.assertEqual((exact.color, exact.level, exact.support), (10, "xyz", 3))
        self.assertAlmostEqual(exact.confidence, 2 / 3)
        self.assertEqual(predictor.predict_detail(1, 2, 99).level, "xy")
        self.assertEqual(predictor.predict_detail(1, 99, 8).level, "xz")
        z_priority = predictor.predict_detail(1, 2, 7)
        self.assertEqual((z_priority.level, z_priority.color), ("z", 30))
        self.assertEqual(predictor.predict_detail(1, 99, 99).level, "x")
        self.assertEqual(predictor.predict_detail(99, 99, 99).level, "global")

    def test_generated_function_accepts_xyz_and_returns_color(self) -> None:
        """生成函数的公开签名只需要 xyz，返回颜色索引。"""

        predict_color = build_minimap_color_function([(7, -1, -1, 197), (7, -1, -1, 197)])
        self.assertEqual(predict_color(7, -1, -1), 197)

    def test_statistics_expose_non_deterministic_xyz(self) -> None:
        """同一 xyz 对应不同颜色时必须计为歧义键。"""

        rows = [(1, 2, 3, 10), (1, 2, 3, 11), (4, 5, 6, 20)]
        stats = predictor_statistics(rows, (0, 1, 2))
        self.assertEqual(stats["keys"], 2)
        self.assertEqual(stats["ambiguous_keys"], 1)
        self.assertLess(stats["majority_fit_accuracy"], 1.0)

    def test_leave_one_stage_out_does_not_train_on_held_stage(self) -> None:
        """留一验证应使用其他关卡的映射预测当前关卡。"""

        stages = {
            "stage01": [(1, 2, 3, 10), (9, 9, 9, 30)],
            "stage02": [(1, 2, 3, 10), (9, 8, 7, 30)],
        }
        result = leave_one_stage_out(stages)
        self.assertEqual(result["records"], 4)
        self.assertGreaterEqual(result["accuracy"], 0.5)


if __name__ == "__main__":
    unittest.main()
