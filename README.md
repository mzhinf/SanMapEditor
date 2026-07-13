# 三国霸业地图恢复与编辑器工具

本仓库用于逆向《三国霸业》PC 版的地图、资源容器与关卡语义文件，并在此基础上构建可回写的地图编辑器。

当前已经稳定落地的主线有两条：

1. `stageNN.m` + `kingdom.cel/.atr` 的真实地图渲染与浏览器编辑器原型。
2. `stage.ini` 与 `stageNN.stg` 的结构化导出、Excel 工作簿导出，以及字节级 round-trip 回写。

原始游戏文件位于 [三国霸业](./三国霸业/)。分析产物默认输出到 `derived/` 或 `outputs/`。

## 当前确认的能力

- `stageNN.m` 是地图主表，每个 cell 固定 16 字节，不只是 `acwx/acwy/acwz` 三层索引。
- `kingdom.cel/.atr` 提供真实地图 tile 资源：
  - `acwx`：基础地形层
  - `acwy`：叠加/过渡层
  - `acwz`：建筑/物件层
- `Emperor.exe` 已足够支撑当前稳定渲染：地图采用 staggered isometric 网格，最终渲染结果不是纯菱形大图。
- `stage.ini` 不是文本 ini，而是全局二进制母表，已具备 JSON / Excel / 二进制互转链路。
- `stage01.stg` 已能按原始记录顺序导出成层级表、城池状态表和工作簿，并支持安全回写。
- `.evt/.spr/.dor/.s/.x` 已有 sidecar 研究与保守写回脚本；其中 `.dor` 现已可按“分组 -> 城门记录”稳定导出完整数据。

更详细的格式说明见：

- [docs/FORMAT_NOTES.zh.md](docs/FORMAT_NOTES.zh.md)
- [docs/EDITOR_UI_V2_DESIGN.zh.md](docs/EDITOR_UI_V2_DESIGN.zh.md)
- [docs/DOC_WORKFLOW.zh.md](docs/DOC_WORKFLOW.zh.md)

## 目录说明

- `src/san_tools/`：正式维护的 Python 源码包。
- `tests/`：独立测试目录。
- `tools/`：兼容旧调用方式的包装层；新增编辑器页面与模板资源不再依赖这里。
- `docs/`：格式笔记与文档维护约定。
- `derived/`：中间分析结果、编辑器 bundle、图片导出。
- `outputs/`：工作簿与外部可读导出结果。
- `uft8-game-txt/`：从游戏文本批量转成 UTF-8 后的对照目录。

## Python 项目结构

`san-map-tools` 现在按标准 `src/` 布局维护：

- 根目录使用 `pyproject.toml` 管理打包配置
- 主要源码位于 `src/san_tools/`
- 测试集中在 `tests/`
- `tools/` 保留为兼容包装层，但推荐直接使用 `src/san_tools/` 下的正式入口
- 提供统一入口 `python -m tools` 与安装后的 `san-tools`

## 常用脚本

### 地图渲染与编辑器

渲染真实地图：

```powershell
& $py tools/render_m_cel_map.py . --stage stage11 --layout stagger --layers xyz --crop 93 57 1642 1684 --scale 2
```

导出编辑器 bundle：

```powershell
& $py src/san_tools/map/export_editor_bundle.py . --stage stage01 --out derived/editor
```

导出全部已发现关卡：

```powershell
& $py src/san_tools/map/export_editor_bundle.py . --all
```

导出的编辑页现在支持：

- `src/san_tools/map/editor_model.py` 统一承载严格对齐 `src/san_tools/ksy/m.ksy`、`dor.ksy`、`stg.ksy` 的字段级数据模型，只保留 `.m/.dor/.stg` 本身的结构与顺序解析器，不再混入 stage JSON、patch JSON 或多文件上下文抽象。
- 地图编辑器页面升级为 2.0 五区布局：顶部工具栏、左侧资源库、中央地图画布、右侧 Inspector、底部历史与状态面板。
- 左侧资源库支持地表层、叠加层、物件层、数据层色板切换，并保留资源窗口化渲染，避免一次性挂载全部 DOM。
- `.m` 记录字段按 `m.ksy` 的 `acwx/acwy/acwz/reserved0/terrain_tag/blocked/site_trigger/site_area/reserved1/minimap_color/reserved2` 统一口径展示；旧 `byte08..byte15` 仅作为兼容别名处理。
- 页面支持区域复制、剪切和合成对象，并提供“全复制”与“非底层复制”两种模式；左侧数据叠加和区域操作面板可折叠。
- 右侧 Inspector 提供属性、势力、据点、武将、Raw、校验 6 个视图；据点视图会按 `.dor/.stg` 联动高亮城门。
- bundle 导出时会复制同名 `.dor/.stg` 与可选 `heads.dat` 到关卡目录，浏览器导出会把这些参考文件随 `.m/.s/.x` 一起下载。
- 校验视图会提示 `.m` 结构、sidecar 尾区、`.dor/.stg` 参考文件和字段范围风险。

