from __future__ import annotations

import struct
import unittest

from san_tools.map.editor_model import (
    EDITABLE_RECORD_FIELDS,
    FIELD_NAMES,
    KSY_SCHEMA_PATH,
    MapCell,
    MapEditChange,
    MapEditPatchModel,
    StageMapModel,
    canonical_field_name,
    field_meta,
)


class TestMapEditorModel(unittest.TestCase):
    """验证基于 `m.ksy` 的地图编辑数据模型。"""

    def make_stage_blob(self) -> bytes:
        """构造一个最小 `.m` 样本。"""

        records = [
            struct.pack("<hhhh8B", 1, 2, -1, 0, 3, 4, 5, 6, 0, 10, 0, 0),
            struct.pack("<hhhh8B", 7, 8, 9, 0, 11, 12, 13, 14, 0, 20, 0, 0),
        ]
        return struct.pack("<II8s", 2, 1, b"Hello1.0") + b"".join(records)

    def test_stage_model_reads_m_cells_and_exports_editor_records(self) -> None:
        model = StageMapModel.from_m_bytes(self.make_stage_blob(), stage="stage_test", source="memory")

        self.assertEqual(model.width, 2)
        self.assertEqual(model.height, 1)
        self.assertEqual(model.cell_at(0, 0).acwx, 1)
        self.assertEqual(model.cell_at(0, 0).acwz, -1)
        self.assertEqual(model.editor_records()[1], [7, 8, 9, 0, 11, 12, 13, 14, 0, 20, 0, 0])
        self.assertEqual(model.minimap_color_bytes(), bytes([10, 20]))

    def test_editor_stage_dict_contains_ksy_field_metadata(self) -> None:
        model = StageMapModel.from_m_bytes(self.make_stage_blob(), stage="stage_test")
        payload = model.to_editor_stage_dict({"layout": "stagger"})
        meta_by_name = {row["name"]: row for row in payload["fieldMeta"]}

        self.assertEqual(payload["format"], "san-editor-stage-v1")
        self.assertEqual(payload["fields"], list(FIELD_NAMES))
        self.assertEqual(payload["ksy"], str(KSY_SCHEMA_PATH))
        self.assertEqual(payload["layout"], "stagger")
        self.assertEqual(meta_by_name["byte13"]["ksyId"], "minimap_color")
        self.assertTrue(meta_by_name["byte13"]["sidecarSource"])
        self.assertIn("byte13", EDITABLE_RECORD_FIELDS)

    def test_field_aliases_are_canonicalized(self) -> None:
        self.assertEqual(canonical_field_name("flags"), "word06")
        self.assertEqual(canonical_field_name("final_palette"), "byte13")

        change = MapEditChange(x=1, y=0, field="final_palette", before=20, after=21)
        self.assertEqual(change.field, "byte13")
        self.assertEqual(change.as_json_dict()["field"], "byte13")

    def test_cell_from_editor_record_validates_shape_and_range(self) -> None:
        cell = MapCell.from_editor_record([1, 2, -1, 0, 3, 4, 5, 6, 0, 10, 0, 0])
        self.assertEqual(cell.value_of("final_palette"), 10)

        with self.assertRaises(ValueError):
            MapCell.from_editor_record([1, 2])
        with self.assertRaises(ValueError):
            MapCell.from_editor_record([1, 2, -1, 0, 3, 4, 5, 6, 0, 300, 0, 0])

    def test_patch_model_exports_json_payload(self) -> None:
        patch = MapEditPatchModel(
            stage="stage_test",
            changes=[MapEditChange(0, 0, "byte09", 4, 5)],
            minimap_dirty_cells=[(0, 0)],
        )

        payload = patch.to_patch_dict()

        self.assertEqual(payload["format"], "san-editor-patch-v1")
        self.assertEqual(payload["changes"][0], {"x": 0, "y": 0, "field": "byte09", "before": 4, "after": 5})
        self.assertEqual(payload["minimap"]["dirtyCells"], [[0, 0]])


class TestFieldMetaFunction(unittest.TestCase):
    """验证字段元数据可独立生成。"""

    def test_field_meta_contains_every_field_once(self) -> None:
        rows = field_meta()
        self.assertEqual([row["name"] for row in rows], list(FIELD_NAMES))
        self.assertEqual(len({row["name"] for row in rows}), len(FIELD_NAMES))


if __name__ == "__main__":
    unittest.main()
