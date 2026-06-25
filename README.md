# 三国霸业地图恢复与编辑器工具

本仓库用于逆向《三国霸业》PC 版的地图、资源容器与关卡语义文件，并在此基础上构建可回写的地图编辑器。

当前已经完成两条主线：

1. `stageNN.m` + `kingdom.cel/.atr` 的真实地图渲染与编辑器原型。
2. `stage.ini` 的二进制拆解、Excel 导出，以及字节级 round-trip 回写。

原始游戏文件保留在 [三国霸业](</H:/Workstation/san/三国霸业/>)，分析产物默认输出到 `derived/` 或 `outputs/`。

## 当前结论

- `stageNN.m` 是地图主表，每个 cell 固定 16 字节，不只是 `acwx/acwy/acwz` 三层索引。
- `kingdom.cel/.atr` 提供地图图形资源，其中：
  - `acwx` 是基础地形层。
  - `acwy` 是叠加/过渡层。
  - `acwz` 是建筑/物件层。
- `stage.ini` 不是文本 ini，而是全局二进制母表：
  - 文件头：8 字节
  - 主表：`277 * 224` 字节
  - 尾表：`174 * 76` 字节
- `.stg` 当前按“8 字节头 + 76 字节原始记录链 + 可选尾字节”处理；`stage01.stg` 已按原始顺序导出 2502 条记录，尾部 48 字节。
- `stage01.stg` 更像“剧本名 -> 势力块 -> 城池块 -> 城内武将/士兵/附属记录”的顺序脚本；当前层级导出可得到 10 个势力/特殊块、38 个城池块。
- `city_92_family` 仍是最稳的城市字段子集：20 条记录的 `city_id / city_size` 与 `castle.txt` 20/20 对齐；但完整城池块还会落在 `text_mixed_record`、`city_or_structure` 等偏移变体中。
- `uft8-game-txt/` 中已有 5 类 txt 与 `stage.ini` 建立了稳定关联：
  - `general.txt`
  - `castle.txt`
  - `magic.txt`
  - `soldier.txt`
  - `History.txt`（仅辅助，不参与自动回写）

更详细的格式说明见：

- [格式笔记（中文）](docs/FORMAT_NOTES.zh.md)
- [文档维护约定](docs/DOC_WORKFLOW.zh.md)

## 环境

推荐使用 Codex bundled Python：