启动本地静态服务：

```powershell
& $py -m http.server 8771 --bind 127.0.0.1 --directory derived/editor
```

说明：

- 当前推荐使用 `stage01` 作为验收样本，并显式写入 `derived/editor`。
- `stage01` 这类超大关卡现在会在页面内自动跳过超大 `map.png`，改为按资源重建视图，因此仍然可以继续使用上面的两条命令。

浏览器入口：
- [stage01 编辑器](http://127.0.0.1:8771/stage01/editor.html)
- [编辑器索引](http://127.0.0.1:8771/index.html)

### Windows 编辑器发布包

安装发布依赖并构建包含 `stage01` 的 Windows 发行包：

```powershell
& $py -m pip install -e ".[release]"
& $py -m san_tools.map.build_editor_release . --stage stage01
```

输出文件为 `dist/SanMapEditor-stage01.zip`。解压后双击 `SanMapEditor.exe`，启动器会在随机本机端口提供编辑器并自动打开默认浏览器；关闭启动器窗口会停止服务。发布包同时包含 `editor-data`，编辑人员无需安装 Python。

### 编辑器 patch 写回

按 patch 写回复制后的 `.m`，并同步生成同名 `.s/.x`：

```powershell
& $py src/san_tools/map/apply_editor_patch.py derived/editor/stage11/stage11_patch.json . --out derived/edited/stage11.m
```

如果只想写回 `.m`，不生成 sidecar：

```powershell
& $py src/san_tools/map/apply_editor_patch.py derived/editor/stage11/stage11_patch.json . --out derived/edited/stage11.m --no-minimap-sidecars
```

### `.evt` / `.dor` / `.s/.x` 研究脚本

导出 `.evt` 与文本资源关联：

```powershell
& $py tools/analyze_evt_resources.py .
```

导出 `.s/.x` 缩略缓存统计：

```powershell
& $py tools/analyze_minimap_sidecars.py .
```

导出 `.dor` 的分组、城门坐标、据点坐标与原始记录：

```powershell
& $py tools/analyze_dor.py 三国霸业\stage01.dor
```

按 `.m` 单个 cell 的原始 `byte08-15` 绘制原始网格图、所有非零 value group 分色覆盖图，并输出 `byte09` / `byte11` 的辅助判断报告：

```powershell
& $py tools/analyze_m_byte_fields.py . --stage stage01
```

按当前稳定规则，从 `.m` 重建 `.s/.x`：

```powershell
& $py tools/build_minimap_sidecars.py . --stage stage11
```

批量处理全部可用关卡：

```powershell
& $py tools/build_minimap_sidecars.py . --all --no-preview
```

主要产物：

- `derived/sidecar_analysis/evt_resource_linkage.json`
- `derived/dor_analysis/<dor文件名>.json`
- `derived/minimap_sidecars/<stage>/sidecar_build_report.json`
- `derived/sidecar_analysis/minimap_sidecar_analysis.json`

当前摘要：

- 38 个 `.evt` 都能对上对应 `TalkNN.txt`，其中 `stage17.txt` 是可读脚本原型，`stage01.txt` 是二进制 blob。
- `.evt` 中目前最稳定的 ASCII 命令 token 是 `talk`、`VIEW`、`MAP`、`MAPALL`、`MOVE`、`TIME`、`TIMEOVER`。
- `.dor` 现已确认结构为：`Door    Data` 文件头 + `0x3C` 记录长度 + 多个 `count + records` 分组，遇到 `count=0` 结束；`analyze_dor.py` 可稳定导出 `door_x/door_y/dir/site_x/site_y/raw`。
- `.s/.x` 的稳定拆分方式已经收口为：上 `128` 行由 `.m` 的 `minimap_color` 缩放生成，下 `32` 行直接保留原始 sidecar 尾区。
- `tools/apply_editor_patch.py` 现在会在写回 `.m` 后默认同步生成同名 `.s/.x`；编辑器导出的 bundle 也会内嵌 sidecar 尾区参考，支持页面内一键导出 `.m/.s/.x`。
- 在 33 个关卡里，`.x` 的有效区始终比 `.s` 更接近 `.m` 派生结果，平均匹配率分别为 `0.620744 / 0.47098`；保留尾区后，生成结果的尾区匹配率恒为 `1.0`。
### `minimap_color` 与资源索引分析

全量统计 `acwx/acwy/acwz` 与 `minimap_color`，并生成跨关卡留一验证报告：

```powershell
& $py -m san_tools.analysis.analyze_minimap_color_relation . --out derived/minimap_color_relation/report.json
```

分析模块提供 `MinimapColorPredictor` 和 `build_minimap_color_function`。当前 33 个关卡的 `xyz` 众数样本内命中率为 95.091%，跨关卡验证为 83.471%，因此预测值只能作为编辑建议，不能替代 `.m` 中独立保存的 `minimap_color`。详细结论见 [docs/MINIMAP_COLOR_RELATION.zh.md](docs/MINIMAP_COLOR_RELATION.zh.md)。

### stage.ini 结构化导出与回写

导出 `stage.ini` JSON：

```powershell
& $py tools/export_stage_ini_tables.py .
```

由 JSON 回写 `stage.ini`：

```powershell
& $py tools/build_stage_ini.py derived/stage_ini_analysis/stage_ini_tables.json --compare-with 三国霸业\stage.ini --out derived/stage_ini_analysis/stage_roundtrip.ini
```

导出 `stage.ini` Excel 工作簿：

```powershell
& $py tools/export_stage_ini_txt_workbook.py .
```

产物：

- `outputs/stage_ini_txt_analysis/stage_ini_linked_tables.xlsx`
- `outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx`

说明：

- `linked_tables` 用于分析，保留定位与调试列。
- `conversion_tables` 用于实际转换，只保留 `row_id`、`title` 和业务字段。

把工作簿读回 JSON：

```powershell
& $py tools/import_stage_ini_txt_workbook.py --input outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx --out derived/stage_ini_txt_analysis/stage_ini_conversion_import.json
```

由工作簿回写新的 `stage.ini`：

```powershell
& $py tools/build_stage_ini_from_txt_workbook.py outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx . --out derived/stage_ini_txt_analysis/stage_ini_from_conversion_workbook.ini --compare-with 三国霸业\stage.ini
```

### `.stg` 工作簿导出与回写

导出 `stage01.stg` 工作簿：

```powershell
& $py tools/export_stg_workbook.py . --stage stage01 --out outputs/stg_workbooks/stage01_stg.xlsx
```

工作簿包含：

- `说明`：回写原则与安全边界
- `meta`：文件头、记录数、步长、尾字节
- `raw_records`：每条 76 字节记录的保底数据
- `hierarchy_records` / `force_city_summary`：当前恢复出的势力/城池层级
- `city_state`：当前可编辑的城池状态候选字段
- `troop_candidates`：当前只读的士兵候选表

从工作簿回写 `.stg`：

```powershell
& $py tools/import_stg_workbook.py outputs/stg_workbooks/stage01_stg.xlsx . --out derived/sidecar_analysis/stg_workbooks/stage01_from_workbook.stg --compare-with 三国霸业\stage01.stg
```

只按 `raw_records.raw_hex` 重建：

```powershell
& $py tools/import_stg_workbook.py outputs/stg_workbooks/stage01_stg.xlsx . --out derived/sidecar_analysis/stg_workbooks/stage01_from_workbook_raw_only.stg --compare-with 三国霸业\stage01.stg --no-city-state
```

### `.stg` 分析导出

导出原始记录链：

```powershell
& $py tools/export_stg_raw_chain.py . --stage stage01
```

导出势力/城池层级：

```powershell
& $py tools/export_stg_hierarchy.py . --stage stage01
```

导出城池状态与士兵候选表：

```powershell
& $py tools/export_stg_city_troop_analysis.py . --stage stage01
```

导出旧版 Phase 7 对照表：

```powershell
& $py tools/export_stg_phase7_links.py . --stage stage01
```

## 测试

运行 `.stg` 工作簿回归测试：

```powershell
& $py -m unittest tests.test_stg_workbook_roundtrip
```

运行 `.stg` 士兵候选分析测试：

```powershell
& $py -m unittest tests.test_stg_troop_analysis
```

运行 `.m -> .s/.x` 小地图转换测试：

```powershell
& $py -m unittest tests.test_minimap_sidecar_builder
```

运行编辑器 patch -> `.m/.s/.x` 闭环测试：

```powershell
& $py -m unittest tests.test_apply_editor_patch_minimap
```

运行地图编辑数据模型测试：

```powershell
& $py -m unittest tests.test_map_editor_model
```

运行 `.m/.dor/.stg` 多文件编辑模型测试：

```powershell
& $py -m unittest tests.test_stage_file_models
```

## 文档维护要求

本项目把文档视为交付物的一部分。每次修改都要同步维护：

1. 二进制结构变化：更新 `docs/FORMAT_NOTES.zh.md`
2. 脚本入口或参数变化：更新 `README.md`
3. 阶段目标变化：更新 `task_plan.md`
4. 新结论或废弃旧结论：更新 `findings.md`
5. 本次做了什么、如何验证：更新 `progress.md`

完整规则见 [docs/DOC_WORKFLOW.zh.md](docs/DOC_WORKFLOW.zh.md)。

## 下一步建议

当前最值得继续推进的方向：

1. 继续逆向 `stageNN.stg`，把城池块、武将块和士兵块的字段边界拆得更干净。
2. 继续逆向 `stageNN.evt`，确认事件记录如何引用地图坐标、对象和全局 id。
3. 继续从 `Emperor.exe` 核实 `.dor` 与 `.s/.x` 的真实读取/生成路径，并解释为什么 `.x` 比 `.s` 更接近真实派生结果。
4. 低优先级补充 `Tiled/TMX` 交换格式，作为外部工具互操作层。
