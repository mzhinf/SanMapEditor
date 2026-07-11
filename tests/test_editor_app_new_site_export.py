from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from san_tools.map.editor_model import StgFile
from san_tools.map.export_editor_bundle import build_editor_common_model, build_editor_scenario_model


ROOT = Path(__file__).resolve().parents[1]


class TestEditorNewSiteExport(unittest.TestCase):
    """验证新增城池触发的 .stg 对象流重写。"""

    def test_stage01_new_city_can_rebuild_stg(self) -> None:
        game_dir = ROOT / "三国霸业"
        source_stg = game_dir / "stage01.stg"
        if not source_stg.exists() or not shutil.which("node"):
            self.skipTest("缺少 stage01.stg 或 node")

        scenario = build_editor_scenario_model(game_dir, "stage01")
        common = build_editor_common_model(ROOT)
        html = (ROOT / "src" / "san_tools" / "map" / "editor_app.html").read_text(encoding="utf-8")
        source = re.search(r"<script>([\s\S]*)</script>", html).group(1)
        start = source.index("function mergedBig5CharMap")
        end = source.index("function buildHistoryPatchArtifact", start)
        functions = source[start:end]

        tmp_dir = ROOT / "derived" / "test_tmp" / "editor_runtime_new_site"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True)
        try:
            meta_path = tmp_dir / "meta.json"
            out_path = tmp_dir / "stage01-new.stg"
            script_path = tmp_dir / "rebuild.mjs"
            meta_path.write_text(json.dumps({"scenarioModel": scenario, "commonModel": common}, ensure_ascii=False), encoding="utf-8")
            script_path.write_text(self._node_harness(functions), encoding="utf-8")
            subprocess.run(
                ["node", str(script_path), str(meta_path), str(source_stg), str(out_path)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            rebuilt = StgFile.from_bytes(out_path.read_bytes())
            self.assertEqual(sum(len(force.sites) for force in rebuilt.forces), len(scenario["sites"]) + 1)
            added = next(site for force in rebuilt.forces for site in force.sites if site.site_name == "Site 84")
            runtime = added.part2.body
            self.assertEqual((runtime.runtime_coord_or_spawn_x_004, runtime.runtime_coord_or_spawn_y_008), (41, 30))
            self.assertEqual(runtime.site_kind_or_force_group_00c, 8)
            self.assertEqual(runtime.site_serial_010, 84)
            self.assertNotEqual(
                (runtime.runtime_coord_or_spawn_x_004, runtime.runtime_coord_or_spawn_y_008, runtime.site_serial_010),
                (187, 120, 1),
            )
            self.assertEqual(added.primary_entity_count, 1)
            general = added.entities[0]
            self.assertEqual(general.entity_name, "HUANG_SHENG")
            self.assertEqual(general.part1.body.runtime_force_or_ai_side_30, 8)
            self.assertEqual(general.part2.body.max_martial_force, 90)
            self.assertEqual(general.part2.body.max_intellect, 90)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def _node_harness(functions: str) -> str:
        """构造只运行 .stg 重写函数的 Node 测试环境。"""

        return """
import fs from 'node:fs';
const meta = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const original = new Uint8Array(fs.readFileSync(process.argv[3]));
const forces = meta.scenarioModel.forces.map(row => ({ ...row, deleted: false }));
const sites = meta.scenarioModel.sites.map(row => ({ ...row, deleted: false }));
const entities = meta.scenarioModel.entities.map(row => ({ ...row, deleted: false }));
const first = sites[0];
const added = {
  ...first,
  isNew: true,
  siteKey: 'site:new:test', siteIndex: sites.length, site_name: 'Site 84', city_index: 43,
  castle_scale: 1, population: 0, gold: 0, food: 0, coord_x: 40, coord_y: 50,
  parentForceKey: forces[7].forceKey, entityKeys: [], patchFields: {}, stgLayout: {}, deleted: false
};
sites.push(added);
const entityTemplate = entities.find(row => row.parentForceKey === forces[7].forceKey && Number(row.command || 0) > 0);
entities.push({
  ...entityTemplate,
  isNew: true,
  entityKey: 'entity:new:test', entityIndex: entities.length, entityGroup: 'primary',
  entity_name: 'HUANG_SHENG', person_id: 278, portrait_id: 10, command: 90,
  martial_force: 90, intellect: 90, max_martial_force: 90, max_intellect: 90,
  parentSiteKey: added.siteKey, parentForceKey: forces[7].forceKey,
  patchFields: {}, stgLayout: {}, deleted: false
});
const state = {
  meta,
  scenario: {
    forces, sites, entities,
    forceByKey: new Map(forces.map(row => [row.forceKey, row])),
    siteByKey: new Map(sites.map(row => [row.siteKey, row])),
    entityByKey: new Map(entities.map(row => [row.entityKey, row]))
  },
  scenarioPatches: new Map([['site:add', { kind: 'site', key: added.siteKey, op: 'add', field: '' }]])
};
function scenarioRows(kind) {
  const rows = kind === 'force' ? forces : kind === 'site' ? sites : entities;
  return rows.filter(row => !row.deleted);
}
""" + functions + "\nfs.writeFileSync(process.argv[4], buildEditedStgBytes(original));\n"


if __name__ == "__main__":
    unittest.main()
