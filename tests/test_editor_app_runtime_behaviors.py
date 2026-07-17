from __future__ import annotations

import json
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

    def test_web_title_reads_release_metadata(self) -> None:
        """验证网页从发布元数据读取标题，缺失时才退回关卡名。"""

        source = script_source()
        functions = function_range(source, "appTitle", "fieldIndex")
        harness = """
const state = { releaseInfo: { app_title: '三国霸业地图编辑器 2.0' }, meta: { stage: 'stage01' } };
async function fetch(path, options) {
  if (path !== '../release-info.json' || options.cache !== 'no-store') throw new Error('发布元数据路径错误');
  return { ok: true, json: async () => ({ app_title: '测试标题' }) };
}
"""
        checks = """
(async () => {
  if (appTitle() !== '三国霸业地图编辑器 2.0') throw new Error('未使用发布标题');
  const info = await loadReleaseInfo();
  if (info.app_title !== '测试标题') throw new Error('未读取 release-info.json');
  state.releaseInfo = {};
  if (appTitle() !== 'stage01') throw new Error('缺少标题时未回退关卡名');
})().catch(error => { console.error(error); process.exit(1); });
"""
        self.run_node(harness + functions + checks)

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
function deriveMinimapColorChanges(changes) { return changes; }
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

    def test_legacy_bundle_restores_editable_minimap_color(self) -> None:
        """验证上一版只读元数据载入后会恢复颜色的 Raw 编辑入口。"""

        source = script_source()
        functions = function_range(source, "normalizeMeta", "getFieldMeta")
        harness = """
const EXPORT_FIELD_ORDER = ['acwx', 'acwy', 'acwz', 'minimap_color'];
const RESOURCE_LAYER_OPTIONS = ['acwx', 'acwy', 'acwz'];
const POINT_LAYER_OPTIONS = [];
const defaults = [
  { name: 'acwx', editable: true, reserved: false },
  { name: 'acwy', editable: true, reserved: false },
  { name: 'acwz', editable: true, reserved: false },
  { name: 'minimap_color', editable: true, reserved: false, derived: true }
];
function canonicalFieldName(value) { return value; }
function defaultFieldMetaByName() { return new Map(defaults.map(entry => [entry.name, entry])); }
function normalizeSidecars(value) { return value || {}; }
function normalizeSiteLinks(value) { return value || {}; }
"""
        checks = """
const normalized = normalizeMeta({
  fields: EXPORT_FIELD_ORDER,
  fieldMeta: [{ name: 'minimap_color', editable: false, reserved: false }],
  editableRecordFields: ['acwx', 'acwy', 'acwz'],
  records: [[1, 2, 3, 10]]
});
const colorMeta = normalized.fieldMeta.find(entry => entry.name === 'minimap_color');
if (!colorMeta.editable || !normalized.editableRecordFields.includes('minimap_color')) throw new Error('旧 bundle 未恢复颜色编辑入口');
"""
        self.run_node(harness + functions + checks)

    def test_xyz_change_derives_minimap_color_in_same_transaction(self) -> None:
        """验证 xyz 修改自动派生颜色，并与源字段共同撤销和重做。"""

        source = script_source()
        start = source.index("const MINIMAP_PREDICTION_LEVELS")
        end = source.index("function resetSelectedLayerChange", start)
        functions = source[start:end]
        harness = """
const fields = ['acwx', 'acwy', 'acwz', 'minimap_color'];
const records = [[1, 2, 3, 10], [1, 2, 4, 12], [1, 2, 4, 12], [9, 9, 7, 30], [8, 8, 7, 30]];
const state = {
  meta: { width: 5, height: 1, fields, records: records.map(row => row.slice()), editableLayers: ['acwx', 'acwy', 'acwz'] },
  originalRecords: records.map(row => row.slice()), undoStack: [], redoStack: [], patches: new Map(), recentMapPatchKeys: [],
  minimapColorPredictor: null
};
function canonicalFieldName(value) { return value; }
function fieldIndex(field) { return fields.indexOf(field); }
function recordAt(cell) { return state.meta.records[cell.row * state.meta.width + cell.col]; }
function updateLayerStats() {}
function syncPatchFor() {}
function refreshAfterRecordEdit() {}
"""
        checks = """
state.minimapColorPredictor = buildMinimapColorPredictor(state.originalRecords, fields);
const detail = state.minimapColorPredictor.predictDetail(1, 99, 4);
if (detail.level !== 'xz' || detail.color !== 12) throw new Error('xz 回退错误');
const zPriority = state.minimapColorPredictor.predictDetail(1, 2, 7);
if (zPriority.level !== 'z' || zPriority.color !== 30) throw new Error('z 优先级错误');
if (!applyChangeSet([{ x: 0, y: 0, field: 'acwz', after: 4 }])) throw new Error('xyz 修改未生效');
if (state.meta.records[0].join(',') !== '1,2,4,12' || state.undoStack[0].length !== 2) throw new Error('颜色未并入同一事务');
undoLastEdit();
if (state.meta.records[0].join(',') !== '1,2,3,10') throw new Error('组合撤销错误');
redoLastEdit();
if (state.meta.records[0].join(',') !== '1,2,4,12') throw new Error('组合重做错误');
if (!applyChangeSet([{ x: 0, y: 0, field: 'minimap_color', after: 99 }]) || state.meta.records[0][3] !== 99) throw new Error('手工颜色修正未生效');
if (!applyChangeSet([{ x: 0, y: 0, field: 'acwz', after: 3 }, { x: 0, y: 0, field: 'minimap_color', after: 77 }])) throw new Error('组合手工修正未生效');
if (state.meta.records[0].join(',') !== '1,2,3,77') throw new Error('手工颜色未覆盖自动推导');
"""
        self.run_node(harness + functions + checks)

    def test_new_site_uses_stage_ini_fields_and_becomes_active(self) -> None:
        """验证新增据点使用固定初值、清零其他母表字段并立即选中。"""

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
const expected = { castle_scale: 1, population: 1200, gold: 3000, food: 7500, standby_soldier: 0, develop: 40, commerce: 40, security: 50, governor: 0 };
for (const [field, value] of Object.entries(expected)) {
  if (site[field] !== value) throw new Error(`新增据点默认值错误：${field}`);
}
if (site.house_attr !== 0 || site.coord_x !== 40 || site.coord_y !== 50 || site.stageIniRowKey !== '2') throw new Error('据点类型、坐标或母表行错误');
if (site.stageIniValues.develop_cap !== '0' || site.stageIniValues.commerce_cap !== '0' || site.stageIniValues.security_cap !== '0' || site.stageIniValues.officer_slot !== '0') throw new Error('未指定的母表字段没有清零');
addScenarioSite(force.forceKey);
const appended = state.scenario.sites[1];
if (appended.city_index !== 3 || appended.stageIniRowKey !== '3') throw new Error('新增城池的都市索引与母表行号未独立递增');
for (const [field, value] of Object.entries(expected)) {
  if (appended[field] !== value) throw new Error(`追加据点默认值错误：${field}`);
}
if (appended.stageIniValues.develop_cap !== '0' || appended.stageIniValues.commerce_cap !== '0' || appended.stageIniValues.security_cap !== '0' || appended.stageIniValues.officer_slot !== '0') throw new Error('追加据点继承了模板保留字段');
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
const general = {
  stageIniGeneralKey: 'stageini:88', stageIniRowKey: '88', name: '测试武将', person_id: 88, portrait_id: 3,
  level: 1, troop_count: 50, command: 60, martial_force: 60, intellect: 60, loyalty: 100,
  max_troop_count: 50, max_martial_force: 60, max_intellect: 60
};
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
const added = state.scenario.entities[0];
if (added.person_id !== 88 || siteRefreshes !== 1) throw new Error('据点 UI 未同步刷新');
if (added.level !== 1 || added.troop_count !== 50 || added.command !== 60 || added.martial_force !== 60 || added.intellect !== 60 || added.loyalty !== 100) throw new Error('新 Entity 未继承武将默认属性');
if (added.max_troop_count !== 50 || added.max_martial_force !== 60 || added.max_intellect !== 60) throw new Error('新 Entity 未继承最大属性');
if ('stageIniValues' in state.scenario.entities[0] || 'stageIniGeneralKey' in state.scenario.entities[0]) throw new Error('母表 UI 元数据泄漏到 STG Entity');
"""
        self.run_node(harness + functions + checks)

    def test_general_manager_creates_master_row_without_site_membership(self) -> None:
        """验证武将管理新增只创建母表行，不写入据点 Entity。"""

        source = script_source()
        functions = function_range(source, "newGeneralDefaults", "scenarioFieldLabel")
        harness = """
