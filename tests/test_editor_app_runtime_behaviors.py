from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "src" / "san_tools" / "map" / "editor_app.html"


def script_source() -> str:
    """读取编辑器内联脚本。"""

    html = EDITOR.read_text(encoding="utf-8")
    match = re.search(r"<script>([\s\S]*)</script>", html)
    if not match:
        raise AssertionError("未找到编辑器脚本")
    return match.group(1)


def function_range(source: str, start_name: str, end_name: str) -> str:
    """按相邻函数名截取可独立执行的脚本片段。"""

    start = source.index(f"function {start_name}")
    end = source.index(f"function {end_name}", start)
    return source[start:end]


class TestEditorRuntimeBehaviors(unittest.TestCase):
    """通过 Node 小型运行环境验证关键状态转换。"""

    def run_node(self, body: str) -> None:
        if not shutil.which("node"):
            self.skipTest("缺少 node")
        subprocess.run(["node", "-e", body], cwd=ROOT, check=True, capture_output=True, text=True)

    def test_map_change_can_be_undone_and_redone(self) -> None:
        """验证新修改、撤销、重做形成闭合状态链。"""

        source = script_source()
        functions = function_range(source, "applyChangeSet", "resetSelectedLayerChange")
        harness = """
const state = {
  meta: { records: [[1]], editableLayers: ['terrain_tag'] },
  originalRecords: [[1]], undoStack: [], redoStack: []
};
function canonicalFieldName(value) { return value; }
function fieldIndex() { return 0; }
function recordAt() { return state.meta.records[0]; }
function updateLayerStats() {}
function syncPatchFor() {}
function refreshAfterRecordEdit() {}
"""
        checks = """
if (!applyChangeSet([{ x: 0, y: 0, field: 'terrain_tag', after: 9 }])) throw new Error('修改未生效');
if (state.meta.records[0][0] !== 9 || state.undoStack.length !== 1) throw new Error('撤销栈错误');
undoLastEdit();
if (state.meta.records[0][0] !== 1 || state.redoStack.length !== 1) throw new Error('撤销错误');
redoLastEdit();
if (state.meta.records[0][0] !== 9 || state.undoStack.length !== 1 || state.redoStack.length !== 0) throw new Error('重做错误');
"""
        self.run_node(harness + functions + checks)

    def test_new_site_uses_stage_ini_fields_and_becomes_active(self) -> None:
        """验证新增据点具有完整母表字段并立即成为当前据点。"""

        source = script_source()
        functions = function_range(source, "stageIniSiteRows", "stageIniGeneralByKey")
        harness = """
const model = {
  workbookSheets: [{
    name: 'castle',
    headers: ['row_id', 'title', '都市索引', '房子属性', '城规模', '人口', '金', '粮', '待命士兵', '开发值', '商业值', '治安值', '坐标X', '坐标Y', '太守'],
    rows: [[2, '测试城', 2, 0, 4, 2100, 6000, 15000, 10, 70, 70, 50, 20, 30, 0]]
  }],
  fieldMap: { site: { fields: {
    city_index: '都市索引', house_attr: '房子属性', castle_scale: '城规模', population: '人口',
    gold: '金', food: '粮', standby_soldier: '待命士兵', develop: '开发值', commerce: '商业值',
    security: '治安值', coord_x: '坐标X', coord_y: '坐标Y', governor: '太守'
  } } }
};
const force = { forceKey: 'force:0', forceIndex: 0, force_name: '测试势力' };
const state = {
  selected: { col: 40, row: 50 }, activeForceKey: force.forceKey, activeSiteKey: '',
  scenario: { sites: [], forces: [force], forceByKey: new Map([[force.forceKey, force]]), siteByKey: new Map() }
};
model.workbookSheets[0].headers.push('develop_cap', 'commerce_cap', 'security_cap', 'officer_slot');
model.workbookSheets[0].rows[0].push(120, 130, 140, 9);
function stageIniPatchModel() { return model; }
function scenarioRows(kind) { return kind === 'site' ? state.scenario.sites.filter(row => !row.deleted) : state.scenario.forces; }
function refreshScenarioRelations() { state.scenario.siteByKey = new Map(state.scenario.sites.map(row => [row.siteKey, row])); }
function storeScenarioPatch() {}
function setActiveSite(key) { state.activeSiteKey = key; }
function renderSitePicker() {}
function renderDomainManagers() {}
"""
        checks = """
addScenarioSite(force.forceKey);
const site = state.scenario.sites[0];
if (!site || state.activeSiteKey !== site.siteKey) throw new Error('新增据点未选中');
if (site.city_index !== 2 || site.castle_scale !== 4 || site.population !== 2100 || site.gold !== 6000 || site.food !== 15000) throw new Error('stage.ini 基本字段缺失');
if (site.coord_x !== 40 || site.coord_y !== 50 || site.stageIniRowKey !== '2') throw new Error('据点坐标或母表行错误');
addScenarioSite(force.forceKey);
const appended = state.scenario.sites[1];
if (appended.city_index !== 3 || appended.stageIniRowKey !== '3') throw new Error('新增城池的都市索引与母表行号未独立递增');
if (appended.stageIniValues.develop_cap !== 120 || appended.stageIniValues.commerce_cap !== 130 || appended.stageIniValues.security_cap !== 140 || appended.stageIniValues.officer_slot !== 9) throw new Error('新增城池未继承完整母表模板');
if (appended.stageIniValues.row_id !== '3' || appended.stageIniValues.title !== 'Site 2') throw new Error('新增城池母表标识或标题未初始化');
"""
        self.run_node(harness + functions + checks)


    def test_add_existing_general_refreshes_site_immediately(self) -> None:
        """验证据点添加已有武将后关系与据点 UI 同步刷新。"""

        source = script_source()
        functions = function_range(source, "stageIniGeneralByKey", "addScenarioEntity")
        harness = """
const force = { forceKey: 'force:0', forceIndex: 0, force_name: '测试势力', force_lord_person_id: 1 };
const site = { siteKey: 'site:0', site_name: '测试城', city_index: 2, parentForceKey: force.forceKey, entityKeys: [] };
const general = { stageIniGeneralKey: 'stageini:88', stageIniRowKey: '88', name: '测试武将', person_id: 88, portrait_id: 3, command: 70 };
let siteRefreshes = 0;
const state = {
  activeSiteKey: site.siteKey, activeEntityKey: '', activeHistoryGeneralKey: '',
  scenario: { entities: [], siteByKey: new Map([[site.siteKey, site]]), forceByKey: new Map([[force.forceKey, force]]) }
};
function stageIniGeneralRows() { return [general]; }
function inactiveHistoryGeneralRows() { return [general]; }
function historyGeneralKey(row) { return row.stageIniGeneralKey; }
function scenarioRows(kind) { return kind === 'site' ? [site] : kind === 'force' ? [force] : state.scenario.entities; }
function refreshScenarioRelations() { site.entityKeys = state.scenario.entities.filter(row => row.parentSiteKey === site.siteKey).map(row => row.entityKey); }
function storeScenarioPatch() {}
function renderSitePicker() { siteRefreshes += 1; }
function renderDomainManagers() {}
"""
        checks = """
addExistingGeneralToSite(site.siteKey, general.stageIniGeneralKey);
if (state.scenario.entities.length !== 1 || site.entityKeys.length !== 1) throw new Error('武将关系未立即生效');
if (state.scenario.entities[0].person_id !== 88 || siteRefreshes !== 1) throw new Error('据点 UI 未同步刷新');
if ('stageIniValues' in state.scenario.entities[0] || 'stageIniGeneralKey' in state.scenario.entities[0]) throw new Error('母表 UI 元数据泄漏到 STG Entity');
"""
        self.run_node(harness + functions + checks)

    def test_general_manager_creates_master_row_without_site_membership(self) -> None:
        """验证武将管理新增只创建母表行，不写入据点 Entity。"""

        source = script_source()
        functions = function_range(source, "addScenarioEntity", "scenarioFieldLabel")
        harness = """
const headers = ['row_id', 'title', '人物编号', '头像编号', '统御力'];
const state = {
  newStageIniGenerals: [], activeEntityKey: 'old', activeHistoryGeneralKey: '',
  stageIniGeneralPatches: new Map(), scenario: { entities: [] }
};
function stageIniGeneralSheet() { return { headers }; }
function stageIniGeneralRows() { return [{ person_id: 272 }]; }
function stageIniGeneralFieldHeaders() { return { person_id: '人物编号', portrait_id: '头像编号', command: '统御力' }; }
function schedulePatchRefresh() {}
function ensureHistoryRow() {}
function renderDomainManagers() {}
"""
        checks = """
addScenarioEntity();
if (state.newStageIniGenerals.length !== 1) throw new Error('未创建 stage.ini 武将');
if (state.scenario.entities.length !== 0) throw new Error('错误加入了据点 Entity');
if (state.activeHistoryGeneralKey !== 'stageini:273' || state.newStageIniGenerals[0].command !== 1) throw new Error('新武将状态错误');
"""
        self.run_node(harness + functions + checks)

    def test_new_gate_edit_does_not_change_existing_gate(self) -> None:
        """验证新增城门具有独立键和门序号，编辑不会串到已有城门。"""

        source = script_source()
        functions = function_range(source, "gateKey", "deleteSiteGate")
        harness = """
const existing = { gateKey: 'gate:old', gateIndex: 5, group: 2, doorIndex: 3, doorX: 10, doorY: 20, deleted: false };
const state = {
  gates: [existing], selected: { col: 30, row: 40 }, gatePatches: new Map(),
  meta: { siteLinks: {} }, scenario: null
};
function dorRecordKey(group, doorIndex) { return String(group) + ':' + String(doorIndex); }
function schedulePatchRefresh() {}
function buildSiteIndex() { return null; }
function renderSitePicker() {}
function scheduleDraw() {}
"""
        checks = """
addSiteGate({ siteKey: 'site:1', cityName: '测试城', forceIndex: 2, mapX: 50, mapY: 60 });
const added = state.gates[1];
if (!added || added.doorIndex !== 4 || added.doorX !== 30 || added.doorY !== 40) throw new Error('新增城门初值错误');
updateGateField(added.gateKey, 'doorX', '99', true);
if (added.doorX !== 99 || existing.doorX !== 10) throw new Error('新增城门编辑串改已有城门');
"""
        self.run_node(harness + functions + checks)
    def test_new_master_rows_require_append_layout(self) -> None:
        """验证旧 bundle 缺少新增布局时会阻断母表扩展。"""

        source = script_source()
        functions = function_range(source, "validationIssues", "renderValidationPanel")
        harness = """
const model = { available: true, fieldLocations: { castle: {}, general: {} } };
const state = {
  meta: {
    records: [[0]], width: 1, height: 1,
    sidecars: { available: true }, siteLinks: { available: true },
    scenarioFiles: {
      dor: { path: 'stage01.dor' }, stg: { path: 'stage01.stg' },
      stageIni: { path: 'stage.ini' }, stageIniWorkbook: { path: 'stage_ini.xlsx' }
    }
  },
  commonModel: { stageIniPatchModel: model },
  scenario: { sites: [{ isNew: true, siteKey: 'site:new', house_attr: 0, city_index: 43, stageIniRowKey: '43', deleted: false }] },
  newStageIniGenerals: [{ isNew: true, stageIniRowKey: '273' }],
  patches: new Map()
};
function canBuildStageIniWorkbook() { return true; }
function stageIniPatchModel() { return model; }
function scenarioRows(kind) { return kind === 'site' ? state.scenario.sites : []; }
function siteHouseAttrValue(site) { return Number(site.house_attr || 0); }
function unsupportedScenarioChanges() { return []; }
function recordFieldBounds() { return { min: 0, max: 255 }; }
"""
        checks = """
const errors = validationIssues().filter(issue => issue.level === 'error');
if (errors.length !== 1) throw new Error('未阻断缺少布局的母表扩展：' + JSON.stringify(errors));
if (!errors[0].text.includes('新增布局')) throw new Error('错误信息不明确');
"""
        self.run_node(harness + functions + checks)

    def test_raw_record_can_be_restored_at_once(self) -> None:
        """验证 Raw 一键恢复会恢复当前 Cell 的全部可编辑字段。"""

        source = script_source()
        functions = function_range(source, "resetSelectedRecord", "resetAllChanges")
        harness = """
const state = {
  selected: { col: 0, row: 0 },
  meta: { editableRecordFields: ['a', 'b'], records: [[9, 8]] },
  originalRecords: [[1, 2]]
};
function recordIndex() { return 0; }
function fieldIndex(field) { return field === 'a' ? 0 : 1; }
function applyChangeSet(changes) { for (const change of changes) state.meta.records[0][fieldIndex(change.field)] = change.after; return true; }
const canvas = { getBoundingClientRect() { return { width: 100, height: 100 }; } };
const els = { coordX: {}, coordY: {}, status: {} };
function scheduleDraw() {}
function cellToWorld() { return { x: 0, y: 0 }; }
function selectCell() {}
function refreshSide() {}
"""
        checks = """
resetSelectedRecord();
if (state.meta.records[0][0] !== 1 || state.meta.records[0][1] !== 2) throw new Error('整记录恢复失败');
"""
        self.run_node(harness + functions + checks)

    def test_coordinate_search_selects_and_centers_cell(self) -> None:
        """验证坐标搜索会选择合法 Cell 并触发定位。"""

        source = script_source()
        functions = function_range(source, "findCellByCoordinates", "resetAllChanges")
        harness = """
let selected = null; let focused = 0; let refreshed = 0;
const state = { meta: { width: 10, height: 20 } };
const els = { coordX: { value: '3' }, coordY: { value: '7' }, status: { textContent: '' } };
function selectCell(cell) { selected = cell; }
function focusSelectedCell() { focused += 1; }
function refreshSide() { refreshed += 1; }
"""
        checks = """
if (!findCellByCoordinates()) throw new Error('合法坐标被拒绝');
if (selected.col !== 3 || selected.row !== 7 || focused !== 1 || refreshed !== 1) throw new Error('坐标选择或定位未执行');
els.coordX.value = '10';
if (findCellByCoordinates()) throw new Error('越界坐标未被拒绝');
"""
        self.run_node(harness + functions + checks)

    def test_full_copy_captures_every_selected_cell_and_cut_clears_non_base_fields(self) -> None:
        """验证全复制包含全部选中 Cell，剪切后源区域只保留底层地表。"""

        source = script_source()
        functions = function_range(source, "regionCellHasContent", "refreshCompositeList")
        harness = """
const fields = ['acwx', 'acwy', 'acwz', 'terrain_tag', 'blocked', 'site_trigger', 'site_area', 'minimap_color'];
const state = {
  regionCopyMode: 'full',
  meta: {
    width: 2, height: 1, fields, editableRecordFields: fields.slice(),
    records: [[10, 20, 30, 1, 2, 3, 4, 60], [11, -1, -1, 0, 0, 0, 0, 61]]
  },
  selected: { col: 1, row: 0 },
  selectedCells: new Map([['0,0', { col: 0, row: 0 }], ['1,0', { col: 1, row: 0 }]])
};
let appliedBatches = 0;
function canonicalFieldName(value) { return value; }
function fieldIndex(field) { return fields.indexOf(field); }
function selectedCellList() { return [...state.selectedCells.values()]; }
function selectedCellBounds() { return { left: 0, right: 1, top: 0, bottom: 0, width: 2, height: 1, count: 2 }; }
function currentRegionBounds() { return selectedCellBounds(); }
function recordAt(cell) { return state.meta.records[cell.row * state.meta.width + cell.col]; }
function applyChangeSet(changes) {
  appliedBatches += 1;
  for (const change of changes) recordAt({ col: change.x, row: change.y })[fields.indexOf(change.field)] = change.after;
  return true;
}
"""
        checks = """
const snapshot = cutRegionSnapshot();
if (!snapshot || snapshot.copyMode !== 'full' || snapshot.cells.length !== 2) throw new Error('全复制未包含全部选中 Cell');
if (snapshot.fields.join(',') !== fields.join(',')) throw new Error('全复制未保留全部字段');
if (state.meta.records[0].join(',') !== '10,-1,-1,0,0,0,0,0') throw new Error('全复制剪切未清理到底层地表');
if (state.meta.records[1].join(',') !== '11,-1,-1,0,0,0,0,0') throw new Error('纯底层 Cell 未参与全复制剪切');
if (appliedBatches !== 1) throw new Error('区域剪切未作为单次撤销事务提交');
"""
        self.run_node(harness + functions + checks)

    def test_non_base_copy_filters_cells_and_excludes_object_and_minimap_fields(self) -> None:
        """验证非底层复制按六个内容字段筛选，并排除 acwz 与 minimap_color。"""

        source = script_source()
        functions = function_range(source, "regionCellHasContent", "refreshCompositeList")
        harness = """
const fields = ['acwx', 'acwy', 'acwz', 'terrain_tag', 'blocked', 'site_trigger', 'site_area', 'minimap_color'];
const state = {
  regionCopyMode: 'non-base',
  meta: {
    width: 3, height: 1, fields, editableRecordFields: fields.slice(),
    records: [[10, 20, 30, 1, 2, 3, 4, 60], [11, -1, -1, 5, 0, 0, 0, 61], [12, -1, -1, 0, 0, 0, 0, 62]]
  },
  selected: { col: 1, row: 0 },
  selectedCells: new Map([['0,0', { col: 0, row: 0 }], ['1,0', { col: 1, row: 0 }], ['2,0', { col: 2, row: 0 }]])
};
function canonicalFieldName(value) { return value; }
function fieldIndex(field) { return fields.indexOf(field); }
function selectedCellList() { return [...state.selectedCells.values()]; }
function selectedCellBounds() { return { left: 0, right: 2, top: 0, bottom: 0, width: 3, height: 1, count: 3 }; }
function currentRegionBounds() { return selectedCellBounds(); }
function recordAt(cell) { return state.meta.records[cell.row * state.meta.width + cell.col]; }
function applyChangeSet(changes) {
  for (const change of changes) recordAt({ col: change.x, row: change.y })[fields.indexOf(change.field)] = change.after;
  return true;
}
"""
        checks = """
const snapshot = cutRegionSnapshot();
if (!snapshot || snapshot.copyMode !== 'non-base' || snapshot.cells.length !== 2) throw new Error('非底层复制的 Cell 筛选错误');
if (snapshot.fields.includes('acwz') || snapshot.fields.includes('minimap_color')) throw new Error('非底层复制包含了排除字段');
if (snapshot.cells[0].record.join(',') !== '10,20,1,2,3,4') throw new Error('非底层快照字段顺序错误');
if (state.meta.records[0].join(',') !== '10,-1,30,0,0,0,0,60') throw new Error('非底层剪切错误清除了排除字段');
if (state.meta.records[2].join(',') !== '12,-1,-1,0,0,0,0,62') throw new Error('无内容 Cell 不应参与非底层剪切');
"""
        self.run_node(harness + functions + checks)

    def test_edited_outline_respects_overlay_toggle(self) -> None:
        """验证已编辑绿框可由数据叠加开关独立显示和隐藏。"""

        source = script_source()
        functions = function_range(source, "drawEditedCellOverlay", "drawMinimap")
        harness = """
let strokes = 0;
const ctx = { save() {}, restore() {}, stroke() { strokes += 1; }, set lineWidth(value) {}, set strokeStyle(value) {} };
const state = { transform: { scale: 1 }, patches: new Map([['a', { x: 1, y: 2 }], ['b', { x: 3, y: 4 }]]), dataOverlayVisible: { edited: false } };
function shouldShowDataOverlays() { return true; }
function diamondPath() {}
"""
        checks = """
drawEditedCellOverlay();
if (strokes !== 0) throw new Error('关闭后仍显示已编辑绿框');
state.dataOverlayVisible.edited = true;
drawEditedCellOverlay();
if (strokes !== 2) throw new Error('开启后未显示全部已编辑绿框');
"""
        self.run_node(harness + functions + checks)

    def test_zip_store_contains_all_export_files(self) -> None:
        """验证导出归档是包含全部文件的标准 ZIP 存储包。"""

        source = script_source()
        functions = function_range(source, "crc32", "buildXlsxBytes")
        checks = """
const archive = zipStore([
  { name: 'stage01.m', data: new Uint8Array([1, 2, 3]) },
  { name: 'stage.ini', data: new Uint8Array([4, 5]) }
]);
const view = new DataView(archive.buffer, archive.byteOffset, archive.byteLength);
if (view.getUint32(0, true) !== 0x04034b50 || view.getUint32(archive.length - 22, true) !== 0x06054b50) throw new Error('ZIP 结构签名错误');
const text = new TextDecoder().decode(archive);
if (!text.includes('stage01.m') || !text.includes('stage.ini')) throw new Error('ZIP 缺少导出文件');
"""
        self.run_node(functions + checks)
    def test_data_minimap_builds_without_full_map_image(self) -> None:
        """验证大地图无整图 Canvas 时仍可由 minimap_color 构建小地图。"""

        source = script_source()
        functions = function_range(source, "rebuildDataMinimap", "setPairs")
        harness = """
const fills = [];
const document = { createElement() { return { width: 0, height: 0, getContext() { return { fillStyle: '', fillRect(x, y, w, h) { fills.push([x, y, w, h, this.fillStyle]); } }; } }; } };
const state = { meta: { width: 2, height: 2, origin: [64, 64], records: [[0], [1], [1], [0]], pointPalette: ['#ff0000', '#00ff00'], minimapPalette: ['#000000', '#ffffff'] }, minimap: null };
function fieldIndex() { return 0; }
function canvasSizeForMeta() { return { width: 228, height: 168 }; }
function cellToWorld(col, row) { return { x: 64 + col * 40 + (row & 1 ? 20 : 0), y: 64 + row * 10 }; }
"""
        checks = """
rebuildDataMinimap();
if (!state.minimap || state.minimap.width !== 228 || state.minimap.height !== 168) throw new Error('小地图未按主画布比例渲染');
if (fills.length !== 5) throw new Error('小地图背景或 Cell 未渲染');
if (fills[1][4] !== '#000000' || fills[2][4] !== '#ffffff') throw new Error('小地图误用数据标记色板');
if (fills[1][0] !== 84 || fills[1][1] !== 74) throw new Error('Cell 未按世界坐标投影');
"""
        self.run_node(harness + functions + checks)
    def test_legacy_new_site_master_row_is_migrated(self) -> None:
        """验证旧 Patch 的冲突行号会迁移，并从城池模板补齐完整字段。"""

        source = script_source()
        functions = (
            function_range(source, "stageIniSiteRows", "nextAvailableStageIniSite")
            + function_range(source, "stageIniSiteTemplate", "addScenarioSite")
            + function_range(source, "stageIniRowsForKind", "applyStageIniRowPatch")
        )
        harness = """
const model = {
  available: true,
  workbookSheets: [{ name: 'castle', headers: ['row_id', 'title', 'city', 'cap'], rows: [['43', 'OLD_CITY', 42, 150]] }],
  fieldMap: { site: { sheet: 'castle', fields: { city_index: 'city' } } },
  fieldLocations: { castle: {} }
};
const site = {
  isNew: true, deleted: false, house_attr: 0, siteKey: 'site:new:83', site_name: 'NORTH_STATE',
  city_index: 84, stageIniRowKey: '43', stageIniValues: {}
};
const state = {
  commonModel: { stageIniPatchModel: model },
  scenario: { sites: [site], siteByKey: new Map([[site.siteKey, site]]) },
  scenarioPatches: new Map([['site:update', { kind: 'site', key: site.siteKey, op: 'update', field: 'city_index' }]]),
  stageIniGeneralEdits: new Map()
};
const SITE_INI_FIELDS = ['city_index'];
function stageIniPatchModel() { return model; }
function scenarioRows(kind) { return kind === 'site' ? state.scenario.sites : []; }
function siteHouseAttrValue(row) { return Number(row.house_attr || 0); }
function stageIniGeneralRows() { return []; }
"""
        checks = """
const rows = stageIniRowsForKind('site');
if (rows.length !== 1 || rows[0].stageIniRowKey !== '44') throw new Error('旧 Patch 冲突行号未迁移');
if (rows[0].stageIniValues.title !== 'NORTH_STATE' || rows[0].stageIniValues.cap !== 150) throw new Error('新城标题或完整模板字段未补齐');
if (rows[0].city_index !== 84 || rows[0].stageIniValues.row_id !== '44') throw new Error('迁移后的都市索引或行标识错误');
"""
        self.run_node(harness + functions + checks)
    def test_new_stage_ini_master_rows_are_rebuilt(self) -> None:
        """验证新增武将和城池会扩展 stage.ini 两个母表区段。"""

        source = script_source()
        functions = function_range(source, "stageIniPatchModel", "buildStageIniWorkbookBytes")
        harness = """
const model = {
  available: true,
  fieldMap: {
    entity: { sheet: 'general', fields: { person_id: '人物编号' } },
    site: { sheet: 'castle', fields: { city_index: '都市索引' } }
  },
  fieldLocations: { general: {}, castle: {} },
  workbookSheets: [{ name: 'castle', headers: ['row_id', 'title', '都市索引'], rows: [] }],
  appendLayout: {
    mainCount: 1, mainStride: 8, tailOffset: 16, tailStride: 4,
    general: { insertOffset: 12, rowBytes: 8, titleBytes: 4, numericHeaders: ['人物编号'] },
    castle: { insertOffset: 18, rowBytes: 6, titleBytes: 2, numericHeaders: ['都市索引'] }
  }
};
const general = { isNew: true, stageIniRowKey: '8', entity_name: 'G', person_id: 8, stageIniValues: { title: 'G', 人物编号: 8 } };
const site = { isNew: true, stageIniRowKey: '9', site_name: 'C', city_index: 9, house_attr: 0, deleted: false, stageIniValues: { title: 'X' } };
const state = {
  meta: { commonModel: { big5CharMap: { G: [71], C: [67], X: [88] } } },
  commonModel: { stageIniPatchModel: model },
  scenarioPatches: new Map(), stageIniGeneralEdits: new Map(),
  scenario: { sites: [site], siteByKey: new Map([[site.siteKey, site]]) }
};
const SITE_INI_FIELDS = [];
function stageIniSiteRows() { return []; }
function stageIniSiteTemplate() { return null; }
function stageIniGeneralRows() { return [general]; }
function stageIniGeneralSaveRows() { return [general]; }
function scenarioRows(kind) { return kind === 'site' ? [site] : []; }
function siteHouseAttrValue(row) { return Number(row.house_attr || 0); }
function encodeBig5Text(text) { return new Uint8Array([...String(text)].map(char => char.charCodeAt(0))); }
function concatBytes(parts) {
  const result = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0));
  let offset = 0; for (const part of parts) { result.set(part, offset); offset += part.length; }
  return result;
}
"""
        checks = """
const original = new Uint8Array(20);
new DataView(original.buffer).setUint32(0, 1, true);
new DataView(original.buffer).setUint32(4, 8, true);
original[18] = 0xaa; original[19] = 0xbb;
const edited = buildEditedStageIniBytes(original);
const view = new DataView(edited.buffer);
if (edited.length !== 36 || view.getUint32(0, true) !== 2) throw new Error('主表块数或文件长度错误');
if (edited[12] !== 71 || view.getUint32(16, true) !== 8) throw new Error('新增武将母表行错误');
if (edited[26] !== 67 || view.getUint32(28, true) !== 9) throw new Error('新增城池母表标题或数值错误');
if (edited[34] !== 0xaa || edited[35] !== 0xbb) throw new Error('新增城池破坏了后续 tail 步长对齐');
const sheets = cloneWorkbookSheets();
const sheetMap = new Map(sheets.map(sheet => [sheet.name, sheet]));
applyWorkbookRowPatch(sheetMap, site, 'site');
if (sheets[0].rows[0][0] !== '9' || sheets[0].rows[0][1] !== 'C' || sheets[0].rows[0][2] !== '9') throw new Error('新增城池工作簿标题或字段错误');
"""
        self.run_node(harness + functions + checks)
    def test_unedited_stage_ini_stays_byte_identical(self) -> None:
        """验证仅加载剧本不会把 STG 当前值批量覆盖回 stage.ini。"""

        source = script_source()
        functions = function_range(source, "stageIniPatchModel", "buildStageIniWorkbookBytes")
        harness = """
const model = { available: true, fieldMap: {}, fieldLocations: {} };
const state = {
  commonModel: { stageIniPatchModel: model },
  scenarioPatches: new Map(),
  stageIniGeneralEdits: new Map(),
  scenario: { siteByKey: new Map() }
};
const SITE_INI_FIELDS = [];
function stageIniSiteRows() { return []; }
function stageIniSiteTemplate() { return null; }
function stageIniGeneralRows() { return []; }
function scenarioRows() { return []; }
function siteHouseAttrValue() { return 0; }
"""
        checks = """
const original = new Uint8Array([1, 2, 3, 4, 5]);
const edited = buildEditedStageIniBytes(original);
if (edited.length !== original.length || edited.some((value, index) => value !== original[index])) throw new Error('未编辑 stage.ini 被污染');
"""
        self.run_node(harness + functions + checks)

    def test_patch_import_restores_all_editor_domains_atomically(self) -> None:
        """验证 Patch 可恢复全部数据域、重复导入幂等且冲突时不产生部分修改。"""

        source = script_source()
        functions = function_range(source, "patchValuesEqual", "localScenarioFileKey")
        harness = """
const force = { forceKey: 'force:0', force_name: '旧势力', deleted: false };
const gate = { gateKey: 'gate:0', doorX: 10, deleted: false };
const historyBase = { rowKey: '1', 加入年: '190' };
const generalBase = { stageIniRowKey: '1', stageIniValues: { 统御力: '70' } };
const state = {
  meta: { stage: 'stage01', width: 1, height: 1, fields: ['terrain_tag'], records: [[1]], siteLinks: {} },
  originalRecords: [[1]], patches: new Map(), undoStack: [], redoStack: [],
  scenario: { available: true, forces: [force], sites: [], entities: [] },
  scenarioPatches: new Map(), gates: [gate], gatePatches: new Map(),
  historyEdits: new Map(), historyPatches: new Map(),
  newStageIniGenerals: [], stageIniGeneralEdits: new Map(), stageIniGeneralPatches: new Map()
};
const els = { status: { textContent: '' } };
function canonicalFieldName(value) { return value; }
function fieldIndex(field) { return state.meta.fields.indexOf(field); }
function recordFieldBounds() { return { min: 0, max: 255 }; }
function applyChangeSet(changes) { for (const change of changes) state.meta.records[change.y * state.meta.width + change.x][fieldIndex(change.field)] = change.after; return !!changes.length; }
function scenarioPatchKey(kind, key, op, field = '') { return `${kind}:${op}:${key}:${field}`; }
function gateKey(row) { return row.gateKey; }
function normalizeGateRows(rows) { return rows.map(row => ({ ...row })); }
function historyTableRows() { return [{ ...historyBase, ...(state.historyEdits.get('1') || {}) }]; }
function stageIniGeneralRows() { return [{ ...generalBase, stageIniValues: { ...generalBase.stageIniValues, ...(state.stageIniGeneralEdits.get('1') || {}) } }]; }
function refreshScenarioRelations() {
  state.scenario.forceByKey = new Map(state.scenario.forces.map(row => [row.forceKey, row]));
  state.scenario.siteByKey = new Map(); state.scenario.entityByKey = new Map();
}
function buildSiteIndex() { return null; }
function renderSitePicker() {}
function renderDomainManagers() {}
function refreshSide() {}
function refreshPatches() {}
function scheduleDraw() {}
"""
        checks = """
const payload = {
  format: 'san-editor-patch-v1', stage: 'stage01', width: 1, height: 1,
  changes: [{ x: 0, y: 0, field: 'terrain_tag', before: 1, after: 9 }],
  scenarioChanges: [{ kind: 'force', key: 'force:0', op: 'update', field: 'force_name', before: '旧势力', after: '新势力' }],
  gateChanges: [{ kind: 'gate', key: 'gate:0', op: 'update', field: 'doorX', before: 10, after: 11 }],
  historyChanges: [{ kind: 'history', key: '1', field: '加入年', before: '190', after: '191' }],
  stageIniGeneralChanges: [{ kind: 'stageIniGeneral', key: '1', field: '统御力', before: '70', after: '80' }]
};
payload.scenarioChanges.push(
  { kind: 'site', key: 'site:new:83', op: 'add', after: { siteKey: 'site:new:83', coord_y: 510, governor: 0 } },
  { kind: 'site', key: 'site:new:83', op: 'update', field: 'coord_y', before: 521, after: 520 },
  { kind: 'site', key: 'site:new:83', op: 'update', field: 'governor', before: 5, after: 278 }
);
applyImportedPatchPayload(payload, 'all_patch.json');
if (state.meta.records[0][0] !== 9) throw new Error('地图 Patch 未恢复');
if (state.scenario.forces[0].force_name !== '新势力') throw new Error('场景 Patch 未恢复');
if (state.scenario.sites[0].coord_y !== 520 || state.scenario.sites[0].governor !== 278) throw new Error('新增场景对象的连续更新未合并');
if (state.gates[0].doorX !== 11) throw new Error('城门 Patch 未恢复');
if (state.historyEdits.get('1').加入年 !== '191') throw new Error('History Patch 未恢复');
if (state.stageIniGeneralEdits.get('1').统御力 !== '80') throw new Error('ini Patch 未恢复');
applyImportedPatchPayload(payload, 'all_patch.json');
const conflict = { ...payload, changes: [{ x: 0, y: 0, field: 'terrain_tag', before: 1, after: 8 }], scenarioChanges: [{ kind: 'force', key: 'force:0', op: 'update', field: 'force_name', before: '新势力', after: '不应写入' }] };
let rejected = false;
try { applyImportedPatchPayload(conflict, 'conflict.json'); } catch (err) { rejected = String(err.message).includes('地图冲突'); }
if (!rejected) throw new Error('冲突 Patch 未被拒绝');
if (state.meta.records[0][0] !== 9 || state.scenario.forces[0].force_name !== '新势力') throw new Error('冲突后产生了部分修改');
"""
        self.run_node(harness + functions + checks)

if __name__ == "__main__":
    unittest.main()
