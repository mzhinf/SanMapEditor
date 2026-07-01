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
- `.evt/.spr/.dor/.s/.x` 已有第二轮 sidecar 研究与保守写回脚本，能输出 `.evt` 文本资源关联、`.s/.x` 缩略缓存统计，以及从 `.m` 重建 `.s/.x` 的有效区。

更详细的格式说明见：

- [docs/FORMAT_NOTES.zh.md](docs/FORMAT_NOTES.zh.md)
- [docs/DOC_WORKFLOW.zh.md](docs/DOC_WORKFLOW.zh.md)

## 目录说明

- `src/san_tools/`：正式维护的 Python 源码包。
- `tests/`：独立测试目录。
- `tools/`：兼容旧调用方式的包装层，方便继续直接运行 `tools/*.py`。
- `docs/`：格式笔记与文档维护约定。
- `derived/`：中间分析结果、编辑器 bundle、图片导出。
- `outputs/`：工作簿与外部可读导出结果。
- `uft8-game-txt/`：从游戏文本批量转成 UTF-8 后的对照目录。

## Python 项目结构

`san-map-tools` 现在按标准 `src/` 布局维护：

- 根目录使用 `pyproject.toml` 管理打包配置
- 主要源码位于 `src/san_tools/`
- 测试集中在 `tests/`
- `tools/` 保留为兼容包装层，避免打断现有脚本入口
- 提供统一入口 `python -m tools` 与安装后的 `san-tools`

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

导出的编辑页现在支持：

- `.m` 记录字段按 `flags / byte08..byte15` 统一口径展示，其中 `reserved0/1/2/3` 只读。
- 侧边栏顺序固定为 `Minimap -> Cell -> Record -> Resources -> Stage`。
- `Record` 区可直接编辑所有非 `reserved` 数值字段。
- 通过工具栏的“导出 .m/.s/.x”按钮可直接一键导出当前修改结果。

启动本地静态服务：

```powershell
& $py -m http.server 8787 --bind 127.0.0.1 --directory derived/editor
```

浏览器入口：

- [stage11 编辑器](http://127.0.0.1:8787/stage11/editor.html)
- [编辑器索引](http://127.0.0.1:8787/index.html)

### 编辑器 patch 写回

按 patch 写回复制后的 `.m`，并同步生成同名 `.s/.x`：

```powershell
& $py tools/apply_editor_patch.py derived/editor/stage11/stage11_patch.json . --out derived/edited/stage11.m
```

如果只想写回 `.m`，不生成 sidecar：

```powershell
& $py tools/apply_editor_patch.py derived/editor/stage11/stage11_patch.json . --out derived/edited/stage11.m --no-minimap-sidecars
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

分析 `.dor` 与 `.m` 的候选坐标关系并导出覆盖图：

```powershell
& $py tools/analyze_dor_relationship.py . --stage stage20 --top-pairs 3
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
- `derived/dor_relationship/<stage>/dor_relationship.json`
- `derived/minimap_sidecars/<stage>/sidecar_build_report.json`
- `derived/sidecar_analysis/minimap_sidecar_analysis.json`

当前摘要：

- 38 个 `.evt` 都能对上对应 `TalkNN.txt`，其中 `stage17.txt` 是可读脚本原型，`stage01.txt` 是二进制 blob。
- `.evt` 中目前最稳定的 ASCII 命令 token 是 `talk`、`VIEW`、`MAP`、`MAPALL`、`MOVE`、`TIME`、`TIMEOVER`。
- `.dor` 文件头携带 `Door    Data` 魔数；重新从 `Emperor.exe` 复核后，`.spr/.dor/.evt` 明确落在同一 sidecar 装配簇里，而 `.m/.s/.x` 在另一组加载链上，当前更支持“.dor 是关卡 sidecar”而不是“.m 某个字节字段的直出表”。
- `.s/.x` 的稳定拆分方式已经收口为：上 `128` 行由 `.m` 的 `byte13 / minimap_color` 缩放生成，下 `32` 行直接保留原始 sidecar 尾区。
- `tools/apply_editor_patch.py` 现在会在写回 `.m` 后默认同步生成同名 `.s/.x`；编辑器导出的 bundle 也会内嵌 sidecar 尾区参考，支持页面内一键导出 `.m/.s/.x`。
- 在 33 个关卡里，`.x` 的有效区始终比 `.s` 更接近 `.m` 派生结果，平均匹配率分别为 `0.620744 / 0.47098`；保留尾区后，生成结果的尾区匹配率恒为 `1.0`。
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