const headers = ['row_id', 'title', '人物編號', '頭像編號', '統御力', '等級', '帶兵數', '武力', '智力', '忠誠值', '最大帶兵數', '最大武力', '最大智力'];
const state = {
  newStageIniGenerals: [], activeEntityKey: 'old', activeHistoryGeneralKey: '',
  stageIniGeneralPatches: new Map(), scenario: { entities: [] }
};
function stageIniGeneralSheet() { return { headers }; }
function stageIniGeneralRows() { return [{ person_id: 272 }]; }
function stageIniGeneralFieldHeaders() {
  return {
    person_id: '人物編號', portrait_id: '頭像編號', command: '統御力', level: '等級',
    troop_count: '帶兵數', martial_force: '武力', intellect: '智力', loyalty: '忠誠值',
    max_troop_count: '最大帶兵數', max_martial_force: '最大武力', max_intellect: '最大智力'
  };
}
function schedulePatchRefresh() {}
function ensureHistoryRow() {}
function renderDomainManagers() {}
"""
        checks = """
addScenarioEntity();
if (state.newStageIniGenerals.length !== 1) throw new Error('未创建 stage.ini 武将');
if (state.scenario.entities.length !== 0) throw new Error('错误加入了据点 Entity');
const general = state.newStageIniGenerals[0];
if (state.activeHistoryGeneralKey !== 'stageini:273') throw new Error('新武将选中状态错误');
const expectedFields = {
  level: 1, troop_count: 50, command: 60, martial_force: 60, intellect: 60, loyalty: 100,
  max_troop_count: 50, max_martial_force: 60, max_intellect: 60
};
const headersByField = stageIniGeneralFieldHeaders();
for (const [field, expected] of Object.entries(expectedFields)) {
  if (general[field] !== expected) throw new Error(`新武将属性默认值错误：${field}`);
  if (general.stageIniValues[headersByField[field]] !== String(expected)) throw new Error(`新武将母表默认值错误：${field}`);
}
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

    def test_new_gate_rejects_odd_y(self) -> None:
        """验证奇数 Y 坐标会提示并阻止新增城门。"""

        source = script_source()
        functions = function_range(source, "gateKey", "deleteSiteGate")
        harness = """
const state = {
  gates: [], selected: { col: 30, row: 41 }, gatePatches: new Map(),
  meta: { siteLinks: {} }, scenario: null
};
const alerts = [];
let refreshes = 0;
const window = { alert: message => alerts.push(String(message)) };
function dorRecordKey(group, doorIndex) { return String(group) + ':' + String(doorIndex); }
function schedulePatchRefresh() {}
function buildSiteIndex() { return null; }
function renderSitePicker() { refreshes += 1; }
function scheduleDraw() {}
"""
        checks = """
addSiteGate({ siteKey: 'site:1', cityName: '测试城', forceIndex: 2, mapX: 50, mapY: 60 });
if (state.gates.length !== 0 || state.gatePatches.size !== 0 || refreshes !== 0) throw new Error('奇数 Y 仍新增了城门或产生副作用');
if (alerts.length !== 1 || !alerts[0].includes('Y 坐标 41 为奇数') || !alerts[0].includes('只能保存偶数 Y 坐标')) throw new Error('奇数 Y 提示不明确');
"""
        self.run_node(harness + functions + checks)

    def test_gate_edit_rejects_odd_y(self) -> None:
        """验证直接编辑城门 Y 为奇数时会提示且不登记 Patch。"""

        source = script_source()
        functions = function_range(source, "gateKey", "deleteSiteGate")
        harness = """
const gate = { gateKey: 'gate:old', gateIndex: 5, group: 2, doorIndex: 3, doorX: 10, doorY: 92, deleted: false };
const state = { gates: [gate], gatePatches: new Map(), meta: { siteLinks: {} }, scenario: null };
const alerts = [];
let refreshes = 0;
const window = { alert: message => alerts.push(String(message)) };
function dorRecordKey(group, doorIndex) { return String(group) + ':' + String(doorIndex); }
function schedulePatchRefresh() {}
function buildSiteIndex() { return null; }
function renderSitePicker() { refreshes += 1; }
function scheduleDraw() {}
"""
        checks = """
if (updateGateField(gate.gateKey, 'doorY', '93', true) !== false) throw new Error('奇数 Y 未被拒绝');
if (gate.doorY !== 92 || state.gatePatches.size !== 0 || refreshes !== 0) throw new Error('奇数 Y 修改产生了副作用');
if (alerts.length !== 1 || !alerts[0].includes('Y 坐标 93 为奇数') || !alerts[0].includes('只能保存偶数 Y 坐标')) throw new Error('直接修改的提示不明确');
if (updateGateField(gate.gateKey, 'doorY', '94', true) !== true || gate.doorY !== 94 || state.gatePatches.size !== 1 || refreshes !== 1) throw new Error('偶数 Y 修改未正常生效');
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

    def test_isometric_selection_roundtrips_and_supports_set_operations(self) -> None:
        """验证等距坐标可逆，并按菱形网格执行替换、添加和扣除。"""

        source = script_source()
        functions = (
            function_range(source, "cellToIsoGrid", "rememberSelectedCell")
            + function_range(source, "applyIsoSelection", "selectCell")
        )
        harness = """
