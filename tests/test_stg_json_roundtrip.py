from __future__ import annotations

import copy
import unittest
from pathlib import Path

from san_tools.codecs.stg_stream_codec_refactored import build_stage_bytes, load_txt_tables, parse_stage_file
from tests.sample_support import require_game_data
from san_tools.pipelines.roundtrip_stg_json import (
    reserved_zero_ranges,
    strip_reserved_fields_inplace,
    zero_reserved_zero_fields_inplace,
)


class TestStgJsonRoundtrip(unittest.TestCase):
    """验证 `.stg -> json -> stg` 预处理逻辑。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.game_dir = require_game_data(Path(__file__).resolve().parents[1])
        cls.stage_path = cls.game_dir / "stage01.stg"
        if not cls.stage_path.exists():
            raise unittest.SkipTest("缺少 stage01.stg，跳过 JSON roundtrip 测试。")
        cls.tables = load_txt_tables(cls.game_dir)
        cls.doc = parse_stage_file(cls.stage_path, tables=cls.tables, strict=True, detect_tail_entities=True)
        cls.original_bytes = cls.stage_path.read_bytes()

    def test_strip_reserved_fields_keeps_roundtrip_identical(self) -> None:
        json_doc = copy.deepcopy(self.doc)
        strip_reserved_fields_inplace(json_doc)
        rebuilt = build_stage_bytes(json_doc, recompute_counts=True, patch_fields=True)
        self.assertEqual(rebuilt, self.original_bytes)

    def test_strip_reserved_fields_removes_reserved_names(self) -> None:
        json_doc = copy.deepcopy(self.doc)
        strip_reserved_fields_inplace(json_doc)
        field_maps = json_doc.get("field_maps", {})
        for specs in field_maps.values():
            for spec in specs:
                self.assertNotIn("reserved", str(spec.get("name", "")).lower())
        for block in [json_doc.get("root_part1"), json_doc.get("root_part2")]:
            if isinstance(block, dict):
                for field_name in block.get("fields", {}).keys():
                    self.assertNotIn("reserved", field_name.lower())

    def test_zero_reserved_zero_fields_only_touches_reserved_ranges(self) -> None:
        json_doc = copy.deepcopy(self.doc)

        root_block = json_doc["root_part1"]
        root_payload = bytearray.fromhex(root_block["raw_hex"])
        root_payload[0x10:0x14] = bytes.fromhex("78563412")
        root_payload[0x14:0x18] = bytes.fromhex("21436587")
        root_block["raw_hex"] = root_payload.hex()

        tail = json_doc.get("after_forces_tail", {})
        original_tail_hex = str(tail.get("raw_hex", ""))

        zeroed = zero_reserved_zero_fields_inplace(json_doc)
        self.assertGreaterEqual(zeroed, 4)

        new_root_payload = bytes.fromhex(json_doc["root_part1"]["raw_hex"])
        self.assertEqual(new_root_payload[0x10:0x14], bytes.fromhex("78563412"))
        self.assertEqual(new_root_payload[0x14:0x18], b"\x00\x00\x00\x00")

        self.assertEqual(str(json_doc.get("after_forces_tail", {}).get("raw_hex", "")), original_tail_hex)
        self.assertIn((0x14, 0x1C), reserved_zero_ranges("root_part1", len(new_root_payload)))

        rebuilt = build_stage_bytes(json_doc, recompute_counts=True, patch_fields=True)
        self.assertEqual(len(rebuilt), len(self.original_bytes))
