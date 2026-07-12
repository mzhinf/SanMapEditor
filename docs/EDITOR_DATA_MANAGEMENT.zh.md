# 地图编辑器 2.0 数据管理

本文档维护地图编辑器中 `.m`、`.dor`、`.stg` 及配套武将资料之间的编辑、派生和同步规则。字段结构以项目 `ksy` 描述为准，UI 只负责呈现和维护这些关系。

## 管理原则

1. 源字段：用户修改后写回所属文件，并记录补丁。
2. 关系字段：用户修改关联键，名称、索引和数量由编辑器重新计算。
3. 派生字段：只读显示，不允许直接输入；每次关系变化后立即刷新。
4. 镜像字段：一个业务关系在多个文件中重复存储时，只保留一个编辑入口，导出时同步到各目标文件。
5. 运行时字段：仅用于 UI 定位、列表状态和补丁跟踪，不写入游戏文件。

## 地图格子

`.m` 的每个 Cell 是地图编辑的唯一数据源。底层、叠加层和物件层使用资源图块显示；`terrain_tag`、`blocked`、`site_trigger`、`site_area` 等点字段直接写入当前 Cell。

点字段有两套相互独立的显示职责：

- 当前编辑点图层：始终用 Cell 中心点标记显示真实编辑结果。
- 数据显示叠加：只在底层、叠加层、物件层启用，按独立开关显示半透明填充、内框或阻挡标记，不修改数据。

两者读取同一份 Cell 记录，但叠加开关不参与编辑，也不改变导出内容。

本地导入 `.m` 后的小地图按主画布世界坐标投影：Cell 使用与中央画布相同的列步进 40、行步进 10，再等比缩放到最多 280×224。不得直接按 Cell 数组宽高绘制矩形网格。

## 势力与据点

势力的 `site_count` 是派生字段，等于当前未删除且归属于该势力的据点数量。修改据点的 `parentForceKey`、移出据点或删除据点后必须立即重算，不能直接编辑 `site_count`。

据点的 `primary_entity_count` 是派生字段，等于当前未删除、归属于该据点且属于 `.stg` primary Entity 区的记录数量。武将与士兵的增删或归属变更后必须立即重算。

以下关系显示字段也由关联键派生：

- 据点的 `parent_force_index`、`parent_force_name` 来自 `parentForceKey`。
- Entity 的 `parent_site_name` 来自 `parentSiteKey`。
- Entity 的 `parentForceKey`、`parent_force_*`、`actual_force_*` 由所属据点及其势力计算。
- `siteKeys`、`entityKeys` 仅为运行时关系索引，不直接编辑或导出。

## 城门

城门位置 `doorX`、`doorY`、方向 `dir`、分组 `group` 等 `.dor` 字段可编辑。城门的 `siteX`、`siteY` 是据点坐标镜像字段，必须只读并始终等于当前据点的 `coord_x`、`coord_y`。

据点坐标变化时，编辑器同步更新所属城门的 `siteX`、`siteY`，并记录 `.dor` 更新补丁，确保 `.stg` 与 `.dor` 导出结果一致。`gateKey`、`originalDorKey` 等键仅用于稳定匹配原始记录。

## 武将资料

武将列表只把 `.stg` 中 `command > 0` 的 Entity 作为已加入剧本武将；士兵仍保留在据点内容列表，但不进入武将管理列表。

未加入剧本的候选武将由 `stage.ini` 与 `History.txt` 合并，按有效 `person_id` 去重。字段职责如下：

- `.stg`：剧本归属、据点、势力、兵种、兵力及当前剧本属性。
- `stage.ini`：武将母表属性；通过 `person_id` 与 `.stg` 对应。
- `History.txt`：未加入当前剧本的候选武将及历史资料。
- `heads.dat`：通过 `portrait_id` 读取头像；只提供显示资源，不改变武将关系。

“武将管理 / 新增武将”只创建新的 stage.ini 母表候选，不自动加入任何据点；“据点 / 武将信息 / 添加已有武将”才创建 .stg Entity 并建立据点与势力归属。

## 编辑历史与本地导入

地图 Cell 修改使用独立的撤销栈和重做栈。执行新修改会清空重做栈；撤销后可通过工具栏“重做”、Ctrl+Y 或 Ctrl+Shift+Z 恢复。

本地导入允许一次选择 stageXX.m 及同名 .dor/.stg、stage.ini、History.txt、heads.dat、stage_ini.xlsx。导出优先使用本次导入的本地二进制；同关卡页面继续使用 bundle 中已经按 KSY 解析的 .stg 场景模型。

`stage.ini` 的武将主表和城池尾表按连续逻辑行管理。新增对象没有既有母表行时，编辑器根据 bundle 的 `appendLayout` 构造新行、插入对应区段并重算区段对齐；只有旧 bundle 缺少该布局时才阻断导出。

`stage.ini` 已有行只回写用户在 ini 页实际修改过的字段。新增行写入完整逻辑行；加载场景或只编辑 `.stg` 归属，不得把所有 `.stg` 当前值批量覆盖到已有母表。
## Patch 跨版本迁移

编辑器导出的 `san-editor-patch-v1` 可以通过顶部“导入”重新加载。推荐迁移顺序：

1. 在新版本编辑器中加载目标版本的 `stageXX.m`，并同时选择 `stageXX.dor`、`stageXX.stg`、`stage.ini`、`History.txt` 等配套文件。
2. 再选择旧版本导出的 `stageXX_patch.json`；也可以把 `.m`、配套文件和 Patch JSON 一次选中。
3. 检查底部修改数量和校验页，再导出新的数据文件。

组合 Patch 保存地图 Cell、场景、城门、`History.txt` 和 `stage.ini` 武将修改。编辑器也兼容导入独立的 `san-editor-scenario-patch-v1`、`san-editor-dor-patch-v1`、`san-editor-history-patch-v1`。

导入使用 `before -> after` 冲突校验：当前值等于 `before` 时应用，等于 `after` 时视为已经应用；两者都不相等时整体拒绝该 Patch，不允许只落入部分数据域。导入后继续编辑同一字段时保留最初 `before`，只更新最终 `after`，确保下一版本仍能从原始基线重放。
## UI 与补丁状态

`activeForceKey`、`activeSiteKey`、`activeEntityKey`、页签状态和列表滚动位置仅属于 UI。选择记录不得改变源数据，也不得重置同一列表的滚动位置。

删除操作先标记 `deleted` 并记录补丁，所有派生数量和关系查询必须排除已删除记录。新增、更新、删除在导出前统一经过校验和二进制重写流程。

## 新增 STG 对象

新增据点不能直接复制对象流中的第一个据点。模板按“同势力且同 `house_attr`、同 `house_attr`、任意据点”的顺序选择；新增 Entity 按“同势力且同武将/士兵类别、同类别、任意 Entity”的顺序选择。

根据 `stg.ksy` 的字段定义，新增据点必须重建 `site_part2_payload` 中的运行坐标、势力组和全局据点序号：

- `runtime_coord_or_spawn_x_004 = coord_x + 1`
- `runtime_coord_or_spawn_y_008 = floor(coord_y / 2) + 5`
- `site_kind_or_force_group_00c = parent force index + 1`
- `site_serial_010 = 重写后对象流中的全局 1-based 据点序号`

新增 Entity 的 `entity_part1_payload.runtime_force_or_ai_side_30` 在该 payload 具有 `0x34` 字节时同步为父势力的 1-based 序号。武将最大兵力、最大武力和最大智力默认取对应当前属性，不能保留模板武将的数值。