const state = {
  meta: { width: 10, height: 10 },
  selected: null,
  selectionAnchor: null,
  selectedCells: new Map()
};
function cellKey(cell) { return `${cell.col},${cell.row}`; }
function selectedCellList() { return [...state.selectedCells.values()]; }
"""
        checks = """
for (let row = 0; row < 10; row++) {
  for (let col = 0; col < 10; col++) {
    const restored = isoGridToCell(cellToIsoGrid({ col, row }));
    if (restored.col !== col || restored.row !== row) throw new Error(`等距坐标不可逆：${col},${row}`);
  }
}
const anchor = { col: 3, row: 2 };
const end = { col: 3, row: 4 };
const cells = isoCellsBetween(anchor, end);
const keys = cells.map(cellKey).sort().join(';');
if (keys !== '2,3;3,2;3,3;3,4') throw new Error(`菱形选区错误：${keys}`);
const bounds = isoSelectionBounds(cells);
if (bounds.width !== 2 || bounds.height !== 2 || bounds.count !== 4) throw new Error('等距范围尺寸错误');
applyIsoSelection(anchor, end, 'replace');
if (state.selectedCells.size !== 4 || cellKey(state.selectionAnchor) !== '3,2') throw new Error('替换选区错误');
applyIsoSelection({ col: 0, row: 0 }, { col: 0, row: 0 }, 'add');
if (state.selectedCells.size !== 5) throw new Error('添加选区错误');
applyIsoSelection(anchor, { col: 2, row: 3 }, 'subtract');
if (state.selectedCells.size !== 3 || !state.selectedCells.has('0,0')) throw new Error('扣除选区错误');
"""
        self.run_node(harness + functions + checks)

    def test_isometric_drag_cancel_restores_previous_selection(self) -> None:
        """验证拖动模式优先级和 Esc 取消使用的事务回滚。"""

        source = script_source()
        functions = (
            function_range(source, "cellToIsoGrid", "rememberSelectedCell")
            + function_range(source, "applyIsoSelection", "selectCell")
            + function_range(source, "isoSelectionMode", "resizeCanvas")
        )
        harness = """
