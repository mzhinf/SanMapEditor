# Progress Log

## 2026-06-23

- 盘点游戏目录，确认 `stageNN.*`、`kingdom.cel/.atr`、DAT 容器与 `Emperor.exe` 是核心对象。
- 确认 `.m` 文件头为 `width + height + Hello1.0`，cell 记录固定 16 字节。
- 完成 `kingdom.cel/.atr` 的首轮图层拆解。
- 恢复基于 `acwx/acwy/acwz` 的真实地图渲染。
- 从 `Emperor.exe` 收口 `stage11` 对齐所需的 world-to-screen 变换。
- 建立浏览器地图编辑器原型，支持 Inspect / Paint / 本地 `.m` 加载 / Undo / Reset / patch 导出。

## 2026-06-24

- 补齐编辑器资源面板、即时重绘、右键拖动地图、方向键移动选中格。
- 完成安全 patch -> `.m` 复制写回脚本。
- 建立 `.stg/.evt/.spr/.dor/.s/.x` 的首轮 sidecar 分析脚本与工作簿导出。
- 修正文档中的第一轮编码污染，并确认后续仍需整体清理。
- 确认 `stage.ini` 可导出 JSON / Excel，并可从 JSON 回写字节级一致文件。

## 2026-06-25

- 重做 `uft8-game-txt/` 与 `stage.ini` 的关联方式，改为基于原始 dword 流，而不是先信任旧的推断标签。
- 确认 `general.txt`、`castle.txt`、`magic.txt`、`soldier.txt` 与 `stage.ini` 的稳定映射。
- 区分分析版工作簿与纯转换版工作簿。
- 新增 `stage.ini` 的 Python Excel 导出、导入与回写链路。
- 修复 Python 导出 `xlsx` 时的非法 XML 控制字符问题。

## 2026-06-26

- 继续整理 `.stg` 的势力/城池层级导出。
- 建立 `raw_chain`、`hierarchy`、`city_state` 三条并行分析链路。
- 让 `.stg` 工作簿在未修改情况下支持完整 round-trip。

## 2026-06-27

- 为 `.stg` 工作簿回写补充回归测试。
- 验证修改 `city_state.candidate_population` 时，只改动预期的单个 `u16` 字段。
- 确认编辑器卡顿的主要原因来自整图重绘与高频事件直接触发绘制。

## 2026-06-30

- 回滚 `b4a9f70` 在文档中引入的新增说明，避免把尚未收口的 `.stg` 士兵块结论写成稳定事实。
- 重新整理 `README.md`、`docs/FORMAT_NOTES.zh.md`、`findings.md`、`progress.md`、`task_plan.md`、`docs/DOC_WORKFLOW.zh.md`，统一为有效 UTF-8 中文文档。
- 把 Python 项目调整为标准 `src/` 布局：主源码迁入 `src/san_tools/`，测试迁入 `tests/`，`tools/` 改为兼容包装层。
- 扩展 `pyproject.toml` 为 `src` 包发现配置，并让 `python -m tools`、`san-tools`、旧 `tools/*.py` 三种入口同时可用。
- 补入 `export_stage_ini_txt_tables.py` 到正式源码结构，并新增 `convert-game-texts` 统一命令。
- 验证结果：`python -m tools list`、`python tools/export_stage_ini_txt_tables.py --help`、`python -m unittest tests.test_stg_troop_analysis`、`python -m unittest tests.test_stg_workbook_roundtrip` 全部通过。
