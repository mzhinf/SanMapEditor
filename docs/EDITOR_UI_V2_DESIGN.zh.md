# 三国霸业地图编辑器 UI 2.0 设计文档

## 1. 背景

当前编辑器已经具备地图浏览、资源绘制、原始字段修改、patch 导出、`.m/.s/.x` 导出，以及据点与城门高亮联动能力。但它的信息组织方式仍然偏向“工程调试页”：

- 原始 `Cell / Record / 修改` 长期占据左侧主栏
- `Minimap / Stage / 据点 / Resources` 长期占据右侧主栏
- 语义对象、底层字段、资源挑选与修改历史同时暴露

这适合逆向阶段，却不利于长期扩展成真正的地图编辑器。

本次 UI 2.0 的目标，不是单纯换一层皮，而是把页面从“按字段分布”改成“按编辑任务组织”。

## 2. 设计目标

### 2.1 目标

1. 让用户一眼看懂“我正在编辑什么、在哪里、怎么改、改了什么”。
2. 保留底层字段可控性，但把 `Raw` 能力下沉到二级视图。
3. 让据点、城门、资源与图层具备更自然的工作流组织。
4. 保留当前 bundle 数据结构，尽量以前端重组为主，降低回归风险。

### 2.2 非目标

1. 本轮不改 `.m/.s/.x` 写回协议。
2. 本轮不新建复杂的据点编辑模型写回链路。
3. 本轮不引入 Electron 或桌面壳层，只重写前端页面。

## 3. 设计原则

### 3.1 任务优先

页面优先回答四个问题：

- 我在编辑什么
- 它在地图哪里
- 它有哪些属性
- 我刚刚改了什么

### 3.2 渐进披露

- 高频内容放在一线：画布、模式、资源、据点导航
- 低频但关键内容保留在二线：`Raw`、patch、sidecar 说明

### 3.3 语义层与原始层并存

- 语义层：据点、图层、资源、当前模式、当前目标
- 原始层：`records`、字段值、恢复、patch

### 3.4 维持已有数据契约

UI 2.0 仍以 `stage.json`、`resources.json`、导出的图片资源和 `siteLinks` 为主，不依赖游戏目录实时读盘。

## 4. 信息架构

## 4.1 总体布局

新版布局采用四区结构：

1. 顶部：菜单带 + 主工具栏
2. 左侧：导航区
3. 中央：地图画布区
4. 右侧：Inspector
5. 底部：历史与说明抽屉
6. 底边：状态栏

## 4.2 左侧导航区

左侧不再只是“关卡摘要 + 资源列表”，而是明确承担两条主线导航：

### A. 剧本主线

- 剧本摘要：当前关卡、格子规模、修改数、联动状态
- 领域骨架：剧本 / 势力 / 城池 / 城门 / 地图 的统计与入口
- 城池导航：按名称、势力、坐标检索据点，并联动城门高亮

### B. 资源主线

- 当前编辑图层
- 资源过滤与排序
- 资源缩略图列表
- 点位层色板列表

这样左侧会从“面板堆叠”升级为“剧本对象导航 + 资源入口”的双主线结构，和游戏设计本身的层级更一致。

## 4.3 中央画布区

中央区域仍然是主地图，但增强三类视觉提示：

1. 顶部浮动模式条
2. 画布角标信息
3. 右上角悬浮 minimap

### 画布角标信息

用于持续显示：

- 当前工具：查看 / 绘制
- 当前图层
- 当前资源编号
- 当前据点状态

### 浮动 minimap

minimap 改为悬浮卡片，不再挤占固定侧栏高度。点击 minimap 仍然支持快速跳转。

## 4.4 右侧 Inspector

Inspector 统一为上下文面板，并拆为 4 个视图：

1. `选中项`
2. `关卡`
3. `Raw`
4. `修改`

### 选中项

显示当前选中格子的语义摘要：

- 选中坐标与索引
- 附近资源信息
- 当前归属据点
- 当前据点的门坐标概览

### 关卡

显示关卡级元数据：

