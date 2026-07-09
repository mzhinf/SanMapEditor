from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from san_tools.map.export_editor_bundle import copy_scenario_reference_files, write_stage_json


ROOT = Path(__file__).resolve().parents[1]


class TestEditorAppV2Template(unittest.TestCase):
    """验证地图编辑器 2.0 模板的关键入口和脚本语法。"""

    def test_editor_app_contains_v2_workspaces(self) -> None:
        html = (ROOT / 'src' / 'san_tools' / 'map' / 'editor_app.html').read_text(encoding='utf-8')
        for marker in (
            '地图编辑器 2.0',
            '合成物件 / 区域复制',
            '势力管理',
            '据点 / 城门',
            '武将管理',
            '导出校验',
            'data-tab="raw"',
            'id="resourceList"',
            'id="canvas"',
        ):
            self.assertIn(marker, html)

    def test_editor_app_script_passes_node_syntax_check(self) -> None:
        html = (ROOT / 'src' / 'san_tools' / 'map' / 'editor_app.html').read_text(encoding='utf-8')
        script_match = re.search(r'<script>([\s\S]*)</script>', html)
        self.assertIsNotNone(script_match)
        tmp_dir = ROOT / 'derived' / 'test_tmp' / 'editor_app_v2'
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        script_path = tmp_dir / 'editor_app.js'
        script_path.write_text(script_match.group(1), encoding='utf-8')
        try:
            subprocess.run(['node', '--check', str(script_path)], cwd=ROOT, check=True, text=True, capture_output=True)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_editor_app_contains_large_stage_viewport_rendering_path(self) -> None:
        """验证超大地图可以跳过整图缓存，改用视口级资源绘制。"""
        html = (ROOT / 'src' / 'san_tools' / 'map' / 'editor_app.html').read_text(encoding='utf-8')
        for marker in (
            'renderCanvasSizeWithinLimit',
            'drawVisibleMapResources',
            'virtualImageSize',
            '底图 ${detail} 过大，已改用资源重建',
        ):
            self.assertIn(marker, html)

    def test_editor_app_els_references_have_dom_ids(self) -> None:
        """验证脚本中的 els 引用都能对应到实际 DOM 节点。"""
        html = (ROOT / 'src' / 'san_tools' / 'map' / 'editor_app.html').read_text(encoding='utf-8')
        script_match = re.search(r'<script>([\s\S]*)</script>', html)
        self.assertIsNotNone(script_match)
        script = script_match.group(1)
        els_match = re.search(r'const els = \{([\s\S]*?)\n\};', script)
        self.assertIsNotNone(els_match)

        registered = set(re.findall(r'\b([A-Za-z][A-Za-z0-9_]*)\s*:\s*document\.getElementById\(\'([^\']+)\'\)', els_match.group(1)))
        registered_names = {name for name, _ in registered}
        registered_ids = {element_id for _, element_id in registered}
        referenced_names = set(re.findall(r'\bels\.([A-Za-z][A-Za-z0-9_]*)\b', script))
        html_ids = set(re.findall(r'\bid="([^"]+)"', html))

        self.assertFalse(referenced_names - registered_names)
        self.assertFalse(registered_ids - html_ids)

class TestEditorBundleScenarioFiles(unittest.TestCase):
    """验证编辑器 bundle 会携带剧本侧参考文件信息。"""

    def test_copy_scenario_references_and_write_stage_json(self) -> None:
        tmp_dir = ROOT / 'derived' / 'test_tmp' / 'editor_bundle_scenario_files'
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            game_dir = tmp_dir / 'game'
            stage_dir = tmp_dir / 'stage99'
            game_dir.mkdir(parents=True, exist_ok=True)
            stage_dir.mkdir(parents=True, exist_ok=True)
            (game_dir / 'stage99.dor').write_bytes(b'dor-data')
            (game_dir / 'stage99.stg').write_bytes(b'stg-data')
            (game_dir / 'heads.dat').write_bytes(b'heads-data')

            scenario_files = copy_scenario_reference_files(game_dir, stage_dir, 'stage99')
            self.assertEqual((stage_dir / 'stage99.dor').read_bytes(), b'dor-data')
            self.assertEqual((stage_dir / 'stage99.stg').read_bytes(), b'stg-data')
            self.assertTrue(scenario_files['dor']['available'])
            self.assertTrue(scenario_files['stg']['available'])
            self.assertTrue(scenario_files['heads']['available'])

            out_path = stage_dir / 'stage.json'
            write_stage_json(
                out_path,
                'stage99',
                1,
                1,
                [[1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0]],
                'stagger',
                (64, 64),
                'map.png',
                'minimap.png',
                {'source_output_size': [100, 100]},
                'palette.dat',
                {'available': False},
                ['#000000'],
                {'available': False},
                scenario_files,
            )
            payload = json.loads(out_path.read_text(encoding='utf-8'))
            self.assertEqual(payload['scenarioFiles']['dor']['path'], 'stage99.dor')
            self.assertEqual(payload['scenarioFiles']['stg']['path'], 'stage99.stg')
            self.assertEqual(payload['scenarioFiles']['heads']['path'], 'heads.dat')
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
