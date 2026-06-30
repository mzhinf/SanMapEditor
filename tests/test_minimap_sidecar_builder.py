from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from san_tools.map.minimap_sidecar import (
    ACTIVE_ROWS,
    GRID_SIZE,
    build_active_minimap_bytes,
    build_sidecar_from_stage,
    merge_active_with_reference_tail,
    parse_stage_final_palette,
)


class TestMinimapSidecarBuilder(unittest.TestCase):
    """验证 `.m -> .s/.x` 保守转换规则。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.game_dir = cls.root / '三国霸业'
        cls.stage_path = cls.game_dir / 'stage11.m'
        cls.s_path = cls.game_dir / 'stage11.s'
        cls.x_path = cls.game_dir / 'stage11.x'
        if not (cls.stage_path.exists() and cls.s_path.exists() and cls.x_path.exists()):
            raise unittest.SkipTest('缺少 stage11 的 .m/.s/.x 样本，跳过小地图 sidecar 测试。')

    def test_active_minimap_length(self) -> None:
        width, height, final_palette = parse_stage_final_palette(self.stage_path)
        active = build_active_minimap_bytes(width, height, final_palette)
        self.assertEqual(len(active), GRID_SIZE * ACTIVE_ROWS)

    def test_merge_preserves_reference_tail(self) -> None:
        width, height, final_palette = parse_stage_final_palette(self.stage_path)
        active = build_active_minimap_bytes(width, height, final_palette)
        reference = self.x_path.read_bytes()
        merged = merge_active_with_reference_tail(active, reference)
        cut = GRID_SIZE * ACTIVE_ROWS
        self.assertEqual(merged[cut:], reference[cut:])
        self.assertEqual(merged[:cut], active)

    def test_build_sidecar_from_stage_keeps_shape(self) -> None:
        generated_s = build_sidecar_from_stage(self.stage_path, self.s_path)
        generated_x = build_sidecar_from_stage(self.stage_path, self.x_path)
        self.assertEqual(len(generated_s), GRID_SIZE * GRID_SIZE)
        self.assertEqual(len(generated_x), GRID_SIZE * GRID_SIZE)
        self.assertEqual(generated_s[GRID_SIZE * ACTIVE_ROWS :], self.s_path.read_bytes()[GRID_SIZE * ACTIVE_ROWS :])
        self.assertEqual(generated_x[GRID_SIZE * ACTIVE_ROWS :], self.x_path.read_bytes()[GRID_SIZE * ACTIVE_ROWS :])