const base = { col: 1, row: 1 };
const state = {
  meta: { width: 8, height: 8 },
  selected: base,
  selectionAnchor: base,
  selectedCells: new Map([['1,1', base]]),
  selectionDrag: null
};
let released = 0;
const canvas = {
  setPointerCapture() {},
  hasPointerCapture() { return true; },
  releasePointerCapture() { released += 1; }
};
const els = { selectionInfo: null };
function cellKey(cell) { return `${cell.col},${cell.row}`; }
function selectedCellList() { return [...state.selectedCells.values()]; }
function updateHud() {}
function scheduleDraw() {}
function refreshSide() {}
function refreshPatches() {}
function refreshCompositeList() {}
function syncActiveSiteFromCell() {}
function clientToWorld() { return { x: 0, y: 0 }; }
function worldToCell() { return base; }
function describeRegion() { return ''; }
"""
        checks = """
if (isoSelectionMode({ altKey: true, ctrlKey: true }) !== 'subtract') throw new Error('扣除模式优先级错误');
if (isoSelectionMode({ altKey: false, ctrlKey: true }) !== 'add') throw new Error('添加模式错误');
if (isoSelectionMode({ altKey: false, ctrlKey: false }) !== 'replace') throw new Error('替换模式错误');
startIsoSelectionDrag({ pointerId: 7, altKey: true, ctrlKey: false }, base);
if (state.selectedCells.size !== 0 || state.selectionDrag.mode !== 'subtract') throw new Error('扣除预览未生效');
if (!stopIsoSelectionDrag(null, true)) throw new Error('取消拖动失败');
if (state.selectedCells.size !== 1 || !state.selectedCells.has('1,1')) throw new Error('未恢复拖动前选区');
if (state.selected !== base || state.selectionAnchor !== base || released !== 1) throw new Error('未恢复锚点或释放指针');
"""
        self.run_node(harness + functions + checks)

    def test_isometric_snapshot_keeps_shape_across_row_parity(self) -> None:
        """验证等距快照从偶数行粘贴到奇数行时保持 du/dv 轮廓。"""

        source = script_source()
        functions = (
            function_range(source, "cellToIsoGrid", "rememberSelectedCell")
            + function_range(source, "regionCellHasContent", "refreshCompositeList")
        )
        harness = """
