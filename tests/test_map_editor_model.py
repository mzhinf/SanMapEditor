from __future__ import annotations

import struct
import unittest

from san_tools.map.editor_model import MFile, MMapCell


class TestMModel(unittest.TestCase):
    """验证 m.ksy 对应的字段级模型。"""

    def test_map_cell_reads_every_field(self) -> None:
        cell = MMapCell.from_bytes(struct.pack("<hhh2sBBBB1sB2s", 1, 2, -3, b"\x00\x00", 4, 5, 6, 7, b"\x00", 8, b"\x00\x00"))

        self.assertEqual(cell.acwx, 1)
        self.assertEqual(cell.acwy, 2)
        self.assertEqual(cell.acwz, -3)
        self.assertEqual(cell.reserved0, b"\x00\x00")
        self.assertEqual(cell.terrain_tag, 4)
        self.assertEqual(cell.blocked, 5)
        self.assertEqual(cell.site_trigger, 6)
        self.assertEqual(cell.site_area, 7)
        self.assertEqual(cell.reserved1, b"\x00")
        self.assertEqual(cell.minimap_color, 8)
        self.assertEqual(cell.reserved2, b"\x00\x00")

    def test_m_file_reads_header_and_cells(self) -> None:
        cell0 = struct.pack("<hhh2sBBBB1sB2s", 1, 2, -1, b"\x00\x00", 3, 4, 5, 6, b"\x00", 7, b"\x00\x00")
        cell1 = struct.pack("<hhh2sBBBB1sB2s", 8, 9, 10, b"\x00\x00", 11, 12, 13, 14, b"\x00", 15, b"\x00\x00")
        blob = struct.pack("<II8s", 2, 1, b"Hello1.0") + cell0 + cell1

        model = MFile.from_bytes(blob)

        self.assertEqual(model.width, 2)
        self.assertEqual(model.height, 1)
        self.assertEqual(model.magic_bytes, b"Hello1.0")
        self.assertEqual(model.cell_size, 2)
        self.assertEqual(model.cells[0].site_area, 6)
        self.assertEqual(model.cells[1].minimap_color, 15)

    def test_m_file_rejects_invalid_magic(self) -> None:
        blob = struct.pack("<II8s", 1, 1, b"BadMagic") + struct.pack("<hhh2sBBBB1sB2s", 0, 0, 0, b"\x00\x00", 0, 0, 0, 0, b"\x00", 0, b"\x00\x00")

        with self.assertRaises(ValueError):
            MFile.from_bytes(blob)


if __name__ == "__main__":
    unittest.main()