- 尺寸、布局、调色板
- sidecar 导出策略
- 当前资源层统计

### Raw

显示 Record 字段编辑器：

- 字段名
- 别名
- 中文语义
- 数值输入
- 单字段恢复

### 修改

显示：

- 修改数量
- 最近 patch 列表
- 变更摘要说明

## 4.5 底部抽屉

底部抽屉负责承载“时间线型信息”，本轮先落两类内容：

1. 最近修改记录
2. 当前工作说明与快捷提示

后续可扩展：

- 校验结果
- 批量操作记录
- 导出日志

## 5. 数据架构

## 5.1 架构目标

新版编辑器需要先建立一套“能长期扩展”的领域模型，再把当前 `.m/.dor/.stg` 与资源 bundle 映射进去。核心原则如下：

1. 领域层优先表达“剧本对象”和“资源对象”，而不是直接把页面绑定到 `records`。
2. 原始字段层继续保留，作为可校验、可回写、可导出 patch 的底层真值。
3. 当前尚未完全逆向出的数据，先保留结构位，不用猜测字段填充假数据。
4. 所有运行时视图都由领域模型派生，避免各个组件直接拼装零散字段。

## 5.2 剧本数据树

剧本数据是编辑器的主语义树，来源于 `.m/.dor/.stg` 及后续可接入的剧本侧文件：

- 剧本
- 势力列表
- 城池列表
- 城池基本信息
- 城池门信息
- 城池内将领、士兵信息
- 地图记录数据

建议的可扩展结构如下：

```text
剧本 ScriptData
├─ scriptMeta
│  ├─ stageId
│  ├─ sources(.m/.dor/.stg/...)
│  ├─ width / height / layout / origin
│  └─ patchState
├─ forces[]
│  ├─ forceId
│  ├─ forceName
│  ├─ cityIds[]
│  └─ ext
├─ cities[]
│  ├─ cityId
│  ├─ cityName
│  ├─ forceId
│  ├─ basic
│  │  ├─ mapPoint
│  │  ├─ coreAreaCells[]
│  │  ├─ influenceAreaCells[]
│  │  ├─ economy / defense / reserve ext
│  │  └─ ext
│  ├─ gates[]
│  │  ├─ gateId
│  │  ├─ mapPoint
│  │  ├─ direction
│  │  └─ ext
│  ├─ roster
│  │  ├─ officers[]
│  │  └─ troops[]
│  └─ sourceRefs
│     ├─ stgRecordIndex
│     └─ dorGateIndices[]
└─ map
   ├─ records[]
   ├─ fieldMeta[]
   ├─ editableLayers[]
   ├─ pointLayers[]
   └─ sidecars
```

其中：

- `.m` 当前提供地图记录真值与图层可写内容。
- `.stg` 当前提供城池坐标、名称、势力等主锚点。
- `.dor` 当前提供城门坐标、分组、方向与归属联动。
- 将领、士兵、内政参数等未完全接入的数据，先保留 `roster` 与 `basic.ext` 结构位。

## 5.3 资源数据树

资源数据是编辑器的第二条主线，来源于 `resources.json`、`kingdom.cel` 及后续人物资源：

```text
资源 ResourceData
├─ resourceMeta
│  ├─ bundlePath
│  ├─ atlasVersion
│  └─ ext
├─ map
│  ├─ terrainLayers[]
│  ├─ overlayLayers[]
│  ├─ objectLayers[]
│  ├─ pointLayers[]
│  └─ objectGroups[]
└─ characters
   ├─ models[]
   ├─ skills[]
   └─ ext
```

字段分工建议：

- `terrainLayers`：承载基础地表资源与规则。
- `overlayLayers`：承载叠加地表、边缘、道路、水体覆盖等。
- `objectLayers`：承载建筑、树木、特效、城墙、桥梁等对象资源。
- `pointLayers`：承载 `byte08~byte11` 这类取值型图层与色板映射。
- `objectGroups`：承载“多个对象按固定阵列组成一个可复用模板”的资源组合。
- `characters`：承载人物模型、技能表现、战场特效挂点等后续可扩展内容。

