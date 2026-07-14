# 地图编辑器 2.0 数据管理

本文档维护地图编辑器中 `.m`、`.dor`、`.stg`、`stage.ini`、`History.txt` 及配套武将资料之间的编辑、派生和同步规则。字段结构以项目 `ksy` 描述为准，UI 只负责呈现和维护这些关系。

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

两者读取同一份 Cell 记录，但叠加开关不参与编辑，也不改变导出内容。“已编辑框”读取当前 `.m` Patch 坐标，仅控制绿色边框显示；与其他数据叠加一样，只在底层、叠加、物件层可见。选中 Cell 使用低透明度橙色填充，避免遮挡底图。

本地导入 `.m` 后的小地图按主画布世界坐标投影：Cell 使用与中央画布相同的列步进 40、行步进 10，再等比缩放到最多 280×224。不得直接按 Cell 数组宽高绘制矩形网格。minimap_color 必须通过 minimapPalette 映射到 SAN_RGB_PALETTE；pointPalette 仅用于区分数据层编辑值，不能用于小地图着色。`minimap_color` 与 xyz 的全量统计表明它不是确定派生字段，管理规则和预测函数见 [小地图颜色关系](MINIMAP_COLOR_RELATION.zh.md)。

区域剪切、区域复制和合成对象共用稀疏快照，并提供两种模式：

- **全复制**：所有选中 Cell 均进入快照，按 `.m` 字段顺序复制完整记录。剪切时保留 `acwx`，令 `acwy/acwz = -1`，其余可编辑字段写为 `0`。
- **非底层复制**：当 Cell 的 `acwy/acwz` 任一值大于等于 `0`，或 `terrain_tag/blocked/site_trigger/site_area` 任一值非 `0` 时才进入快照；快照按原顺序复制除 `acwx`、`minimap_color` 外的全部字段。剪切只清理快照实际包含的可编辑字段，因此保留源 Cell 的 `acwx` 与 `minimap_color`。

两种模式的整次清理都通过一个 `applyChangeSet` 写入，因此可一次撤销或重做。区域范围只取当前画布多选结果，不再维护“设起点”状态。数据叠加显示和区域操作面板均可折叠，以便把左侧高度让给资源库。`terrain_tag` 使用位于 `blocked` 菱形框内部的独立小方框，避免相邻 Cell 标记粘连。

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

本地导入允许一次选择 stageXX.m 及同名 .dor/.stg、stage.ini、History.txt、heads.dat、stage_ini.xlsx。完整项目还应同时选择导出的 scenario/dor/history JSON：在已提供对应二进制时，它们只恢复右侧管理 UI 的快照，不会再次写入新增对象；单独导入 JSON 才按跨版本 Patch 处理。浏览器端会按 `stg.ksy` 已确认的 `u32 size + payload` 对象流解析本地 `.stg`，恢复势力、据点、主 Entity、五类可选 Entity、字段偏移和重建布局；因此只选择二进制项目时，新增据点及已加入剧本的武将也会出现在管理 UI 中。浏览器端同时解析本地 `stage.ini` 的全部主块和城池双块，按物理序号恢复母表行、49/17 个数值字段及其字节偏移，因此新增武将的 ini 页会匹配本地母表，而不是内置旧母表。导出优先使用本次导入的本地二进制。

`stage.ini` 按 `u32 size + payload` 块流管理。新增对象没有既有母表行时，母表行号与都市索引分别递增，并从合法模板继承全部数值字段；当前名称强制写入 20 字节标题/类型槽和 XLSX `title`。新增武将按人物 ID 顺序追加到全部既有主块之后，直接写入完整的 228 字节块（`size=224`）；新增城池直接插入 100 字节双块（`size=92` 主块加 `size=0` 次块），分别更新主块数和城池数；禁止按旧兼容视图的 224/76 字节步长补齐。只有旧 bundle 缺少块流布局时才阻断导出。

`stage.ini` 已有行只回写用户在 ini 页实际修改过的字段。新增行写入完整逻辑行；加载场景或只编辑 `.stg` 归属，不得把所有 `.stg` 当前值批量覆盖到已有母表。
导出按钮固定生成单个 `stageXX-export.zip`，归档内包含 `.m/.s/.x/.dor/.stg/stage.ini/History.txt/heads.dat`、工作簿和可用 Patch；不再逐文件触发下载。

## Patch 跨版本迁移

同一 Patch 内新增对象后的更新属于一个连续事务：新增据点、城门、History 行或 `stage.ini` 武将后，后续更新按 Patch 顺序合并，不再使用新增前的历史 `before` 对该 Patch 自身制造冲突。已有对象仍严格校验 `before`，保证跨版本导入不会覆盖外部修改。

编辑器导出的 `san-editor-patch-v1` 可以通过顶部“导入”重新加载。推荐迁移顺序：

1. 在新版本编辑器中加载目标版本的 `stageXX.m`，并同时选择 `stageXX.dor`、`stageXX.stg`、`stage.ini`、`History.txt` 等配套文件。
2. 再选择旧版本导出的 `stageXX_patch.json`；也可以把 `.m`、配套文件和 Patch JSON 一次选中。
3. 检查底部修改数量和校验页，再导出新的数据文件。

组合 Patch 保存地图 Cell、场景、城门、`History.txt` 和 `stage.ini` 武将修改。编辑器也兼容导入独立的 `san-editor-scenario-patch-v1`、`san-editor-dor-patch-v1`、`san-editor-history-patch-v1`。

导入使用 `before -> after` 冲突校验：当前值等于 `before` 时应用，等于 `after` 时视为已经应用；两者都不相等时整体拒绝该 Patch，不允许只落入部分数据域。导入后继续编辑同一字段时保留最初 `before`，只更新最终 `after`，确保下一版本仍能从原始基线重放。

## 运行时命令语义

- **定位**：只把主画布视口居中到当前 Cell、据点、城门或武将所属位置，不修改任何源文件或补丁。
- **恢复图层**：把当前选中 Cell 的当前编辑层恢复为导入基线值，并作为一次可撤销、可重做的真实编辑记录。
- **Raw 一键恢复**：把当前 Raw 记录的可编辑字段整体恢复为导入基线值；保留字段仍由模型约束，不直接改写。
- **校验**：只读检查字段范围、对象关系、计数镜像、母表布局和导出前置条件。校验不自动修复数据；存在阻断错误时禁止导出，并在校验页列出原因。

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