```powershell
$py = 'C:\Users\mzhinf\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

## 常用脚本

### 地图渲染与编辑器

渲染真实地图：

```powershell
& $py tools/render_m_cel_map.py . --stage stage11 --layout stagger --layers xyz --crop 93 57 1642 1684 --scale 2
```

导出编辑器 bundle：

```powershell
& $py tools/export_editor_bundle.py . --stage stage11
```

导出全部已发现关卡：

```powershell
& $py tools/export_editor_bundle.py . --all
```

启动本地静态服务：

```powershell
& $py -m http.server 8787 --bind 127.0.0.1 --directory derived/editor
```

浏览器入口：

- [stage11 编辑器](http://127.0.0.1:8787/stage11/editor.html)
- [编辑器索引](http://127.0.0.1:8787/index.html)

### `stage.ini` 结构导出

导出 `stage.ini` 结构化 JSON：

```powershell
& $py tools/export_stage_ini_tables.py .
```

从 JSON 回写 `stage.ini`：

```powershell
& $py tools/build_stage_ini.py derived/stage_ini_analysis/stage_ini_tables.json --compare-with 三国霸业\stage.ini --out derived/stage_ini_analysis/stage_roundtrip.ini
```

### `stage.ini` 与 Excel 互转

导出两份工作簿：

```powershell
& $py tools/export_stage_ini_txt_workbook.py .
```

产物：

- `outputs/stage_ini_txt_analysis/stage_ini_linked_tables.xlsx`
- `outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx`

说明：

- `linked_tables` 是分析版，保留定位与调试列。
- `conversion_tables` 是纯转换版，只保留 `row_id`、`title` 和业务字段，适合实际编辑。

把工作簿读回 JSON：

```powershell
& $py tools/import_stage_ini_txt_workbook.py --input outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx --out derived/stage_ini_txt_analysis/stage_ini_conversion_import.json
```

从 Excel 回写新的 `stage.ini`：

```powershell
& $py tools/build_stage_ini_from_txt_workbook.py outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx . --out derived/stage_ini_txt_analysis/stage_ini_from_conversion_workbook.ini --compare-with 三国霸业\stage.ini
```

当前已经验证：未修改的 `stage_ini_conversion_tables.xlsx` 可回写出与原始 `stage.ini` 字节完全一致的文件。

### `.stg` Phase 7 对照导出

导出单个关卡的 `.stg` 原始记录链：

```powershell
& $py tools/export_stg_raw_chain.py . --stage stage01
```

产物：

- `derived/sidecar_analysis/raw_chain/stage01/stg_raw_chain.json`
- `derived/sidecar_analysis/raw_chain/stage01/stg_raw_chain.csv`

导出按原始顺序恢复的势力/城池层级：

```powershell
& $py tools/export_stg_hierarchy.py . --stage stage01
```

产物：

- `derived/sidecar_analysis/hierarchy/stage01/stg_hierarchy.json`
- `derived/sidecar_analysis/hierarchy/stage01/stg_hierarchy_records.csv`
- `derived/sidecar_analysis/hierarchy/stage01/stg_force_city_summary.csv`

用途：

- 将 `.stg` 看成顺序记录链，恢复“势力 -> 城池 -> 武将/士兵”的可读结构。
- 用 `castle.txt`、`History.txt` 交叉验证城池名、武将名与 id 空间。
- 避免把旧脚本的 `slot/context_owner_slot_consensus` 当成已确认 owner 字段；它们只保留为历史排查线索。

导出单个关卡的旧版字段对照表：

```powershell
& $py tools/export_stg_phase7_links.py . --stage stage01
```

产物：

- `derived/sidecar_analysis/phase7/stage01/stg_phase7_links.json`
- `derived/sidecar_analysis/phase7/stage01/general_rows.csv`
- `derived/sidecar_analysis/phase7/stage01/faction_rows.csv`
- `derived/sidecar_analysis/phase7/stage01/city_rows.csv`

用途：继续检查 `224 / 96 / 92` 锚点归一化后的字段候选值。

## 文档维护约定

从现在开始，本项目按固定规则维护文档，不再“代码先走、文档补不补看情况”：

1. 二进制结构变化：同步更新 [docs/FORMAT_NOTES.zh.md](/H:/Workstation/san/docs/FORMAT_NOTES.zh.md)。
2. 脚本用法变化：同步更新 [README.md](/H:/Workstation/san/README.md)。
3. 阶段目标变化：同步更新 [task_plan.md](/H:/Workstation/san/task_plan.md)。
4. 新结论或新证据：同步更新 [findings.md](/H:/Workstation/san/findings.md)。
5. 本次做了什么、怎么验证：同步更新 [progress.md](/H:/Workstation/san/progress.md)。
6. 提交 git 前，至少检查一次“文档是否仍能指导新人复现当前结果”。

完整流程见 [docs/DOC_WORKFLOW.zh.md](/H:/Workstation/san/docs/DOC_WORKFLOW.zh.md)。

## 下一步计划

当前最值得做的 3 件事：

1. 继续逆向 `stageNN.stg`，把层级块写回能力、直接 owner 字段、士兵数量/兵种字段逐步拆清。
2. 继续逆向 `stageNN.evt`，确认事件记录如何引用地图坐标、对象和全局 id。
3. 从 `Emperor.exe` 继续确认 `.s/.x` 的生成和读取路径，把小地图/缓存写回补齐到编辑器链路。