## 5.4 运行时领域模型

前端运行时不应只维护 `meta + resources + selected`，而应显式维护三层模型：

1. 原始层
   - `stageMeta`
   - `records`
   - `fieldMeta`
   - `resourcesRaw`
2. 领域层
   - `scenarioDomain`
   - `resourceDomain`
3. 视图层
   - `siteIndex`
   - `layerStats`
   - `selectionSummary`
   - `resourceListModel`

建议的运行时结构示意：

```js
{
  raw: {
    stageMeta,
    records,
    fieldMeta,
    resourcesRaw,
  },
  domain: {
    script: {
      meta,
      forces,
      cities,
      map,
    },
    resources: {
      meta,
      map,
      characters,
    },
  },
  view: {
    activeSiteKey,
    selectedCell,
    selectedResource,
    siteIndex,
    layerStats,
    patches,
  },
}
```

## 5.5 当前落地范围与预留位

本轮 UI 2.0 中，实际落地范围如下：

- 已落地
- `script.meta`
- `script.cities`
- `script.forces` 的基础聚合
- `script.map`
- `cities[].gates`
- `resources.map` 下的图层资源聚合

- 预留位
- `cities[].basic.coreAreaCells`
- `cities[].basic.influenceAreaCells`
- `cities[].roster.officers`
- `cities[].roster.troops`
- `resources.map.objectGroups`
- `resources.characters.models`
- `resources.characters.skills`

预留位的意义是：现在先把接口和层级定住，未来补数据源时，只需要填充节点，不需要再重做 UI 语义。

## 5.6 派生视图模型

在领域层之上，本轮继续保留并强化以下派生模型：

1. `siteIndex`
   - 从 `siteLinks` 构建据点 -> 城门、格子 -> 据点的双向索引
2. `layerStats`
   - 提供图层占用、资源使用次数与当前图层摘要
3. `resourceListModel`
   - 支撑资源虚拟列表与后续资源分组
4. `selectionSummary`
   - 把当前格子、当前城池、当前城门归属整理成可直接渲染的摘要
5. `domainSummary`
   - 负责把“势力 / 城池 / 城门 / 资源条目 / 预留位”压缩成 UI 总览

## 5.7 数据结构与游戏文件一一对应表

说明：

- 表中的“主来源游戏文件”表示当前结构的首要真值来源。
- 如果一个结构需要多个游戏文件协同恢复，会按“主来源 + 辅助来源”的顺序并列列出。
- “转换脚本”指从游戏文件转成编辑器或分析结构的脚本；“回写脚本”指把结构再落回游戏文件的脚本。

