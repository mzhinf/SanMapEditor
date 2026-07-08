from __future__ import annotations

import copy
import unittest
from pathlib import Path

from san_tools.codecs.stg_stream_codec_refactored import build_stage_bytes, load_txt_tables, parse_stage_file
from san_tools.pipelines.roundtrip_stg_json import (
    compute_defined_byte_mask,
    strip_reserved_fields_inplace,
    zero_undefined_data_inplace,
)


class TestStgJsonRoundtrip(unittest.TestCase):
    """验证 `.stg -> json -> stg` 预处理逻辑。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.game_dir = Path("H:/Workstation/san/三国霸业")
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

    def test_zero_undefined_data_zeroes_uncovered_bytes(self) -> None:
        json_doc = copy.deepcopy(self.doc)
        zeroed = zero_undefined_data_inplace(json_doc)
        self.assertGreater(zeroed, 0)

        root_block = json_doc["root_part1"]
        payload = bytes.fromhex(root_block["raw_hex"])
        mask = compute_defined_byte_mask(str(root_block.get("kind", "")), len(payload))
        self.assertTrue(any(not covered for covered in mask))
        for index, covered in enumerate(mask):
            if not covered:
                self.assertEqual(payload[index], 0)

        tail_hex = json_doc.get("after_forces_tail", {}).get("raw_hex", "")
        self.assertTrue(tail_hex)
        self.assertEqual(set(bytes.fromhex(tail_hex)), {0})

        rebuilt = build_stage_bytes(json_doc, recompute_counts=True, patch_fields=True)
        self.assertEqual(len(rebuilt), len(self.original_bytes))
