# Progress Log

## 2026-06-23

- 盘点游戏目录，确认 `stageNN.*`、`kingdom.cel/.atr`、DAT 容器与 `Emperor.exe` 为核心对象。
- 确认 `.m` 文件头为 `width + height + Hello1.0`，cell 记录固定 16 字节。
- 完成 `kingdom.cel/.atr` 的第一轮图层拆解。
- 恢复基于 `acwx/acwy/acwz` 的真实地图渲染。
- 从 `Emperor.exe` 收口 `stage11` 所需的 world-to-screen 变换。
- 建立浏览器地图编辑器原型，支持 Inspect / Paint / 本地 `.m` 加载 / Undo / Reset / patch 导出。

## 2026-06-24

- 补齐编辑器资源面板、即时重绘、右键拖动地图、方向键移动选中格。
- 完成安全 patch -> `.m` 复制写回脚本。
- 建立 `.stg/.evt/.spr/.dor/.s/.x` 的第一轮 sidecar 分析脚本与工作簿导出。
- 修复 `docs/FORMAT_NOTES.zh.md` 中的中文编码污染一次，但后续又发现其余文档仍有残留污染。
- 确认 `stage.ini` 可导出 JSON / Excel，并可从 JSON 回写字节级一致文件。

## 2026-06-25

- 重做 `uft8-game-txt` 与 `stage.ini` 的关联方式，改为基于原始 dword 流，而不是先信任 `family_guess`。
- 确认当前稳定映射：
  - `general.txt`：步长 `57 dwords`
  - `castle.txt`：步长 `25 dwords`
  - `magic.txt`：步长 `19 dwords`
  - `soldier.txt`：步长 `20 dwords`
- 区分分析版工作簿与纯转换版工作簿。
- 新增纯 Python 的 Excel 导出、导入、回写链路：
  - `tools/export_stage_ini_txt_workbook.py`
  - `tools/import_stage_ini_txt_workbook.py`
  - `tools/build_stage_ini_from_txt_workbook.py`
- 修复 Python 导出 `xlsx` 时的非法 XML 控制字符问题。
- 验证结果：
  - `stage_ini_linked_tables.xlsx` 可由 Python 正常导出
  - `stage_ini_conversion_tables.xlsx` 可由 Python 正常导出
  - 未修改的 `stage_ini_conversion_tables.xlsx` 可回写为与原始 `stage.ini` 完全一致的新文件
  - `sha256 = 29584de26770323a09849d180331d936e9c112f55936d76b08f4f6f6a63663b8`
- 新增并修正 `.stg` 导出链路：
  - `tools/export_stg_phase7_links.py`：保留旧版 `224 / 96 / 92` 字段归一化对照。
  - `tools/export_stg_raw_chain.py`：直接按原始 76 字节 stride 导出完整记录链，不再跳过无文本记录。
  - `tools/export_stg_hierarchy.py`：按原始顺序恢复势力/城池/武将/士兵层级。
- 导出 `stage01` 新产物：
  - `derived/sidecar_analysis/raw_chain/stage01/stg_raw_chain.json`
  - `derived/sidecar_analysis/raw_chain/stage01/stg_raw_chain.csv`
  - `derived/sidecar_analysis/hierarchy/stage01/stg_hierarchy.json`
  - `derived/sidecar_analysis/hierarchy/stage01/stg_hierarchy_records.csv`
  - `derived/sidecar_analysis/hierarchy/stage01/stg_force_city_summary.csv`
- `stage01.stg` 当前验证结果：
  - 文件为 8 字节头、2502 条完整 76 字节记录、48 字节尾部。
  - 层级导出得到 10 个势力/特殊块、38 个城池块、86 条武将记录、42 条士兵记录。
  - 可读结构例子：`劉備 -> 平原`、`曹操 -> 陳留`、`孫堅 -> 長沙`、`劉表 -> 襄陽/江夏/江陵`、`中立國 -> 襄平/北平/薊/...`。
  - `city_92_family` 仍有 20 条记录全部对上 `castle.txt` 的 `city_id / city_size`。
  - `context_prev_slot / context_next_slot / context_owner_slot_consensus` 已降级为旧版排查线索，不再当作 owner 结论。
- 新增 `tools/export_stg_city_troop_analysis.py`，导出城池状态字段与士兵记录候选表：
  - `derived/sidecar_analysis/city_troop/stage01/stg_city_troop_candidates.json`
  - `derived/sidecar_analysis/city_troop/stage01/city_state_candidates.csv`
  - `derived/sidecar_analysis/city_troop/stage01/troop_candidates.csv`