const fields = ['value'];
const records = Array.from({ length: 100 }, (_, index) => [index]);
const sourceCells = [{ col: 3, row: 2 }, { col: 2, row: 3 }, { col: 3, row: 3 }, { col: 3, row: 4 }];
const state = {
  regionCopyMode: 'full',
  meta: { width: 10, height: 10, fields, editableRecordFields: fields, records },
  selected: { col: 3, row: 4 },
  selectionAnchor: { col: 3, row: 2 },
  selectedCells: new Map(sourceCells.map(cell => [`${cell.col},${cell.row}`, cell]))
};
let applied = [];
function canonicalFieldName(value) { return value; }
function fieldIndex() { return 0; }
function cellKey(cell) { return `${cell.col},${cell.row}`; }
function selectedCellList() { return [...state.selectedCells.values()]; }
function recordAt(cell) { return records[cell.row * 10 + cell.col]; }
function applyChangeSet(changes) { applied = changes; return changes.length > 0; }
function refreshCompositeList() {}
function scheduleDraw() {}
"""
        checks = """
const snapshot = captureRegionSnapshot();
if (snapshot.mode !== 'iso-cells-v2' || snapshot.cells.length !== 4) throw new Error('未生成等距快照');
const target = { col: 6, row: 3 };
state.selected = target;
state.selectionAnchor = target;
if (!pasteRegionSnapshot(snapshot)) throw new Error('等距快照未粘贴');
const actual = [...state.selectedCells.keys()].sort().join(';');
if (actual !== '6,3;6,4;6,5;7,4') throw new Error(`跨奇偶行形状错误：${actual}`);
if (applied.length !== 4 || cellKey(state.selectionAnchor) !== '6,3') throw new Error('粘贴锚点或变更数量错误');
const targetPoint = cellToIsoGrid(target);
for (const cell of snapshot.cells) {
  const restored = isoGridToCell({ u: targetPoint.u + cell.du, v: targetPoint.v + cell.dv });
  if (!state.selectedCells.has(cellKey(restored))) throw new Error('du/dv 相对位置未保持');
}
"""
        self.run_node(harness + functions + checks)

    def test_full_copy_captures_every_selected_cell_and_cut_clears_non_base_fields(self) -> None:
        """验证全复制保留可手工修正的小地图颜色，剪切时不直接清零颜色。"""

        source = script_source()
        functions = function_range(source, "cellToIsoGrid", "rememberSelectedCell") + function_range(source, "regionCellHasContent", "refreshCompositeList")
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
function cellKey(cell) { return `${cell.col},${cell.row}`; }
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
if (snapshot.fields.join(',') !== fields.join(',')) throw new Error('全复制未保留手工颜色');
if (state.meta.records[0].join(',') !== '10,-1,-1,0,0,0,0,60') throw new Error('全复制剪切未清理到底层地表');
if (state.meta.records[1].join(',') !== '11,-1,-1,0,0,0,0,61') throw new Error('纯底层 Cell 未参与全复制剪切');
if (appliedBatches !== 1) throw new Error('区域剪切未作为单次撤销事务提交');
"""
        self.run_node(harness + functions + checks)

    def test_non_base_copy_filters_cells_and_excludes_base_and_minimap_fields(self) -> None:
        """验证非底层复制按六个内容字段筛选，并排除 acwx 与 minimap_color。"""

        source = script_source()
        functions = function_range(source, "cellToIsoGrid", "rememberSelectedCell") + function_range(source, "regionCellHasContent", "refreshCompositeList")
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
function cellKey(cell) { return `${cell.col},${cell.row}`; }
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
if (snapshot.fields.includes('acwx') || snapshot.fields.includes('minimap_color')) throw new Error('非底层复制包含了排除字段');
if (snapshot.cells[0].record.join(',') !== '20,30,1,2,3,4') throw new Error('非底层快照字段顺序错误');
if (state.meta.records[0].join(',') !== '10,-1,-1,0,0,0,0,60') throw new Error('非底层剪切错误清除了排除字段');
if (state.meta.records[2].join(',') !== '12,-1,-1,0,0,0,0,62') throw new Error('无内容 Cell 不应参与非底层剪切');
"""
        self.run_node(harness + functions + checks)

    def test_region_commands_use_current_copy_mode(self) -> None:
        """验证按钮与快捷键共用命令函数，并读取当前复制模式。"""

        source = script_source()
        start = source.index("function copySelectedRegion")
        end = source.index("els.copyRegion.addEventListener", start)
        functions = source[start:end]
        harness = """
