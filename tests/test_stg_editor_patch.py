from __future__ import annotations

import unittest
from pathlib import Path

from san_tools.map.editor_model import StgFile
from tests.sample_support import require_game_data
from san_tools.map.stg_editor_patch import apply_stg_scenario_changes, build_stg_layout_index, build_stg_patch_index, encode_big5_fixed


ROOT = Path(__file__).resolve().parents[1]


class TestStgEditorPatch(unittest.TestCase):
    """验证编辑器 .stg 字段级回写工具。"""

    def test_big5_fixed_encoding(self) -> None:
        encoded = encode_big5_fixed('ABC', 6)
        self.assertEqual(encoded, b'ABC\x00\x00\x00')

    def test_stage01_patch_index_contains_ksy_fields(self) -> None:
        game_dir = require_game_data(ROOT)
        path = game_dir / 'stage01.stg'
        if not path.exists():
            self.skipTest('缺少 stage01.stg 样本')

        index = build_stg_patch_index(path.read_bytes())

        self.assertIn('force_name', index['force:0'])
        self.assertIn('site_name', index['force:0/site:0'])
        self.assertIn('entity_name', index['force:0/site:0/entity:0'])
        self.assertIn('person_id', index['force:0/site:0/entity:0'])

    def test_stage01_layout_index_contains_object_stream_offsets(self) -> None:
        game_dir = require_game_data(ROOT)
        path = game_dir / 'stage01.stg'
        if not path.exists():
            self.skipTest('缺少 stage01.stg 样本')

        layout = build_stg_layout_index(path.read_bytes())

        self.assertIn('forceCountOffset', layout['layout'])
        self.assertIn('root2ForceCountOffset', layout['layout'])
        self.assertIn('force:0', layout['forces'])
        self.assertIn('force:0/site:0', layout['sites'])
        self.assertIn('force:0/site:0/entity:0', layout['entities'])
        self.assertIn('siteCountOffset', layout['forces']['force:0'])
        self.assertIn('primaryEntityCountOffset', layout['sites']['force:0/site:0'])
        self.assertIn('sitePart2PayloadOffset', layout['sites']['force:0/site:0'])
        self.assertIn('entityPart1PayloadOffset', layout['entities']['force:0/site:0/entity:0'])
        self.assertGreaterEqual(layout['entities']['force:0/site:0/entity:0']['entityPart1PayloadSize'], 0x30)
        self.assertEqual(
            sorted(layout['sites']['force:0/site:0']['optionalEntityFlagOffsets']),
            ['optional_entity_27c', 'optional_entity_280', 'optional_entity_284', 'optional_entity_288', 'optional_entity_28c'],
        )
    def test_stage01_updates_existing_force_site_and_entity_fields(self) -> None:
        game_dir = require_game_data(ROOT)
        path = game_dir / 'stage01.stg'
        if not path.exists():
            self.skipTest('缺少 stage01.stg 样本')

        original = path.read_bytes()
        patched = apply_stg_scenario_changes(original, [
            {'kind': 'force', 'key': 'force:0', 'op': 'update', 'field': 'force_lord_person_id', 'after': 99},
            {'kind': 'site', 'key': 'force:0/site:0', 'op': 'update', 'field': 'coord_x', 'after': 123},
            {'kind': 'entity', 'key': 'force:0/site:0/entity:0', 'op': 'update', 'field': 'entity_name', 'after': '劉備'},
            {'kind': 'entity', 'key': 'force:0/site:0/entity:0', 'op': 'update', 'field': 'troop_count', 'after': 4567},
        ])
        model = StgFile.from_bytes(patched)

        self.assertEqual(model.forces[0].part1.body.force_lord_person_id, 99)
        self.assertEqual(model.forces[0].sites[0].part1.body.coord_x, 123)
        self.assertEqual(model.forces[0].sites[0].entities[0].part2.body.entity_name, '劉備')
        self.assertEqual(model.forces[0].sites[0].entities[0].part2.body.troop_count, 4567)


if __name__ == '__main__':
    unittest.main()