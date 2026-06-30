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
- `.evt/.spr/.dor/.s/.x` 已有首轮 sidecar 分析脚本，但仍有未定字段。

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

启动本地静态服务：

```powershell
& $py -m http.server 8787 --bind 127.0.0.1 --directory derived/editor
```

浏览器入口：

- [stage11 编辑器](http://127.0.0.1:8787/stage11/editor.html)
- [编辑器索引](http://127.0.0.1:8787/index.html)

### `stage.ini` 结构化导出与回写

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
3. 继续从 `Emperor.exe` 核实 `.s/.x` 的生成与读写路径，把小地图缓存写回补齐到编辑器链路。
4. 低优先级补充 `Tiled/TMX` 交换格式，作为外部工具互操作层。