const state = { regionCopyMode: 'non-base', regionClipboard: null, activeCompositeId: 'old', selected: { col: 4, row: 5 }, compositeObjects: [] };
const els = { status: { textContent: '' } };
let copyMode = ''; let cutMode = ''; let refreshes = 0; let pasted = null;
function captureRegionSnapshot() { copyMode = state.regionCopyMode; return { copyMode, count: 2 }; }
function cutRegionSnapshot() { cutMode = state.regionCopyMode; return { copyMode: cutMode, count: 3 }; }
function refreshCompositeList() { refreshes += 1; }
function pasteRegionSnapshot(snapshot) { pasted = snapshot; return true; }
"""
        checks = """
if (!copySelectedRegion() || copyMode !== 'non-base') throw new Error('复制命令未使用当前模式');
if (!cutSelectedRegion() || cutMode !== 'non-base') throw new Error('剪切命令未使用当前模式');
if (!pasteSelectedRegion() || pasted !== state.regionClipboard) throw new Error('粘贴命令未使用当前区域剪贴板');
if (refreshes !== 2 || state.activeCompositeId !== null) throw new Error('区域命令未同步剪贴板状态');
"""
        self.run_node(harness + functions + checks)

    def test_edited_outline_respects_overlay_toggle(self) -> None:
        """验证已编辑框可由数据叠加开关独立显示和隐藏。"""

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
if (strokes !== 0) throw new Error('关闭后仍显示已编辑框');
state.dataOverlayVisible.edited = true;
drawEditedCellOverlay();
if (strokes !== 2) throw new Error('开启后未显示全部已编辑框');
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
        """验证新增武将和城池按真实块流扩展 stage.ini。"""

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
    format: 'stage-ini-block-stream-v1',
    general: {
      countOffset: 0, count: 1, insertOffset: 16, rowBytes: 12,
      recordPrefixValues: [8], titleBytes: 4, titleSuffix: [0],
      numericHeaders: ['人物编号'], recordSuffixHeaders: [], recordSuffixValues: []
    },
    castle: {
      countOffset: 16, count: 1, insertOffset: 40, rowBytes: 20,
      recordPrefixValues: [12, 0], titleBytes: 4, titleSuffix: [0],
      numericHeaders: ['都市索引'], recordSuffixHeaders: [], recordSuffixValues: [0]
    }
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
const original = new Uint8Array(42);
const originalView = new DataView(original.buffer);
originalView.setUint32(0, 1, true);
originalView.setUint32(4, 8, true);
originalView.setUint32(16, 1, true);
originalView.setUint32(20, 12, true);
originalView.setUint32(36, 0, true);
original[40] = 0xaa; original[41] = 0xbb;
const edited = buildEditedStageIniBytes(original);
const view = new DataView(edited.buffer);
if (edited.length !== 74 || view.getUint32(0, true) !== 2) throw new Error('主表块数或文件长度错误');
if (view.getUint32(16, true) !== 8 || edited[20] !== 71 || view.getUint32(24, true) !== 8) throw new Error('新增武将块错误');
if (view.getUint32(28, true) !== 2) throw new Error('城池计数未按武将插入量迁移');
if (view.getUint32(52, true) !== 12 || edited[60] !== 67 || view.getUint32(64, true) !== 9) throw new Error('新增城池双块错误');
if (view.getUint32(68, true) !== 0) throw new Error('新增城池缺少零长度次块');
if (edited[72] !== 0xaa || edited[73] !== 0xbb) throw new Error('新增记录破坏了后续原始块');
const sheets = cloneWorkbookSheets();
const sheetMap = new Map(sheets.map(sheet => [sheet.name, sheet]));
applyWorkbookRowPatch(sheetMap, site, 'site');
if (sheets[0].rows[0][0] !== '9' || sheets[0].rows[0][1] !== 'C' || sheets[0].rows[0][2] !== '9') throw new Error('新增城池工作簿标题或字段错误');
"""
        self.run_node(harness + functions + checks)
    def test_local_history_parser_restores_appended_general_record(self) -> None:
        """验证本地 History 表可恢复人物 278 并与本地 ini 属性合并。"""

        source_path = ROOT / "outputs" / "History.txt"
        if not source_path.exists():
            self.skipTest("缺少 outputs/History.txt")
        script = script_source()
        functions = function_range(script, "stgReadU32", "patchValuesEqual")
        harness = """
function historyIdHeader(headers) { return headers.find(header => ['編號', '编号', '人物編號', '人物编号'].includes(header)) || headers[0] || ''; }
function historyNameHeader(headers) { return headers.find(header => ['武將名', '武将名', '姓名', '名稱', '名称'].includes(header)) || headers[1] || ''; }
function stageIniGeneralRows() { return [{ person_id: 278, portrait_id: 12, command: 77, name: 'ini 名称', entity_name: 'ini 名称' }]; }
"""
        checks = f"""
const fs = require('fs');
const model = parseLocalHistoryBytes(new Uint8Array(fs.readFileSync({json.dumps(str(source_path))})));
if (model.rawHeaders[1] !== ' 編號' || model.headers[1] !== '編號') throw new Error('History 原始或规整表头错误');
const row = model.rows.find(item => item.rowKey === '278');
if (!row || row['武將名'] !== '劉飛羽' || row['加入年'] !== '189') throw new Error('劉飛羽 History 记录未恢复');
if (!model.big5CharMap['劉'] || !model.big5CharMap['羽']) throw new Error('History CP950 字符映射缺失');
const candidates = buildLocalHistoryGeneralRows(model);
if (candidates.length !== 1 || candidates[0].person_id !== 278 || candidates[0].name !== '劉飛羽' || candidates[0].command !== 77) throw new Error('History 与 ini 合并错误');
"""
        self.run_node(harness + functions + checks)

    def test_local_stage_ini_parser_restores_appended_general_rows(self) -> None:
        """验证本地母表解析可恢复新增武将字段、偏移和动态追加边界。"""

        source_path = ROOT / "data" / "game" / "stage.ini"
        if not source_path.exists():
            self.skipTest("缺少 data/game/stage.ini")
        from san_tools.codecs.stage_ini_codec import parse_stage_ini_block_layout
        from san_tools.map.export_editor_bundle import build_stage_ini_patch_model

        base = build_stage_ini_patch_model(ROOT, source_path.parent)
        slim = {
            "available": base["available"],
            "fieldMap": base["fieldMap"],
            "appendLayout": base["appendLayout"],
            "workbookSheets": [
                {"name": sheet["name"], "headers": sheet["headers"], "rows": []}
                for sheet in base["workbookSheets"]
            ],
        }
        layout = parse_stage_ini_block_layout(source_path.read_bytes())
        script = script_source()
        functions = function_range(script, "stgReadU32", "patchValuesEqual")
        output_path = ROOT / "outputs" / "stage.ini"
        output_layout = parse_stage_ini_block_layout(output_path.read_bytes()) if output_path.exists() else None
        checks = f"""
const fs = require('fs');
const baseModel = {json.dumps(slim, ensure_ascii=False)};
const parsed = parseLocalStageIniBytes(new Uint8Array(fs.readFileSync({json.dumps(str(source_path))})), baseModel);
if (parsed.appendLayout.general.count !== {layout['main_count']} || parsed.appendLayout.castle.count !== {layout['city_count']}) throw new Error('基准母表计数错误');
if (parsed.workbookSheets.find(sheet => sheet.name === 'general').rows[0][1] !== '劉備') throw new Error('母表标题解码错误');
if (!parsed.fieldLocations.general['1'] || parsed.appendLayout.general.insertOffset !== {layout['main_blocks_end']}) throw new Error('基准字段偏移错误');
"""
        if output_layout is not None:
            checks += f"""
const exported = parseLocalStageIniBytes(new Uint8Array(fs.readFileSync({json.dumps(str(output_path))})), baseModel);
const generalSheet = exported.workbookSheets.find(sheet => sheet.name === 'general');
const personColumn = generalSheet.headers.indexOf(exported.fieldMap.entity.fields.person_id);
const row278 = generalSheet.rows.find(row => String(row[0]) === '278');
if (!row278 || row278[1] !== '劉飛羽' || String(row278[personColumn]) !== '278') throw new Error('新增武将 ini 行未恢复');
if (!exported.fieldLocations.general['278']) throw new Error('新增武将字段偏移缺失');
if (exported.appendLayout.general.count !== {output_layout['main_count']} || exported.appendLayout.general.insertOffset !== {output_layout['main_blocks_end']}) throw new Error('新增母表追加边界错误');
if (exported.appendLayout.castle.count !== {output_layout['city_count']} || exported.appendLayout.castle.insertOffset !== {output_layout['city_records_end']}) throw new Error('新增城池追加边界错误');
"""
        self.run_node(functions + checks)

    def test_local_stg_parser_matches_python_field_model(self) -> None:
        """验证浏览器解析出的势力、据点和 Entity 顺序与字段模型一致。"""

        source_path = ROOT / "data" / "game" / "stage01.stg"
        if not source_path.exists():
            self.skipTest("缺少 data/game/stage01.stg")
        from san_tools.map.editor_model import StgFile

        stg = StgFile.from_file(source_path)
        site_names: list[str] = []
        entity_names: list[str] = []
        optional_names = (
            "optional_entity_27c", "optional_entity_280", "optional_entity_284",
            "optional_entity_288", "optional_entity_28c",
        )
        for force in stg.forces:
            for site in force.sites:
                site_names.append(site.site_name)
                entity_names.extend(entity.part2.body.entity_name for entity in site.entities)
                entity_names.extend(
                    entity.part2.body.entity_name
                    for name in optional_names
                    if (entity := getattr(site, name)) is not None
                )
        script = script_source()
        functions = function_range(script, "stgReadU32", "patchValuesEqual")
        harness = "const state = { meta: { stage: 'stage01' }, localScenarioFiles: new Map([['stg', { name: 'stage01.stg' }]]) };\n"
        checks = f"""
const fs = require('fs');
const bytes = new Uint8Array(fs.readFileSync({json.dumps(str(source_path))}));
const model = parseLocalStgBytes(bytes);
if (model.force_count !== {stg.force_count}) throw new Error('势力数量不一致');
if (JSON.stringify(model.sites.map(row => row.site_name)) !== JSON.stringify({json.dumps(site_names, ensure_ascii=False)})) throw new Error('据点名称或顺序不一致');
if (JSON.stringify(model.entities.map(row => row.entity_name)) !== JSON.stringify({json.dumps(entity_names, ensure_ascii=False)})) throw new Error('Entity 名称或顺序不一致');
if (!model.stgLayout || !model.sites.every(row => row.patchFields && row.stgLayout)) throw new Error('字段偏移或布局缺失');
"""
        self.run_node(harness + functions + checks)

    def test_project_snapshots_restore_ui_without_reapplying_binary_changes(self) -> None:
        """验证完整项目的 JSON 仅恢复界面状态，不再形成重复写回 Patch。"""

        source = script_source()
        start = source.index("function hydrateProjectSnapshotPayload")
        end = source.index("async function loadPatchFile", start)
        functions = source[start:end]
        harness = """
const state = {
  meta: { stage: 'stage01', siteLinks: {} },
  localScenarioFiles: new Map([['stg', {}], ['dor', {}], ['history', {}]]),
  scenario: { available: true, forces: [], sites: [], entities: [] }, scenarioPatches: new Map([['old', {}]]),
  gates: [], gatePatches: new Map([['old', {}]]),
  commonModel: { historyTable: { available: true, headers: ['編號', '武將名'], rawHeaders: ['編號', '武將名'], rows: [] } },
  historyEdits: new Map([['old', {}]]), newHistoryRows: [{ rowKey: 'old' }], deletedHistoryRowKeys: new Set(['old']), historyPatches: new Map([['old', {}]])
};
function normalizeScenarioModel(model) { return { ...model }; }
function normalizeGateRows(rows) { return rows.map(row => ({ ...row })); }
function refreshScenarioRelations() {}
function buildSiteIndex() { return null; }
function renderSitePicker() {}
function renderDomainManagers() {}
function refreshSide() {}
function refreshPatches() {}
function scheduleDraw() {}
"""
        checks = """
const scenario = { format: 'san-editor-scenario-patch-v1', stage: 'stage01', forces: [{ forceKey: 'force:0' }], sites: [{ siteKey: 'site:new', site_name: '晉都' }], entities: [{ entityKey: 'entity:new', person_id: 278 }] };
if (!hydrateProjectSnapshotPayload(scenario) || state.scenario.sites[0].site_name !== '晉都' || state.scenarioPatches.size) throw new Error('场景快照未正确恢复');
const dor = { format: 'san-editor-dor-patch-v1', stage: 'stage01', gates: [{ gateKey: 'gate:new:1', siteKey: 'site:new', doorIndex: 4 }] };
if (!hydrateProjectSnapshotPayload(dor) || state.gates.length !== 1 || state.gatePatches.size) throw new Error('城门快照被重复登记');
const history = { format: 'san-editor-history-patch-v1', stage: 'stage01', rows: [{ 編號: '278', 武將名: '劉飛羽', rowKey: '278' }] };
if (!hydrateProjectSnapshotPayload(history) || state.commonModel.historyTable.rows[0].rowKey !== '278' || state.historyPatches.size || state.newHistoryRows.length) throw new Error('History 快照被重复登记');
state.localScenarioFiles.delete('stg');
if (hydrateProjectSnapshotPayload(scenario)) throw new Error('缺少本地 STG 时不应把迁移 Patch 当快照');
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
