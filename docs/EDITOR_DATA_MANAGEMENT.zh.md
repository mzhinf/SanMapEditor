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

## UI 与补丁状态

`activeForceKey`、`activeSiteKey`、`activeEntityKey`、页签状态和列表滚动位置仅属于 UI。选择记录不得改变源数据，也不得重置同一列表的滚动位置。

删除操作先标记 `deleted` 并记录补丁，所有派生数量和关系查询必须排除已删除记录。新增、更新、删除在导出前统一经过校验和二进制重写流程。
