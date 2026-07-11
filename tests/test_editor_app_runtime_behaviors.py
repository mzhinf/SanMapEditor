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

if __name__ == "__main__":
    unittest.main()
