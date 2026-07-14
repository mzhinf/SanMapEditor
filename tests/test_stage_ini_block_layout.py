from __future__ import annotations

import unittest
from pathlib import Path

from san_tools.codecs.stage_ini_codec import parse_stage_ini_block_layout
from san_tools.map.export_editor_bundle import STAGE_INI_FIELD_MAP, build_stage_ini_patch_model


ROOT = Path(__file__).resolve().parents[1]


def size_block(payload: bytes) -> bytes:
    """构造与 stage.ini 一致的 `u32 size + payload` 测试块。"""

    return len(payload).to_bytes(4, "little") + payload


class TestStageIniBlockLayout(unittest.TestCase):
    """验证 stage.ini 真实块流边界及编辑器追加布局。"""

    def test_general_field_map_contains_new_general_maximum_fields(self) -> None:
        """三项最大值必须进入通用字段映射，供新 Entity 继承。"""

        fields = STAGE_INI_FIELD_MAP["entity"]["fields"]
        self.assertEqual(fields["max_troop_count"], "最大帶兵數")
        self.assertEqual(fields["max_martial_force"], "最大武力")
        self.assertEqual(fields["max_intellect"], "最大智力")

    def test_synthetic_block_stream_boundaries(self) -> None:
        """验证主表单块和城池双块均按 size 字段推进。"""

        blob = (
            (2).to_bytes(4, "little")
            + size_block(bytes(8))
            + size_block(bytes(4))
            + (2).to_bytes(4, "little")
            + size_block(bytes(12))
            + size_block(b"")
            + size_block(bytes(12))
            + size_block(b"")
            + b"\xaa\xbb"
        )
        layout = parse_stage_ini_block_layout(blob)

        self.assertEqual(layout["main_count"], 2)
        self.assertEqual(layout["main_blocks_end"], 24)
        self.assertEqual(layout["city_count_offset"], 24)
        self.assertEqual(layout["city_count"], 2)
        self.assertEqual(layout["city_records_end"], 68)
        self.assertEqual(layout["remaining_offset"], 68)
        self.assertEqual(layout["main_blocks"][1]["size_offset"], 16)
        self.assertEqual(layout["city_records"][1]["secondary"]["size"], 0)

    def test_game_stage_ini_confirmed_boundaries(self) -> None:
        """使用游戏有效母表锁定已确认的武将和城池边界。"""

        source = ROOT / "data" / "game" / "stage.ini"
        if not source.exists():
            self.skipTest("缺少 data/game/stage.ini")
        layout = parse_stage_ini_block_layout(source.read_bytes())

        self.assertEqual(layout["main_count"], 277)
        self.assertEqual(layout["main_blocks_end"], 63160)
        self.assertTrue(all(block["size"] == 224 for block in layout["main_blocks"]))
        self.assertEqual(layout["city_count_offset"], 63160)
        self.assertEqual(layout["city_count"], 42)
        self.assertEqual(layout["city_records_end"], 67364)
        self.assertTrue(
            all(
                record["primary"]["size"] == 92 and record["secondary"]["size"] == 0
                for record in layout["city_records"]
            )
        )

    def test_editor_append_layout_matches_game_blocks(self) -> None:
        """验证 bundle 不再用 224/76 伪步长补齐新增逻辑行。"""

        source = ROOT / "data" / "game" / "stage.ini"
        if not source.exists():
            self.skipTest("缺少 data/game/stage.ini")
        model = build_stage_ini_patch_model(ROOT, source.parent)
        self.assertTrue(model["available"], model.get("reason"))
        append = model["appendLayout"]

        self.assertEqual(append["format"], "stage-ini-block-stream-v1")
        self.assertEqual(append["general"]["insertOffset"], 63160)
        self.assertEqual(append["general"]["rowBytes"], 228)
        self.assertEqual(append["general"]["titleBytes"], 20)
        self.assertEqual(append["general"]["recordSuffixHeaders"], ["最大武力", "最大智力"])
        self.assertEqual(append["general"]["insertOffset"], append["castle"]["countOffset"])
        self.assertEqual(append["castle"]["countOffset"], 63160)
        self.assertEqual(append["castle"]["insertOffset"], 67364)
        self.assertEqual(append["castle"]["rowBytes"], 100)
        self.assertEqual(append["castle"]["recordPrefixValues"], [92, 0])
        self.assertEqual(append["castle"]["recordSuffixValues"], [0])


if __name__ == "__main__":
    unittest.main()
