from __future__ import annotations

import struct
import unittest

from san_tools.map.editor_model import DorFile, StgFile


def fixed_big5(text: str, size: int) -> bytes:
    """生成 Big5 定长字符串。"""

    raw = text.encode("big5")
    if len(raw) > size:
        raise ValueError(text)
    return raw + b"\x00" * (size - len(raw))


def block(payload: bytes) -> bytes:
    """生成 stg 的 size 加 payload 块。"""

    return struct.pack("<I", len(payload)) + payload


def make_dor_blob() -> bytes:
    """构造一个严格符合 dor.ksy 的最小样本。"""

    record_words = (12, 34, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 90, 91, 0)
    return b"Door    Data" + struct.pack("<I", 15) + struct.pack("<I", 1) + struct.pack("<15I", *record_words) + struct.pack("<I", 0)


def make_stg_blob() -> bytes:
    """构造一个严格符合 stg.ksy 的最小样本。"""

    root1 = bytearray(0x4C)
    root1[0x00:0x10] = fixed_big5("TEST", 16)
    struct.pack_into("<I", root1, 0x1C, 190)
    struct.pack_into("<I", root1, 0x20, 500)
    struct.pack_into("<I", root1, 0x30, 1)
    struct.pack_into("<I", root1, 0x34, 1)

    root2 = bytearray(0x34)
    struct.pack_into("<I", root2, 0x14, 1)

    force1 = bytearray(0x60)
    force1[0x00:0x14] = fixed_big5("FORCE_A", 20)
    force2 = bytearray(0x7C)
    struct.pack_into("<I", force2, 0x00, 1)
    struct.pack_into("<I", force2, 0x04, 1)

    site1 = bytearray(0x58)
    site1[0x00:0x14] = fixed_big5("SITE_A", 20)
    struct.pack_into("<i", site1, 0x14, 7)
    struct.pack_into("<i", site1, 0x48, 90)
    struct.pack_into("<i", site1, 0x4C, 91)

    site2 = bytearray(0x2B0)
    struct.pack_into("<I", site2, 0x27C, 1)

    entity1_part1 = bytearray(0x30)
    entity1_part2 = bytearray(0xE0)
    entity1_part2[0x00:0x14] = fixed_big5("LEADER_A", 20)
    struct.pack_into("<i", entity1_part2, 0x14, 101)
    struct.pack_into("<i", entity1_part2, 0x30, 500)

    entity2_part1 = bytearray(0x30)
    entity2_part2 = bytearray(0xE0)
    entity2_part2[0x00:0x14] = fixed_big5("UNIT_B", 20)
    struct.pack_into("<i", entity2_part2, 0x14, 102)
    struct.pack_into("<i", entity2_part2, 0x30, 300)

    return (
        struct.pack("<I", 1)
        + block(bytes(root1))
        + block(bytes(root2))
        + struct.pack("<I", 1)
        + block(bytes(force1))
        + block(bytes(force2))
        + struct.pack("<I", 1)
        + block(bytes(site1))
        + block(bytes(site2))
        + struct.pack("<I", 1)
        + block(bytes(entity1_part1))
        + block(bytes(entity1_part2))
        + block(bytes(entity2_part1))
        + block(bytes(entity2_part2))
        + b"TAIL"
    )


class TestDorAndStgModels(unittest.TestCase):
    """验证 dor.ksy 与 stg.ksy 对应的字段级模型。"""

    def test_dor_file_reads_groups_by_ksy_shape(self) -> None:
        model = DorFile.from_bytes(make_dor_blob())

        self.assertEqual(model.magic_bytes, b"Door    Data")
        self.assertEqual(model.record_size, 15)
        self.assertEqual(model.record_size_bytes, 60)
        self.assertEqual(len(model.dor_groups), 2)
        self.assertEqual(model.dor_groups[0].record_count, 1)
        self.assertEqual(model.dor_groups[0].records[0].site_x, 90)
        self.assertEqual(model.dor_groups[0].records[0].site_y, 91)
        self.assertEqual(model.dor_groups[1].record_count, 0)

    def test_stg_file_reads_nested_objects_by_ksy_shape(self) -> None:
        model = StgFile.from_bytes(make_stg_blob())

        self.assertEqual(model.present_or_version, 1)
        self.assertEqual(model.root_part1.body.scenario_title, "TEST")
        self.assertEqual(model.root_part1.body.scenario_year_start, 190)
        self.assertEqual(model.root_part1.body.scenario_year_end, 500)
        self.assertEqual(model.root_part1.body.scenario_id, 1)
        self.assertEqual(model.force_count, 1)
        self.assertEqual(model.forces[0].force_name, "FORCE_A")
        self.assertEqual(model.forces[0].site_count, 1)
        self.assertEqual(model.forces[0].site_list_pre_count_or_flag, 1)
        self.assertEqual(model.forces[0].sites[0].site_name, "SITE_A")
        self.assertEqual(model.forces[0].sites[0].city_index, 7)
        self.assertEqual(model.forces[0].sites[0].map_x, 90)
        self.assertEqual(model.forces[0].sites[0].map_y, 91)
        self.assertEqual(model.forces[0].sites[0].primary_entity_count, 1)
        self.assertEqual(model.forces[0].sites[0].entities[0].entity_name, "LEADER_A")
        self.assertEqual(model.forces[0].sites[0].entities[0].person_id, 101)
        self.assertEqual(model.forces[0].sites[0].entities[0].troop_count, 500)
        self.assertIsNotNone(model.forces[0].sites[0].optional_entity_27c)
        self.assertEqual(model.forces[0].sites[0].optional_entity_27c.entity_name, "UNIT_B")
        self.assertEqual(model.forces[0].sites[0].optional_entity_27c.troop_count, 300)
        self.assertEqual(model.after_forces_tail.middle_tail_size, 0)
        self.assertEqual(model.after_forces_tail.trailer_or_small_tail_size, 4)


if __name__ == "__main__":
    unittest.main()