- `stage01.stg` 城池状态字段验证结果：
  - `city_id / city_size / map_x / map_y` 全部 38/38 对齐 `castle.txt`。
  - `city_id+6/+8/+10` 高置信对应当前人口/金/粮。
  - `city_id+14/+16/+18` 高置信对应开发/商业/治安。
  - `city_id+20/+22/+24` 高置信对应三项上限。
  - `city_id+30` 是太守/城主武将 id 候选，23 条能映射 `History.txt`，其中 22 条在本城武将列表内。
  - 42 条士兵记录已挂回城池，但数量/等级字段仍未最终命名。

## 本次文档收口（已完成）

- `README.md` 已重写为干净 UTF-8 中文版本。
- `docs/FORMAT_NOTES.zh.md` 已重写，并单列 `stage.ini` 二进制构成。
- 新增 `docs/DOC_WORKFLOW.zh.md`，把文档更新责任和提交前检查表写死。
- `task_plan.md`、`findings.md`、`progress.md` 已同步为新的有效基线。
- 本轮继续把 `.stg Phase 7` 的新结论同步写回文档，避免只停留在聊天上下文。
- 验证：Python 按 UTF-8 读取上述文档成功，确认乱码来自控制台代码页而非文件内容。

## 验证记录

| 项目 | 结果 |
| --- | --- |
| `stage.ini` JSON -> binary 回写 | 字节级一致 |
| `stage_ini_conversion_tables.xlsx -> stage.ini` 回写 | 字节级一致 |
| 编辑器本地 `.m` 加载 | 通过 |
| 编辑器 patch 写回复制件 | 通过 |
| 核心文档 UTF-8 读取 | 通过 |
| `stage01.stg city_id -> castle.txt` 对齐 | 20/20 通过 |
| `stage01.stg city_size -> castle.txt` 对齐 | 20/20 通过 |
| `stage01.stg` 原始记录链导出 | 2502 条记录 + 48 字节尾部，通过 |
| `stage01.stg` 层级导出 | 10 个势力/特殊块、38 个城池块，通过 |
| `stage01.stg` 城池状态字段 | `city_id/city_size/x/y` 38/38 对齐，通过 |

## 当前风险

1. `.stg` 直接 owner 字段仍未锁定，当前优先按顺序层级解释所属关系。
2. 士兵记录中的数量、等级、兵种 id 字段仍需继续命名。
3. `.evt` 仍未完成字段命名，暂时不能做完整语义编辑器。
4. `.s/.x` 的写回流程尚未确认，不应贸然生成覆盖。
5. `acwz` 的完整 footprint / z-order 仍有尾差。

## 2026-06-25 `.stg` Excel 互转收口

- 新增 `.stg` Excel 互转脚本：
  - `tools/export_stg_workbook.py`：导出 `meta/raw_records/hierarchy_records/force_city_summary/city_state/troop_candidates`。
  - `tools/import_stg_workbook.py`：从 workbook 回写 `.stg`，默认应用 `city_state`，也支持 `--no-city-state` raw-only 重建。
- 补充 `docs/FORMAT_NOTES.zh.md` 的 `.stg` 字节级构成与转换脚本契约，写明 header、record、tail、sheet、回写公式和验证结果。
- 更新 `README.md` 的 `.stg` 互转使用指南。
- 验证结果：
  - 默认模式：`stage01_stg.xlsx -> stage01_from_workbook.stg` 与原 `stage01.stg` 字节完全一致。
  - `--no-city-state`：同样字节完全一致。
  - 编辑烟测：第一个城池人口 `1200 -> 1201` 后仅 1 个字节变化，偏移 `0x1A4`。

## 2026-06-29 `.stg` Excel 互转测试

- 新增 `tools/test_stg_workbook_roundtrip.py`，用 `unittest` 覆盖 `.stg -> Excel -> .stg` 的核心回归路径。
- 测试点包括：工作簿必要 sheet 与 meta、默认导入字节一致、raw-only 字节一致、编辑 `city_state.candidate_population` 后只改预期 u16 字段。
- 修正 `tools/stage_ini_excel_codec.py`：读取/写入 workbook 后显式关闭 openpyxl 句柄，避免 Windows 上测试清理或后续批处理遇到文件锁。
- 验证命令：`& $py -m unittest tools.test_stg_workbook_roundtrip`，结果 `Ran 4 tests ... OK`。