| 数据结构 | 主来源游戏文件 | 当前转换脚本 | 回写脚本 | 说明 |
| --- | --- | --- | --- | --- |
| `raw.stageMeta`、`raw.records`、`raw.fieldMeta` | `stageNN.m` | `src/san_tools/map/export_editor_bundle.py` | `src/san_tools/map/apply_editor_patch.py` | 对应 `.m` 文件头与每个 cell 的 16 字节记录，是编辑器最底层真值。 |
| `raw.resourcesRaw`、`domain.resources.map.terrainLayers / overlayLayers / objectLayers` | `kingdom.cel` + `kingdom.atr` | `src/san_tools/map/export_editor_bundle.py`、`src/san_tools/map/render_m_cel_map.py` | 暂无稳定回写链路 | 负责地图 tile、叠加层与物件层资源目录。 |
| `domain.resources.map.pointLayers` | `stageNN.m` 的 `byte08~byte11` + `src/san_tools/map/palette.py` | `src/san_tools/map/export_editor_bundle.py` | `src/san_tools/map/apply_editor_patch.py` | 点位层本质仍是 `.m` 记录字段，只是以色板和统计列表形式投影到资源侧。 |
| `domain.script.forces[]`、`domain.script.cities[]` | `stageNN.stg` | `src/san_tools/pipelines/export_stg_raw_chain.py`、`src/san_tools/pipelines/export_stg_hierarchy.py`、`src/san_tools/pipelines/export_stg_city_troop_analysis.py` | `src/san_tools/pipelines/import_stg_workbook.py` | 势力、城池、城池状态等语义对象当前以 `.stg` 为主锚点恢复。 |
| `domain.script.cities[].gates[]`、`view.siteIndex` | `stageNN.dor` + `stageNN.stg` | `src/san_tools/analysis/analyze_dor.py`、`src/san_tools/analysis/stage_site_links.py` | 暂无独立 `.dor` 回写脚本 | `.dor` 提供城门，`.stg` 提供据点坐标，两者共同构成“城门 -> 据点”归属表。 |
| `domain.script.map.sidecars`、`raw.sidecars` | `stageNN.s` + `stageNN.x` | `src/san_tools/map/export_editor_bundle.py` | `src/san_tools/map/build_minimap_sidecars.py`、`src/san_tools/map/apply_editor_patch.py` | 当前采用“上 128 行由 `.m` 的 `byte13` 派生、下 32 行保留原始尾区”的保守策略。 |
| `stage.json` | `stageNN.m` + `stageNN.dor` + `stageNN.stg` + `stageNN.s/.x` | `src/san_tools/map/export_editor_bundle.py` | 编辑器内导出后由 `src/san_tools/map/apply_editor_patch.py` 写回 `.m/.s/.x` | 这是编辑器的主 bundle 契约，承载原始层、领域层输入与 sidecar 参考。 |
| `resources.json` | `kingdom.cel` + `kingdom.atr` + `stageNN.m` 使用统计 | `src/san_tools/map/export_editor_bundle.py` | 暂无直接回写 | 这是编辑器的资源 bundle 契约，既包含 atlas，也包含按当前关卡统计出的资源使用次数。 |

## 5.8 仓库级转换脚本总表

| 游戏文件 | 结构化产物 / 中间数据 | 转换脚本 | 回写脚本 | 说明 |
| --- | --- | --- | --- | --- |
| `stageNN.m` | `stage.json`、`map.png`、`minimap.png`、字段分析报告 | `src/san_tools/map/export_editor_bundle.py`、`src/san_tools/map/render_m_cel_map.py`、`src/san_tools/analysis/analyze_m_byte_fields.py` | `src/san_tools/map/apply_editor_patch.py` | `.m` 既是渲染输入，也是地图编辑闭环的主写回目标。 |
| `stageNN.s` / `stageNN.x` | `sidecar_build_report.json`、预览图、`stage.json.sidecars` | `src/san_tools/analysis/analyze_minimap_sidecars.py`、`src/san_tools/map/build_minimap_sidecars.py`、`src/san_tools/map/export_editor_bundle.py` | `src/san_tools/map/build_minimap_sidecars.py`、`src/san_tools/map/apply_editor_patch.py` | 小地图 sidecar 当前已经纳入编辑器导出闭环。 |
| `stageNN.stg` | `stg_raw_chain.json/csv`、`stg_hierarchy.json/csv`、`city_state`、`stageNN_stg.xlsx` | `src/san_tools/pipelines/export_stg_raw_chain.py`、`src/san_tools/pipelines/export_stg_hierarchy.py`、`src/san_tools/pipelines/export_stg_city_troop_analysis.py`、`src/san_tools/pipelines/export_stg_workbook.py` | `src/san_tools/pipelines/import_stg_workbook.py` | `.stg` 当前同时支持原始链、层级树、工作簿与已确认字段的安全回写。 |
| `stageNN.dor` | `derived/dor_analysis/*.json`、`site_links` | `src/san_tools/analysis/analyze_dor.py`、`src/san_tools/analysis/stage_site_links.py` | 暂无 | `.dor` 当前定位是城门 sidecar，重点产出为分组门数据与据点归属表。 |
| `stageNN.evt` | `evt_resource_linkage.json` | `src/san_tools/analysis/analyze_evt_resources.py` | 暂无 | 目前仍是研究态，稳定产物以分析报告为主。 |
| `kingdom.cel` / `kingdom.atr` | `resources.json`、资源 atlas、地图渲染图、图层导出图 | `src/san_tools/map/render_m_cel_map.py`、`src/san_tools/map/export_editor_bundle.py`、`src/san_tools/map/export_m_layers.py`、`src/san_tools/map/export_map_previews.py` | 暂无 | 资源容器目前只读，承担地图与资源目录生成。 |
| `stage.ini` | `stage_ini_tables.json`、`stage_ini_linked_tables.xlsx`、`stage_ini_conversion_tables.xlsx` | `src/san_tools/pipelines/export_stage_ini_tables.py`、`src/san_tools/pipelines/export_stage_ini_txt_workbook.py`、`src/san_tools/codecs/stage_ini_txt_linkage.py` | `src/san_tools/pipelines/build_stage_ini.py`、`src/san_tools/pipelines/build_stage_ini_from_txt_workbook.py` | `stage.ini` 的直接文本映射当前稳定对应 `general.txt`、`castle.txt`、`magic.txt`、`soldier.txt`。 |

