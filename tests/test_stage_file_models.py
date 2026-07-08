from __future__ import annotations

import struct
import unittest

from san_tools.map.editor_model import StageMapModel
from san_tools.map.stage_file_models import DorModel, StageEditFilesModel, StgModel


def fixed_big5(text: str, size: int) -> bytes:
    """生成 Big5 定长文本字段。"""

    raw = text.encode("big5")
    if len(raw) > size:
        raise ValueError(f"文本过长：{text}")
    return raw + b"\x00" * (size - len(raw))


def block(payload: bytes) -> bytes:
    """生成 `.stg` 的 `u32 size + payload` 块。"""

    return struct.pack("<I", len(payload)) + payload


def make_m_blob() -> bytes:
    """构造一个最小 `.m` 样本。"""

    records = [
        struct.pack("<hhhh8B", 1, 0, -1, 0, 0, 0, 0, 0, 0, 10, 0, 0),
        struct.pack("<hhhh8B", 2, 0, -1, 0, 0, 0, 0, 0, 0, 20, 0, 0),
    ]
    return struct.pack("<II8s", 2, 1, b"Hello1.0") + b"".join(records)


def make_dor_blob() -> bytes:
    """构造一个带单城门记录的 `.dor` 样本。"""

    record_words = (12, 34, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 90, 91, 0)
    return b"Door    Data" + struct.pack("<I", 15) + struct.pack("<I", 1) + struct.pack("<15I", *record_words) + struct.pack("<I", 0)


def make_stg_blob() -> bytes:
    """构造一个最小 KSY 对象流形态的 `.stg` 样本。"""

    root1 = bytearray(0x4C)
    root1[0x00:0x10] = fixed_big5("測試", 16)
    struct.pack_into("<I", root1, 0x1C, 190)
    struct.pack_into("<I", root1, 0x20, 500)
    struct.pack_into("<I", root1, 0x34, 1)

    root2 = bytearray(0x34)
    struct.pack_into("<I", root2, 0x14, 1)

    force1 = bytearray(0x60)
    force1[0x00:0x14] = fixed_big5("勢力", 20)
    force2 = bytearray(0x7C)
    struct.pack_into("<I", force2, 0x00, 1)

    site1 = bytearray(0x58)
    site1[0x00:0x14] = fixed_big5("城池", 20)
    struct.pack_into("<i", site1, 0x14, 7)
    struct.pack_into("<i", site1, 0x48, 90)
    struct.pack_into("<i", site1, 0x4C, 91)
    site2 = bytearray(0x2B0)

    entity1 = bytearray(0x30)
    entity2 = bytearray(0xE0)
    entity2[0x00:0x14] = fixed_big5("武將", 20)
    struct.pack_into("<i", entity2, 0x14, 101)
    struct.pack_into("<i", entity2, 0x30, 500)

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
        + block(bytes(entity1))
        + block(bytes(entity2))
        + b"TAIL"
    )


class TestStageFileModels(unittest.TestCase):
    """验证 `.m/.dor/.stg` 多文件编辑数据模型。"""

    def test_dor_model_reads_groups_and_records(self) -> None:
        model = DorModel.from_dor_bytes(make_dor_blob(), stage="stage_test")

        self.assertEqual(model.record_size_words, 15)
        self.assertEqual(len(model.groups), 1)
        self.assertEqual(len(model.records), 1)
        self.assertEqual(model.records[0].site_key, "90,91")
        self.assertTrue(model.has_zero_count_terminator)

    def test_stg_model_reads_object_stream(self) -> None:
        model = StgModel.from_stg_bytes(make_stg_blob(), stage="stage_test")

        self.assertEqual(model.title, "測試")
        self.assertEqual(model.force_count, 1)
        self.assertEqual(model.forces[0].name, "勢力")
        self.assertEqual(model.sites[0].name, "城池")
        self.assertEqual(model.sites[0].site_key, "90,91")
        self.assertEqual(model.entities[0].name, "武將")
        self.assertEqual(model.entities[0].troop_count, 500)
        self.assertEqual(model.after_forces_tail, b"TAIL")

    def test_stage_edit_files_model_links_dor_and_stg(self) -> None:
        bundle = StageEditFilesModel(
            stage="stage_test",
            map_model=StageMapModel.from_m_bytes(make_m_blob(), stage="stage_test"),
            dor_model=DorModel.from_dor_bytes(make_dor_blob(), stage="stage_test"),
            stg_model=StgModel.from_stg_bytes(make_stg_blob(), stage="stage_test"),
        )

        context = bundle.to_editor_context_dict()
        self.assertEqual(context["format"], "san-editor-stage-files-v1")
        self.assertEqual(context["siteLinks"]["matchedGateCount"], 1)
        self.assertEqual(context["siteLinks"]["gates"][0]["siteName"], "城池")
        self.assertEqual(context["map"]["width"], 2)


if __name__ == "__main__":
    unittest.main()
