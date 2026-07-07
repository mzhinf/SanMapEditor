# 结论记录

## 当前稳定结论

### 1. 编辑器输入数据已经足够支撑 UI 2.0

当前导出的 `stage.json` 已经同时提供：

- 关卡基础信息：`stage`、`width`、`height`、`layout`、`origin`、`render`
- 原始记录数据：`records`
- 字段元数据：`fields`、`fieldMeta`、`editableRecordFields`
- 图层定义：`editableLayers`、`resourceLayers`、`pointLayers`
- 语义辅助数据：`pointPalette`、`siteLinks`
- sidecar 回写辅助数据：`sidecars`

因此，新版 UI 不需要先扩展后端数据结构，就可以先完成布局与交互重构。

### 2. 当前编辑器的主要问题不是功能缺失，而是信息架构偏底层

现有页面更像“工程调试页”：

- 左侧常驻 `Cell / Record / 修改`
- 右侧常驻 `Minimap / Stage / 据点 / Resources`
- 原始字段与语义对象长期同时暴露

这使用户在“选对象、改属性、验证结果、切换资源”之间频繁横向扫视，任务链被拆散。

### 3. 研究文档与示意图指向同一方向

两份参考都支持把界面重组为：

- 左侧：结构导航、图层与资源入口
- 中央：地图画布与直接操作
- 右侧：上下文 Inspector
- 底部：历史、差异、说明、校验等抽屉

也就是说，新版 UI 应该从“字段分栏”转向“任务分层”。

### 4. Raw 能力不能删除，但不该继续占据一线主视图

`Record` 仍然是安全修改与字段核对的核心能力，但更适合作为 Inspector 中的 `Raw` 视图，而不是首页常驻主区块。这样既保留工程透明度，也能把据点、资源、图层等高频任务放回前台。

### 5. 现有据点联动能力已经可以承担导航角色

当前前端已经支持：

- `siteLinks` 的据点与城门归属模型
- 从选中格子同步当前据点
- 在画布中高亮据点与其城门
- 通过下拉选择据点并定位

因此，新版 UI 可以直接把据点选择升级成左侧“结构导航”，不需要额外逆向数据。

## 本轮 UI 2.0 设计决策

### 1. 采用任务导向布局

布局目标：

- 左：导航与资源
- 中：画布与模式提示
- 右：Inspector
- 下：修改历史与说明

### 2. 同时保留“语义层”和“原始层”

- 语义层负责据点、资源、当前模式、当前目标
- 原始层负责 `records`、字段值、恢复、patch

### 3. 先重构前端组织，再视需要扩展导出数据

本轮优先级是重写 `editor_app.html` 的 HTML/CSS/交互组织。

只有当新版 UI 证明需要更多结构化字段时，才回头扩展 `export_editor_bundle.py`。

### 6. 新版编辑器必须先固化“剧本 / 资源”领域模型，不能只停留在布局重排

用户补充的层级要求已经明确指出，编辑器后续不只是地图涂格工具，而是要承载：

- 剧本 -> 势力 -> 城池 -> 城门 / 编制
- 资源 -> 地图层 -> 物件组合 / 人物模型 / 技能模型

这意味着前端运行时需要显式维护领域模型，把 `.m/.dor/.stg` 与 `resources.json` 重新组织成两条主线，而不是让每个面板直接读取零散字段。

### 7. 当前数据已经足够先搭出骨架，但要明确区分“已落地节点”和“预留节点”

目前可稳定接入的节点主要有：

- 剧本元信息
- 城池坐标、名称、势力、城门归属
- 地图记录、字段元数据、资源图层、点位图层

而以下节点仍应先保留结构位，不应伪造内容：

- 城池核心区域与势力范围坐标组
- 城池内将领、士兵信息
- 物件组合模板
- 人物模型与技能模型

这样后续继续接入新文件时，能沿着既有树结构补节点，而不是再次改 UI 语义。

### 8. 当前仓库已经形成“游戏文件 -> 中间结构 -> 回写脚本”的稳定链路，适合用统一表格维护

当前可以把后续维护入口统一收口为以下几条主链：

- `.m` -> `stage.json` / `resources.json` / 编辑器运行时结构，入口脚本以 `src/san_tools/map/export_editor_bundle.py` 为准，回写入口为 `src/san_tools/map/apply_editor_patch.py`。
- `.stg` -> `raw_chain` / `hierarchy` / `city_state` / `stageNN_stg.xlsx`，导出链路由 `src/san_tools/pipelines/export_stg_*.py` 组成，已确认字段通过 `src/san_tools/pipelines/import_stg_workbook.py` 回写。
- `.dor` + `.stg` -> `siteLinks`，由 `src/san_tools/analysis/analyze_dor.py` 与 `src/san_tools/analysis/stage_site_links.py` 组合生成，是当前“城门 -> 据点”归属关系的正式来源。
- `.s/.x` -> `sidecar_build_report.json` / `stage.json.sidecars`，由 `src/san_tools/map/build_minimap_sidecars.py` 负责闭环，策略是“顶部有效区派生 + 底部尾区保留”。
- `stage.ini` + `uft8-game-txt/*.txt` -> `stage_ini_linked_tables.xlsx` / `stage_ini_conversion_tables.xlsx`，正式映射逻辑以 `src/san_tools/codecs/stage_ini_txt_linkage.py` 为准，回写入口为 `src/san_tools/pipelines/build_stage_ini_from_txt_workbook.py`。

这意味着后续文档维护不应再只写“哪个文件大概对应什么”，而应明确写成“游戏文件 -> 中间结构 -> 转换脚本 -> 回写脚本”的可追踪链路；同时新增脚本时应优先记录 `src/san_tools/` 下的正式入口，而不是仅记录 `tools/` 包装层。

## 2026-07-08 STG 块流结构结论

- `.stg` 主格式已从早期“8 字节头 + 76 字节记录”修正为 Emperor.exe 风格对象流：`u32 present_or_version`，随后是多级 `u32 size + payload` Block。
- 已验证 42 个样本：原版 `三国霸业/stage00.stg`、`stage01.stg` 到 `stage45.stg` 中存在的全部样本，`SGBY_MAP/new_san/stage01.stg` 到 `stage04.stg`，以及 `new-stage01.stg`。
- 已见块大小变体：`root_part1=0x48/0x4C`、`force_part2=0x7C/0x84`、`site_part1=0x58/0x5C`、`entity_part1=0x30/0x34`；其余核心块为 `root_part2=0x34`、`force_part1=0x60`、`site_part2=0x2B0`、`entity_part2=0xE0`。
- `site_part2 +0x27C..+0x28C` 是可选 Entity 控制 flag；`+0x2AC` 当前 42 个样本均为 0，仍作为额外 Entity 数量候选保留。
- `after_forces_tail` 不是固定 0xA0：尾区小于等于 0xA0 时整体保留，尾区大于 0xA0 时按“前置尾区 + 最后 0xA0 候选尾块”保留；全部按 u32 words 保存。
