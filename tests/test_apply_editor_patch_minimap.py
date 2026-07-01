from __future__ import annotations

import json
import shutil
import struct
import unittest
from pathlib import Path

from san_tools.map.apply_editor_patch import apply_patch_file
from san_tools.map.minimap_sidecar import ACTIVE_ROWS, GRID_SIZE, build_active_minimap_bytes, parse_stage_final_palette


class TestApplyEditorPatchMinimap(unittest.TestCase):
    """验证编辑器 patch 写回时能同步生成 `.s/.x`。"""

    def make_stage_blob(self) -> bytes:
        records = [
            struct.pack('<hhhh8B', 1, 0, -1, 0, 0, 0, 0, 0, 0, 10, 0, 0),
            struct.pack('<hhhh8B', 2, 0, -1, 0, 0, 0, 0, 0, 0, 20, 0, 0),
            struct.pack('<hhhh8B', 3, 0, -1, 0, 0, 0, 0, 0, 0, 30, 0, 0),
            struct.pack('<hhhh8B', 4, 0, -1, 0, 0, 0, 0, 0, 0, 40, 0, 0),
        ]
        return struct.pack('<II8s', 2, 2, b'Hello1.0') + b''.join(records)

    def make_patch_payload(self) -> dict[str, object]:
        return {
            'format': 'san-editor-patch-v1',
            'stage': 'stage99',
            'fields': ['acwx', 'byte13'],
            'minimap': {'dirtyCells': [[0, 0], [1, 1]]},
            'changes': [
                {'x': 0, 'y': 0, 'field': 'byte13', 'before': 10, 'after': 200},
                {'x': 1, 'y': 1, 'field': 'acwx', 'before': 4, 'after': 8},
            ],
        }

    def make_case_dir(self, case_name: str) -> Path:
        base_dir = Path(__file__).resolve().parents[1] / 'derived' / 'test_tmp' / case_name
        shutil.rmtree(base_dir, ignore_errors=True)
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    def test_apply_patch_writes_output_m_and_sidecars(self) -> None:
        root = self.make_case_dir('apply_patch_writes_output_m_and_sidecars')
        try:
            game_dir = root / 'game'
            game_dir.mkdir(exist_ok=True)
            (game_dir / 'Emperor.exe').write_bytes(b'MZ')
            stage_path = game_dir / 'stage99.m'
            stage_path.write_bytes(self.make_stage_blob())

            reference_s = bytes(index % 251 for index in range(GRID_SIZE * GRID_SIZE))
            reference_x = bytes((index * 3) % 251 for index in range(GRID_SIZE * GRID_SIZE))
            (game_dir / 'stage99.s').write_bytes(reference_s)
            (game_dir / 'stage99.x').write_bytes(reference_x)

            patch_path = root / 'stage99_patch.json'
            patch_path.write_text(json.dumps(self.make_patch_payload(), ensure_ascii=False, indent=2), encoding='utf-8')
            output_path = root / 'derived' / 'edited' / 'custom_stage.m'

            result = apply_patch_file(
                root=root,
                patch_path=patch_path,
                out=output_path,
                source=stage_path,
                force=False,
                dry_run=False,
                write_minimap_sidecars=True,
                sidecar_preview=False,
                sidecar_palette='SAN_RGB_PALETTE',
                sidecar_grid_size=GRID_SIZE,
                sidecar_active_rows=ACTIVE_ROWS,
                sidecar_preview_scale=3,
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(result['minimap_dirty_cells'], 2)
            self.assertTrue(result['minimap_sidecars_written'])
            self.assertIsInstance(result['minimap_sidecars'], dict)

            output_s = output_path.with_suffix('.s')
            output_x = output_path.with_suffix('.x')
            self.assertTrue(output_s.exists())
            self.assertTrue(output_x.exists())
            self.assertTrue((output_path.parent / 'custom_stage_sidecar_build_report.json').exists())

            width, height, final_palette = parse_stage_final_palette(output_path)
            expected_active = build_active_minimap_bytes(width, height, final_palette)
            cut = GRID_SIZE * ACTIVE_ROWS
            self.assertEqual(output_s.read_bytes()[:cut], expected_active)
            self.assertEqual(output_x.read_bytes()[:cut], expected_active)
            self.assertEqual(output_s.read_bytes()[cut:], reference_s[cut:])
            self.assertEqual(output_x.read_bytes()[cut:], reference_x[cut:])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_apply_patch_accepts_legacy_and_new_field_names(self) -> None:
        root = self.make_case_dir('apply_patch_accepts_legacy_and_new_field_names')
        try:
            game_dir = root / 'game'
            game_dir.mkdir(exist_ok=True)
            (game_dir / 'Emperor.exe').write_bytes(b'MZ')
            stage_path = game_dir / 'stage99.m'
            stage_path.write_bytes(self.make_stage_blob())
            (game_dir / 'stage99.s').write_bytes(bytes(index % 251 for index in range(GRID_SIZE * GRID_SIZE)))
            (game_dir / 'stage99.x').write_bytes(bytes((index * 3) % 251 for index in range(GRID_SIZE * GRID_SIZE)))

            patch_path = root / 'stage99_patch_legacy.json'
            patch_payload = self.make_patch_payload()
            patch_payload['changes'].append({'x': 1, 'y': 0, 'field': 'final_palette', 'before': 20, 'after': 21})
            patch_path.write_text(json.dumps(patch_payload, ensure_ascii=False, indent=2), encoding='utf-8')
            output_path = root / 'derived' / 'edited' / 'custom_stage_legacy.m'

            result = apply_patch_file(
                root=root,
                patch_path=patch_path,
                out=output_path,
                source=stage_path,
                force=False,
                dry_run=False,
                write_minimap_sidecars=False,
                sidecar_preview=False,
                sidecar_palette='SAN_RGB_PALETTE',
                sidecar_grid_size=GRID_SIZE,
                sidecar_active_rows=ACTIVE_ROWS,
                sidecar_preview_scale=3,
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(result['changes'], 3)
            blob = output_path.read_bytes()
            self.assertEqual(blob[16 + 13], 200)
            self.assertEqual(blob[16 + 16 + 13], 21)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_apply_patch_can_skip_minimap_sidecars(self) -> None:
        root = self.make_case_dir('apply_patch_can_skip_minimap_sidecars')
        try:
            game_dir = root / 'game'
            game_dir.mkdir(exist_ok=True)
            (game_dir / 'Emperor.exe').write_bytes(b'MZ')
            stage_path = game_dir / 'stage99.m'
            stage_path.write_bytes(self.make_stage_blob())

            patch_path = root / 'stage99_patch.json'
            patch_path.write_text(json.dumps(self.make_patch_payload(), ensure_ascii=False, indent=2), encoding='utf-8')
            output_path = root / 'derived' / 'edited' / 'custom_stage_skip.m'

            result = apply_patch_file(
                root=root,
                patch_path=patch_path,
                out=output_path,
                source=stage_path,
                force=False,
                dry_run=False,
                write_minimap_sidecars=False,
                sidecar_preview=False,
                sidecar_palette='SAN_RGB_PALETTE',
                sidecar_grid_size=GRID_SIZE,
                sidecar_active_rows=ACTIVE_ROWS,
                sidecar_preview_scale=3,
            )

            self.assertTrue(output_path.exists())
            self.assertFalse(result['minimap_sidecars_written'])
            self.assertIsNone(result['minimap_sidecars'])
            self.assertFalse(output_path.with_suffix('.s').exists())
            self.assertFalse(output_path.with_suffix('.x').exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