## 6. 组件架构

## 6.1 页面壳层

- `AppShell`
- `MenuBar`
- `ActionBar`
- `StatusBar`

## 6.2 编辑工作区

- `NavigatorPanel`
- `CanvasStage`
- `InspectorPanel`
- `BottomDock`

## 6.3 关键子组件

- `SiteList`
- `ResourceLibrary`
- `ContextSummary`
- `RawRecordEditor`
- `PatchTimeline`
- `FloatingMiniMap`

## 7. 交互流程

## 7.1 查看流程

1. 左侧选择据点或图层
2. 中央定位到画布区域
3. 右侧查看语义摘要或关卡信息
4. 需要字段级确认时切到 `Raw`

## 7.2 绘制流程

1. 选择图层
2. 在资源库选择资源编号
3. 工具切到 `绘制`
4. 在画布点击目标格
5. 底部与右侧同步显示修改记录

## 7.3 据点检查流程

1. 左侧结构区选择据点
2. 画布高亮据点与城门
3. 右侧 `选中项` 查看归属、门数和门坐标
4. 需要底层核对时切 `Raw`

## 7.4 导出流程

1. 在顶部工具栏执行导出
2. 状态栏反馈导出状态
3. sidecar 缺失时在 `关卡` 面板与状态栏都给出说明

## 8. 视觉与样式方向

## 8.1 风格关键词

- 桌面编辑器
- 温暖纸面感
- 青绿色主强调
- 清晰边框分区
- 非全黑开发者工具风

## 8.2 色彩策略

- 背景：暖灰与纸面色
- 强调：青绿
- 高亮：金色/琥珀
- 辅助：石墨灰

## 8.3 字体策略

- 中文主字体：`"Microsoft YaHei UI", "PingFang SC", "Noto Sans SC", sans-serif`
- 标题可使用更有辨识度的宋黑混合风格，但不能影响可读性

## 9. 实施方案

## 9.1 第一阶段：文档与计划

- 更新 `task_plan.md`
- 更新 `findings.md`
- 更新 `progress.md`
- 新增本设计文档

## 9.2 第二阶段：前端重构

优先改造：

1. HTML 结构
2. CSS 变量与布局系统
3. Inspector 标签切换
4. 左侧据点导航与资源库重排
5. 底部历史抽屉

尽量复用：

1. 画布绘制逻辑
2. minimap 点击跳转
3. 资源虚拟列表
4. patch 与 undo 机制

## 9.3 第三阶段：验证

- Node 语法检查
- bundle 页面基础启动验证
- Git 分两次提交，确保可以独立回滚

## 10. 后续扩展位

本次 UI 2.0 完成后，可在现有架构上继续追加：

- 图层树与可见性/锁定开关
- 校验器抽屉
- 批量选区与复制/剪切
- 据点/城门模板
- 事件与触发对象面板

这样可以保证编辑器后续增长时，不需要再次大规模推翻布局。
