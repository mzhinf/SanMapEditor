from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from san_tools.map.export_editor_bundle import build_editor_common_model, build_editor_scenario_model, build_editor_site_links, build_stage_ini_patch_model, build_stage_ini_workbook_sheets, copy_scenario_reference_files, export_heads_atlas, write_stage_json
from san_tools.project_paths import find_text_data_dir
from tests.sample_support import require_game_data


ROOT = Path(__file__).resolve().parents[1]


class TestEditorAppV2Template(unittest.TestCase):
    """验证地图编辑器 2.0 模板的关键入口和脚本语法。"""

    def test_editor_app_contains_v2_workspaces(self) -> None:
        html = (ROOT / 'src' / 'san_tools' / 'map' / 'editor_app.html').read_text(encoding='utf-8')
        for marker in (
            '地图编辑器 2.0',
            '创建者：mzhinf',
            '__SAN_EDITOR_BUILD_DATE__',
            '合成对象 / 区域操作',
            '势力管理',
            '据点 / 城门',
            '武将管理',
            '导出校验',
            'data-tab="raw"',
            'id="resourceList"',
            'id="cutRegion"',
            'id="regionCopyMode"',
            'class="panel-collapse"',
            'id="canvas"',
            'terrain_tag',
            'minimap_color',
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

    def test_status_text_cannot_expand_editor_grid(self) -> None:
        """验证过长错误信息只能在状态栏内截断，不能挤压编辑器布局。"""
        html = (ROOT / 'src' / 'san_tools' / 'map' / 'editor_app.html').read_text(encoding='utf-8')
        self.assertRegex(html, r'\.status \{[^}]*flex: 1 1 0;[^}]*min-width: 0;[^}]*max-width: 620px;')
        self.assertIn('els.status.title = message', html)
        self.assertRegex(html, r'\.status\.error \{[^}]*position: fixed;[^}]*max-height: 160px;[^}]*overflow: auto;')
        self.assertIn("els.status.addEventListener('click'", html)
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

    def test_editor_app_uses_ksy_m_field_names(self) -> None:
        """验证 UI 字段口径使用 m.ksy 的变量名。"""
        html = (ROOT / 'src' / 'san_tools' / 'map' / 'editor_app.html').read_text(encoding='utf-8')
        self.assertIn('terrain_tag', html)
        self.assertIn('minimap_color', html)
        self.assertIn('scenarioModel', html)
        self.assertIn('stgLayout', html)
        self.assertIn('buildRewrittenStgBytes', html)
        self.assertIn('parentSiteKey', html)
        self.assertIn('selectedCells', html)
        self.assertIn('cutRegionSnapshot', html)
        self.assertIn('copySelectedRegion()', html)
        self.assertIn('cutSelectedRegion()', html)
        self.assertIn('pasteSelectedRegion()', html)
        self.assertIn("shortcutKey === 'c' || shortcutKey === 'x' || shortcutKey === 'v'", html)
        self.assertIn("regionCopyMode: 'full'", html)
        self.assertIn("mode === 'non-base'", html)
        self.assertNotIn('setRegionAnchor', html)
        self.assertIn("key: 'edited'", html)
        self.assertIn('drawEditedCellOverlay', html)
        self.assertIn("rgba(245,158,11,0.07)", html)
        self.assertIn("state.meta.stage + '-export.zip'", html)
        self.assertIn("'application/zip'", html)
        self.assertIn('entityPortraitStyle', html)
        self.assertIn('manager-detail', html)
        self.assertIn('scenarioCollectionName', html)
        self.assertIn("kind === 'entity' ? 'entities' : kind + 's'", html)
        self.assertIn('overlayList', html)
        self.assertIn('DATA_OVERLAY_OPTIONS', html)
        self.assertIn("name: 'terrain_tag'", html)
        self.assertIn("name: 'site_trigger'", html)
        self.assertIn("mode: 'midpoint-square'", html)
        self.assertIn("mode: 'center-ring'", html)
        self.assertIn("mode: 'large-outline'", html)
        self.assertIn('midpointSquarePath', html)
        self.assertIn('ctx.moveTo(p.x + 24, p.y + 6)', html)
        self.assertIn('drawCellDataOverlay', html)
        self.assertIn('shouldShowDataOverlays', html)
        self.assertIn('if (!state.meta || !shouldShowDataOverlays()) return;', html)
        self.assertIn('renderDataOverlayControls(); refreshSide(); refreshPatches(); scheduleDraw();', html)
        self.assertIn('input.disabled = !enabled', html)
        self.assertIn('text.textContent = option.derived ? option.label : layerOptionLabel(option.key)', html)
        self.assertIn('sourceTabState: new Map()', html)
        self.assertIn('sideRefreshQueued: false', html)
        self.assertIn('patchRefreshQueued: false', html)
        self.assertIn('recentMapPatchKeys: []', html)
        self.assertIn('function recentMapPatchPreview', html)
        self.assertIn('const totalChanges = state.patches.size + state.scenarioPatches.size', html)
        self.assertIn('scheduleSideRefresh();', html)
        self.assertIn('schedulePatchRefresh();', html)
        self.assertNotIn('const mapChanges = [...state.patches.values()]', html)
        self.assertIn('state.sourceTabState.set(stateKey, sectionKey)', html)
        self.assertIn('state.sourceTabState.clear()', html)
        self.assertIn('site:${site.siteKey}:source', html)
        self.assertIn('site:${site.siteKey}:stg', html)
        self.assertIn('entity:${entity.entityKey}:source', html)
        self.assertIn('history:${historyGeneralKey(historyGeneral)}:source', html)
        self.assertIn('applyPointResourceThumbStyle', html)
        self.assertNotIn('radial-gradient(circle at center', html)
        self.assertNotIn('polygon(50% 0,100% 50%,50% 100%,0 50%)', html)
        self.assertIn('historyGenerals', html)
        self.assertIn('inactiveHistoryGeneralRows', html)
        self.assertIn('generalCandidateByKey', html)
        self.assertIn('inactiveHistoryGeneralRows().find(row => historyGeneralKey(row) === key)', html)
        self.assertIn('const seenPersonIds = new Set(rows.map(row => Number(row.person_id || 0)).filter(Boolean));', html)
        self.assertIn("const sourceLabel = row.stageIniOnly ? 'stage.ini' : 'History.txt';", html)
        self.assertIn('stageIniGeneralRows', html)
        self.assertIn('stageIniPatchModel: model?.stageIniPatchModel', html)
        self.assertIn('stageIniGeneralSaveRows', html)
        self.assertIn('appendStageIniGeneralFields', html)
        self.assertIn('stageIniGeneralPatches', html)
        self.assertIn('addExistingGeneralToSite', html)
        self.assertIn('SITE_INI_FIELDS', html)
        self.assertIn('SITE_STG_FIELDS', html)
        self.assertIn('createSourceTabs', html)
        self.assertIn('historyGeneralForPerson', html)
        self.assertIn('historyTableModel', html)
        self.assertIn('appendHistoryFields', html)
        self.assertIn('updateHistoryField', html)
        self.assertIn('buildEditedHistoryBytes', html)
        self.assertIn('buildHistoryPatchArtifact', html)
        self.assertIn('encodeBig5Text', html)
        self.assertNotIn("addScenarioEntity('soldier')", html)
        self.assertNotIn('\u65b0\u589e\u58eb\u5175', html)
        self.assertIn("isGeneralEntity(entity)) {", html)
        self.assertIn('Number(entity?.command || 0) > 0', html)
        self.assertIn('normalizeGateRows', html)
        self.assertIn('originalDorKey', html)
        self.assertIn("String(gate.gateKey || '').startsWith('gate:new:')", html)
        self.assertIn("gateKey: `gate:new:${Date.now()}:${state.gates.length}`", html)
        self.assertIn('const original = gate.originalDorKey ? originalByKey.get(gate.originalDorKey) : null;', html)
        self.assertNotIn('originalByKey.get(dorRecordKey(groupNumber, gate.doorIndex)) || originalByKey.get(dorRecordKey(groupNumber, gate.gateIndex))', html)
        self.assertIn('appendGateInput', html)
        self.assertIn('buildDorPatchArtifact', html)
        self.assertIn('buildEditedDorBytes', html)
        self.assertIn('parseDorBytes', html)
        self.assertIn('buildDorRecordBytes', html)
        self.assertIn('stageIniWorkbook', html)
        self.assertIn('const sameStage = state.meta?.stage === stageName', html)
        self.assertIn('const inheritedScenarioFiles = sameStage ? state.meta.scenarioFiles : {}', html)
        self.assertIn('scenarioFiles: inheritedScenarioFiles', html)
        self.assertIn('scenarioModel: sameStage ? state.meta.scenarioModel', html)
        self.assertIn('commonModel: sameStage ? state.meta.commonModel', html)
        self.assertIn('meta.scenarioFiles?.stg?.path', html)
        self.assertIn('buildEditedStageIniBytes', html)
        self.assertIn('buildStageIniWorkbookBytes', html)
        self.assertIn('function canBuildStageIniWorkbook', html)
        self.assertIn('if (!canBuildStageIniWorkbook() && !state.meta.scenarioFiles?.stageIniWorkbook?.path)', html)
        self.assertIn('buildXlsxBytes', html)
        self.assertIn('gateChanges', html)
        self.assertIn('accept=".m,.dor,.stg,.ini,.dat,.txt,.xlsx,.json"', html)
        self.assertIn('applyImportedPatchPayload', html)
        self.assertIn('normalizedImportedPatch', html)
        self.assertIn("const patchFiles = files.filter(file => /\\.json$/i.test(file.name));", html)
        self.assertIn("historyChanges: [...state.historyPatches.values()]", html)
        self.assertIn("stageIniGeneralChanges: [...state.stageIniGeneralPatches.values()]", html)
        self.assertGreaterEqual(html.count('existing?.before ?? before'), 4)
        self.assertIn('SCENARIO_FIELD_LABELS', html)
        self.assertIn('appendScenarioFields', html)
        self.assertIn('assignExistingSiteToForce', html)
        self.assertIn('state.activeForceKey = force.forceKey', html)
        self.assertIn('forceKey: `force:new:${Date.now()}:${state.scenario.forces.length}`', html)
        self.assertIn("siteKey: 'site:new:' + Date.now() + ':' + state.scenario.sites.length", html)
        self.assertIn('entityKey: `entity:new:${Date.now()}:${state.scenario.entities.length}:general`', html)
        self.assertIn('state.activeEntityKey = entity.entityKey', html)
        self.assertIn('removeSiteFromForce', html)
        self.assertIn("receiveButton.textContent = '\\u52a0\\u5165\\u5df2\\u6709\\u636e\\u70b9'", html)
        self.assertIn('receiveButton.disabled = !receiveSite.value', html)
        self.assertIn("const forceSites = scenarioRows('site').filter(site => site.parentForceKey === force.forceKey)", html)
        self.assertNotIn('addScenarioSite(force.forceKey)', html)
        self.assertIn('siteKindLabel', html)
        self.assertIn('function siteKindGroups', html)
        self.assertIn("document.createElement('optgroup')", html)
        self.assertIn('siteHouseAttrValue(a) - siteHouseAttrValue(b)', html)
        self.assertIn('house_attr: site.house_attr', html)
        self.assertIn('house_attr: Number(template?.house_attr || 0)', html)
        self.assertIn("if (houseAttr === 0) return '\\u57ce\\u6c60';", html)
        self.assertIn("if (houseAttr === 1) return '\\u519b\\u5be8';", html)
        self.assertIn("if (houseAttr === 2) return '\\u5c71\\u5be8';", html)
        self.assertIn("if (kind === 'site') {", html)
        self.assertIn("SITE_INI_FIELDS.includes(change.field)", html)
        self.assertIn("{ value: '0', label: '\\u57ce\\u6c60' }", html)
        self.assertIn('function appendFieldControl', html)
        self.assertIn("wrap.className = 'field-row'", html)
        self.assertIn('const tileW = Math.max(1, Number(heads.width || 105));', html)
        self.assertIn('receiveSite', html)
        self.assertIn('\\u7edf\\u5fa1', html)
        self.assertIn('\\u57ce\\u6c60', html)
        self.assertNotIn('land_water_hint', html)
        self.assertNotIn('id="layerVisibilityList"', html)
        reset_body = re.search(r'function resetEditState\(meta\) \{([\s\S]*?)\n\}', html)
        self.assertIsNotNone(reset_body)
        self.assertIn('renderDomainManagers();', reset_body.group(1))

    def test_editor_app_preserves_manager_state_and_derives_relations(self) -> None:
        """验证管理页滚动、直属页签、关系派生和点图层编辑显示。"""
        html = (ROOT / 'src' / 'san_tools' / 'map' / 'editor_app.html').read_text(encoding='utf-8')
        for marker in (
            'Array.from(tabs.children)',
            'Array.from(pages.children)',
            "appendGateInput(gateCard, gate, 'siteX', scenarioFieldLabel('gate', 'siteX'), true, true)",
            "appendGateInput(gateCard, gate, 'siteY', scenarioFieldLabel('gate', 'siteY'), true, true)",
            'syncSiteGateCoordinates(row, true)',
            'force.site_count = force.siteKeys.length',
            'site.primary_entity_count += 1',
            "const SCENARIO_DERIVED_FIELDS = new Set(['site_count', 'primary_entity_count'])",
            'entityListScrollTop: 0',
            'state.entityListScrollTop = currentEntityItems.scrollTop',
            'entityItems.scrollTop = state.entityListScrollTop',
            'function drawCurrentPointLayer',
            'Number(row.command || 0) > 0 && !activePersonIds.has',
            'drawCurrentPointLayer(rect.width, rect.height)',
            'ctx.arc(p.x + 20, p.y + 10, radius',
        ):
            self.assertIn(marker, html)
        self.assertNotIn("tabs.querySelectorAll('.source-tab')", html)
        self.assertNotIn("pages.querySelectorAll('.source-page')", html)
        self.assertIn('id="redoEdit"', html)
        self.assertIn('function redoLastEdit()', html)
        self.assertIn('state.redoStack.push(changes)', html)
        self.assertIn('const radius = 6 / state.transform.scale', html)
        self.assertIn('function stageIniSiteRows()', html)
        self.assertIn('const stageIniRowKey = seed?.stageIniRowKey || nextStageIniSiteRowKey()', html)
        self.assertIn('castle_scale: Number(template?.castle_scale || 1)', html)
        self.assertIn('population: Number(template?.population || 0)', html)
        self.assertIn('gold: Number(template?.gold || 0)', html)
        self.assertIn('food: Number(template?.food || 0)', html)
        self.assertIn('state.newStageIniGenerals.push(general)', html)
        self.assertNotIn("function addScenarioEntity() {\n  const general = inactiveStageIniGeneralRows()", html)
        self.assertIn('function loadLocalProjectFiles(fileList)', html)
        self.assertIn('state.localScenarioFiles.get(key)', html)

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
                [[1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0]],
                'stagger',
                (64, 64),
                'map.png',
                'minimap.png',
                {'source_output_size': [100, 100]},
                'palette.dat',
                {'available': False},
                ['#000000'],
                ['#010203'],
                {'available': False},
                scenario_files,
                {'available': True, 'forces': [], 'sites': [], 'entities': []},
                {'available': True, 'generals': [], 'skills': [], 'cities': [], 'soldiers': []},
            )
            payload = json.loads(out_path.read_text(encoding='utf-8'))
            self.assertEqual(payload['scenarioFiles']['dor']['path'], 'stage99.dor')
            self.assertEqual(payload['scenarioFiles']['stg']['path'], 'stage99.stg')
            self.assertEqual(payload['scenarioFiles']['heads']['path'], 'heads.dat')
            self.assertFalse(payload['scenarioFiles']['stageIni']['available'])
            self.assertFalse(payload['scenarioFiles']['stageIniWorkbook']['available'])
            self.assertTrue(payload['scenarioModel']['available'])
            self.assertTrue(payload['commonModel']['available'])
            self.assertEqual(payload['pointPalette'], ['#000000'])
            self.assertEqual(payload['minimapPalette'], ['#010203'])
            self.assertIn('blocked', payload['editableLayers'])
            self.assertIn('terrain_tag', payload['editableLayers'])
            self.assertEqual(payload['resourceLayers'], ['acwx', 'acwy', 'acwz'])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_stage_ini_reference_and_workbook_are_exported_for_stage01(self) -> None:
        game_dir = require_game_data(ROOT)
        if not (game_dir / 'stage.ini').exists() or not (game_dir / 'stage01.dor').exists():
            self.skipTest('missing stage01 or stage.ini sample')

        tmp_dir = ROOT / 'derived' / 'test_tmp' / 'editor_bundle_stage_ini_files'
        shutil.rmtree(tmp_dir, ignore_errors=True)
        stage_dir = tmp_dir / 'stage01'
        stage_dir.mkdir(parents=True, exist_ok=True)
        try:
            scenario_files = copy_scenario_reference_files(game_dir, stage_dir, 'stage01')
            self.assertTrue(scenario_files['stageIni']['available'])
            self.assertTrue(scenario_files['stageIniWorkbook']['available'])
            self.assertTrue((stage_dir / 'stage.ini').exists())
            self.assertTrue((stage_dir / 'stage_ini.xlsx').exists())
            self.assertTrue((stage_dir / 'History.txt').exists())
            sheets = build_stage_ini_workbook_sheets(game_dir)
            sheet_names = {sheet['name'] for sheet in sheets}
            self.assertIn('general_master', sheet_names)
            self.assertIn('city_master', sheet_names)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)



    def test_stage_ini_patch_model_maps_stage_ini_offsets(self) -> None:
        game_dir = require_game_data(ROOT)
        try:
            find_text_data_dir(ROOT)
        except FileNotFoundError:
            self.skipTest('缺少 stage.ini 文本映射样本')
        if not (game_dir / 'stage.ini').exists():
            self.skipTest('missing stage.ini or txt mapping sample')

        model = build_stage_ini_patch_model(ROOT, game_dir)
        self.assertTrue(model['available'], model)
        self.assertEqual(model['fileSize'], (game_dir / 'stage.ini').stat().st_size)
        self.assertIn('site', model['fieldMap'])
        self.assertIn('entity', model['fieldMap'])
        self.assertIn('general', model['fieldLocations'])
        self.assertIn('castle', model['fieldLocations'])
        self.assertIn('workbookSheets', model)
        self.assertEqual([sheet['name'] for sheet in model['workbookSheets']], ['general', 'castle'])
        command_key = ''.join(chr(code) for code in (0x7d71, 0x5fa1, 0x529b))
        population_key = ''.join(chr(code) for code in (0x4eba, 0x53e3))
        self.assertGreater(model['fieldLocations']['general']['1'][command_key]['byteOffset'], 0)
        self.assertGreater(model['fieldLocations']['castle']['1'][population_key]['byteOffset'], 0)


    def test_stage01_scenario_and_common_models_use_stg_and_stage_ini(self) -> None:
        """验证编辑器 bundle 使用 .stg 和 stage.ini 生成管理面板数据源。"""
        game_dir = require_game_data(ROOT)
        if not (game_dir / 'stage01.stg').exists() or not (game_dir / 'stage.ini').exists():
            self.skipTest('缺少 stage01.stg 或 stage.ini 样本')

        scenario = build_editor_scenario_model(game_dir, 'stage01')
        common = build_editor_common_model(ROOT)

        self.assertTrue(scenario['available'])
        self.assertGreater(len(scenario['forces']), 0)
        self.assertGreater(len(scenario['sites']), 0)
        self.assertGreater(len(scenario['entities']), 0)
        self.assertIn('force_name', scenario['forces'][0])
        self.assertIn('site_name', scenario['sites'][0])
        self.assertIn('entity_name', scenario['entities'][0])
        self.assertIn('force_name', scenario['forces'][0]['patchFields'])
        self.assertIn('coord_x', scenario['sites'][0]['patchFields'])
        self.assertIn('troop_count', scenario['entities'][0]['patchFields'])
        self.assertIn('stgLayout', scenario)
        self.assertIn('stgLayout', scenario['forces'][0])
        self.assertIn('stgLayout', scenario['sites'][0])
        self.assertIn('optionalEntityFlagOffsets', scenario['sites'][0]['stgLayout'])
        self.assertIn('stgLayout', scenario['entities'][0])
        self.assertGreater(len(scenario['big5CharMap']), 0)
        links = build_editor_site_links(ROOT, 'stage01')
        self.assertTrue(links['available'])
        self.assertGreater(links['gateCount'], 0)
        self.assertEqual(links['gateCount'], links['matchedGateCount'])
        self.assertTrue(common['available'])
        self.assertGreater(len(common['generals']), 0)
        self.assertGreater(len(common['historyGenerals']), 0)
        self.assertTrue(all(int(row['command']) > 0 for row in common['historyGenerals']))
        self.assertIn('join_year', common['historyGenerals'][0])
        self.assertTrue(common['historyTable']['available'])
        self.assertIn(''.join(chr(code) for code in (0x7de8, 0x865f)), common['historyTable']['headers'])
        self.assertIn('rowKey', common['historyTable']['rows'][0])
        model = build_stage_ini_patch_model(ROOT, game_dir)
        general_sheet = next(sheet for sheet in model['workbookSheets'] if sheet['name'] == 'general')
        self.assertGreater(len(general_sheet['rows']), 0)
        self.assertLessEqual(len(general_sheet['rows']), len(common['generals']))
        self.assertIn(''.join(chr(code) for code in (0x7d71, 0x5fa1, 0x529b)), general_sheet['headers'])
        self.assertGreater(len(common['skills']), 0)
        self.assertGreater(len(common['cities']), 0)
        self.assertGreater(len(common['soldiers']), 0)
        self.assertGreater(len(common['big5CharMap']), 0)
        tmp_dir = ROOT / 'derived' / 'test_tmp' / 'heads_atlas'
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            heads = export_heads_atlas(game_dir, tmp_dir, [(i, i, i) for i in range(256)])
            self.assertTrue(heads['available'])
            exporter = (ROOT / 'src' / 'san_tools' / 'map' / 'export_editor_bundle.py').read_text(encoding='utf-8')
            self.assertIn('export_heads_atlas(game_dir, stage_dir, SAN_RGB_PALETTE)', exporter)
            self.assertGreater(heads['count'], 0)
            self.assertTrue((tmp_dir / heads['image']).exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

if __name__ == '__main__':
    unittest.main()
