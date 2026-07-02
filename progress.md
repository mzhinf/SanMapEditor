# 进度日志

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
- 扩展 `apply_editor_patch.py`，让编辑器 patch 在写回 `.m` 后默认同步生成同名 `.s/.x`，补齐 sidecar 写回闭环。
- 重构 `build_minimap_sidecars.py`，抽出 `write_stage_sidecar_outputs()`，让批处理与编辑器写回复用同一套 sidecar 生成逻辑。
- 新增 `tests/test_apply_editor_patch_minimap.py`，覆盖 patch -> `.m/.s/.x` 闭环，以及跳过 sidecar 的分支。
- 新增 `analyze_dor_relationship.py` 与命令行入口，结合 `Emperor.exe` 字符串线索和 `.m` 渲染结果输出 `.dor` 候选字段覆盖图。
- 验证结果补充：bundled Python 下的 `python -m unittest tests.test_apply_editor_patch_minimap` 与 `python tools/analyze_dor_relationship.py . --stage stage20 --top-pairs 3` 均已通过。
## 2026-07-01

- 新增 `src/san_tools/analysis/analyze_dor_byte_fields.py` 与 `tools/analyze_dor_byte_fields.py`，用于 `.dor` 记录自身的原始 byte 覆盖图分析。
- 为统一入口补充 `analyze-dor-relationship`、`analyze-dor-byte-fields` 与 `analyze-m-byte-fields` 命令注册。
- 新增 `src/san_tools/analysis/analyze_m_byte_fields.py` 与 `tools/analyze_m_byte_fields.py`，按 `.m` 单个 cell 的原始 `byte08-15` 导出原始网格图、所有非零 value group 分色覆盖图与 `derived/m_byte_fields/<stage>/m_byte_fields.json`。
- 复核 `.m` 口径后确认：`byte08=218` 与 `byte10=239` 都只在 `stage01` 出现；`byte09=1` 广泛分布于 33 个 `.m`；`byte11` 的同值会聚成连续编号、每组 36 cell 的菱形 footprint。
- 调整 `analyze_m_byte_fields.py`：`byte08-15` 不再只围绕 `byte08=218 / byte10=239` 一类猜想单独绘图，而是为每个字段额外输出“所有非零 value group 分色叠加”的底图覆盖图与总览拼图。
- 清理 `analyze_m_byte_fields.py` 中遗留的 `byte08=218` 与 `byte10=239` 专项统计、覆盖图和报告字段，避免脚本继续携带已经失效的旁路输出。
- 根据人工复核结果，回写 `.m` 字节语义：`byte08` 为码头/水陆交界切换辅助标记，`byte09` 为通行标记，`byte10` 为城池/山寨触发范围且 `239` 表示城门，`byte11` 为进入目标区域的触发 id，`byte13` 为小地图颜色索引。
- 新增 `derived/dor_relationship/stage01/dor_m_overlap.json`，把 `stage01.dor` 候选坐标对与 `.m byte08/09/10/11` 做重合度对比；当前结果不支持 `.dor` 直接记录码头/水陆交界切换点，反而更接近门、入口、通行限制或触发范围相关 sidecar。
- 重写 `analyze_dor_relationship.py`，把 `Emperor.exe` 的扩展名引用簇、`Door    Data` 头校验位点与 `.dor` 候选坐标报告合并输出，并补上超大底图的 `Image.MAX_IMAGE_PIXELS = None` 保护。
- 重新从 `Emperor.exe` 核实 `.dor` 与 `.m`：确认 `.spr/.dor/.evt` 与 `.m/.s/.x` 分属不同代码簇，且 `Door    Data` 在 `0x3e6d9 / 0x3ea3b` 做 12 字节头校验；这进一步支持 `.dor` 是关卡 sidecar，而不是 `.m` 某个字节字段的直接外置表。
- 统一 `.m` 编辑字段口径：编辑器与导出 bundle 现在使用 `word06`、`byte08..byte15` 命名，并移除旧的 `flags` 页面描述。
- 重做 `src/san_tools/map/editor_app.html`：页面改为左右双栏，左侧放 `Cell -> Record -> 修改`，右侧放 `Minimap -> Stage -> Resources`，并保留“一键导出 .m/.s/.x”。
- 扩展 `export_editor_bundle.py`：导出的 `stage.json` 现在包含字段元数据与 `.s/.x` 尾区参考，页面内导出会沿用“上 128 行派生、下 32 行保留”的 sidecar 规则。
- 修正 `apply_editor_patch.py`、`build_minimap_sidecars.py` 与 `pyproject.toml`：兼容 `flags/byte13` 与旧字段别名，补回 `Pillow` 依赖声明，并清理脚本内的乱码注释/帮助文本。
- 验证补充：`H:\Workstation\sgby\.venv\Scripts\python.exe -m unittest tests.test_apply_editor_patch_minimap` 已通过；同时完成 `src/san_tools/map/editor_app.html` 的 Node 语法检查，以及 `src/san_tools/map/export_editor_bundle.py . --stage stage11 --out derived/editor_smoke` 的导出烟测。

## 2026-07-02

- 修复编辑器在 `stage01` 等超大关卡上的启动失败：当导出的 `map.png` 超过浏览器稳定解码范围时，页面会自动跳过底图加载并改用资源重建，不再因为 `EncodingError` 中断。
- 修正资源重建模式下的局部重绘逻辑，并在加载本地 `.m` 时主动清空旧底图/小地图缓存，避免后续编辑时把旧关卡底图混入新视图。
- 收口 `export_editor_bundle.py` 的模板来源，改为只从 `src/san_tools/map/editor_app.html` 复制编辑器页面，不再依赖 `tools/editor_app.html`。
- 更新 `README.md` 中编辑器相关命令，推荐直接使用 `src/san_tools/map/*.py` 正式入口，同时保留 `http.server` 的原有启动方式说明。
- 根据最新页面调整字段与布局：`word06` 取代旧的 `flags` 展示，顶部移除“图层/值”，资源图层切换收入右侧 `Resources`，左侧 `Record` 改为紧凑无间隔列表。
- 调整 `Resources` 面板：过滤控件收窄后不再挤出横向滚动，资源区拉伸到右栏底部，并改为窗口化渲染以支持全量资源滚动查看。
- 修正 `Resources` 右栏无法实际滚动的问题：给 `.side-right .resource-section` 单独恢复可伸展高度，避免被通用 `.section` 的 `flex: 0 0 auto` 覆盖。
- 调整资源卡片尺寸计算：`acwz` 现在会按 72px 缩略图自适应卡片宽高，底部 `id x count` 标签不再被缩略图挤掉。
- 继续打磨编辑器 `Resources` 体验：资源计数文案改为“有效资源共 … 项”，左侧改为仅 `修改` 列表独立滚动；同时给 `byte08~byte11` 增加可切换的点位图层，便于直接查看并绘制这些字段。
- 调整 `Resources` 图层切换文案为“中文字段名(英文字段名)”格式，并放大 `byte08~byte11` 的地图点位显示，使高倍缩放下仍能清晰辨认。
- ??????????? `.m` ??? `pointPalette/resourceLayers/pointLayers` ???????? `byte08~byte11` ? `Resources` ?????????
