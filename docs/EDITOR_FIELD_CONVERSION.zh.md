# 地图编辑器字段级转换

本文档记录编辑器模型与 `.m/.dor/.stg/stage.ini/History.txt` 的字段级转换。`.m/.dor/.stg` 的结构仅以 `src/san_tools/ksy/` 为准；保留字段始终保留原始字节。

## CRUD 接口

| 文件 | 查询 | 新增 | 修改 | 删除 |
|---|---|---|---|---|
| `.m` | `recordAt` 按 `row * width + col` 读取 | 地图尺寸固定，不新增 Cell | `applyChangeSet` | 不删除 Cell，只恢复原值 |
| `.dor` | `parseDorBytes` | `addSiteGate` | `updateGateField` | `deleteSiteGate`，重建组计数 |
| `.stg` | `scenarioRows` | 新增 Force/Site/Entity 后重建对象流 | `updateScenarioField` | `markScenarioDeleted`，重建时排除 |
| `stage.ini` | `stageIniGeneralRows`、`stageIniSiteRows` | 按 `appendLayout` 插入逻辑行 | 按 `fieldLocations` 写回 dword | 新行直接移除；旧武将统御归零，保持 ID 稳定 |
| `History.txt` | `historyTableRows` | `ensureHistoryRow` | `updateHistoryField` | `deleteHistoryRow` |

## `.m`

文件头依次是 `width:u4`、`height:u4`、`Hello1.0`。之后按 Y 优先、X 次优顺序保存 `width * height` 个 16 字节 Cell。

| Cell 偏移 | 字段 | 类型 | 转换与写回 |
|---:|---|---|---|
| `+0x00` | `acwx` | `s2` | 基础地形，小端有符号 16 位 |
| `+0x02` | `acwy` | `s2` | 叠加层，`-1` 表示空 |
| `+0x04` | `acwz` | `s2` | 物件层，`-1` 表示空 |
| `+0x06` | `reserved0` | 固定 2 字节 0 | 只读 |
| `+0x08` | `terrain_tag` | `u1` | 地形标记，0..255 |
| `+0x09` | `blocked` | `u1` | 阻挡标记，0..255 |
| `+0x0A` | `site_trigger` | `u1` | 据点势力范围，0..255 |
| `+0x0B` | `site_area` | `u1` | 据点核心区域，0..255 |
| `+0x0C` | `reserved1` | 固定 1 字节 0 | 只读 |
| `+0x0D` | `minimap_color` | `u1` | SAN 调色板索引；通过 bundle 的 minimapPalette 映射 SAN_RGB_PALETTE，再按主画布世界坐标等比投影后重建小地图 |
| `+0x0E` | `reserved2` | 固定 2 字节 0 | 只读 |

## `.dor`

文件头是 `Door    Data` 与 `record_size:u4`。每组先保存 `record_count:u4`，再保存记录。

| 偏移 | KSY 字段 | 编辑器字段 | 转换与写回 |
|---:|---|---|---|
| `+0x00` | `door_x` | `doorX` | `u4` |
| `+0x04` | `door_y` | `doorY` | 原始值读取为 `raw * 2 + 4`，写回执行逆转换 |
| `+0x08` | `door_ori` | `dir` | 0 朝右，1 朝左 |
| `+0x0C..+0x2C` | `reserved0[0..8]` | 不公开 | 9 个 `u4`，原值保留 |
| `+0x30` | `site_x` | `siteX` | 只读镜像当前据点 `coord_x` |
| `+0x34` | `site_y` | `siteY` | 只读镜像当前据点 `coord_y` |
| `+0x38` | `reserved1` | 不公开 | 原值保留 |

`group` 是外层组序号，`doorIndex` 是组内序号，都不是记录字段。增删后重新计算组计数和顺序。

## `.stg` Force

| 区块偏移 | 字段 | 写回规则 |
|---:|---|---|
| `force_part1 +0x00` | `force_name` | Big5 定长 20 字节 |
| `force_part1 +0x14` | `force_slot_or_index_14` | `u4` |
| `force_part1 +0x18` | `force_lord_person_id` | `u4` |
| `force_part2 +0x00` | `site_count` | 由未删除据点数计算 |
| `force_part2 +0x04` | `force_index_1based` | 由对象流顺序计算 |
| `force_part2 +0x08` | `force_lord_person_id_or_ref` | 与君主引用同步 |

其他 Force 字段严格按 `stg.ksy` 原值保留。

## `.stg` Site

`site_part1` 的名称占 20 字节，从 `+0x14` 起每 4 字节一个 `s4`。

| 偏移 | 字段 | stage.ini 列 |
|---:|---|---|
| `+0x00` | `site_name` | `title` |
| `+0x14` | `city_index` | 都市索引 |
| `+0x18` | `house_attr` | 房子属性 |
| `+0x1C` | `castle_scale` | 城规模 |
| `+0x20` | `population` | 人口 |
| `+0x24` | `gold` | 金 |
| `+0x28` | `food` | 粮 |
| `+0x2C` | `standby_soldier` | 待命士兵 |
| `+0x30` | `develop` | 开发值 |
| `+0x34` | `commerce` | 商业值 |
| `+0x38` | `security` | 治安值 |
| `+0x3C` | `develop_limit` | 开发上限 |
| `+0x40` | `commerce_limit` | 商业上限 |
| `+0x44` | `security_limit` | 治安上限 |
| `+0x48` | `coord_x` | 座标X |
| `+0x4C` | `coord_y` | 座标Y |
| `+0x50` | `governor` | 太守 |
| `+0x54` | `general_count_or_slot` | 武将 |

新增 Site 同步设置 `site_part2 +0x004 runtime_coord_or_spawn_x_004 = coord_x + 1`、`+0x008 runtime_coord_or_spawn_y_008 = floor(coord_y / 2) + 5`、`+0x00C site_kind_or_force_group_00c = 父势力序号`、`+0x010 site_serial_010 = 全局据点序号`。

## `.stg` Entity

`entity_part2 +0x00` 是 Big5 定长 20 字节名称。从 `+0x14` 起，以下字段严格按列顺序连续保存为 `s4`：

| 偏移范围 | 字段顺序 |
|---|---|
| `+0x14..+0x40` | `person_id`、`portrait_id`、`static_owner_id`、`static_location_id`、`command`、`soldier_type_id`、`level`、`troop_count`、`martial_force`、`intellect`、`loyalty`、`experience` |
| `+0x44..+0x68` | `skill_fire_1..3`、`skill_stone_1..3`、`skill_thunder_1..3`、`skill_slash_1` |
| `+0x6C..+0x90` | `skill_slash_2..3`、`skill_spear_1..3`、`skill_arrow_1..3`、`skill_persuade`、`skill_inspire` |
| `+0x94..+0xB8` | `skill_shout`、`skill_confuse`、`special_skill`、`action_state`、`imprisoned_flag`、`loaded_flag`、`attribute`、`self_ref`、`alert_ai`、`chase_ai` |
| `+0xBC..+0xD4` | `retreat_ai`、`action_policy`、`ambush_field`、`betrayal_force_id`、`max_troop_count`、`max_martial_force`、`max_intellect` |
| `+0xD8/+0xDC` | `reserved_d8`、`reserved_dc`，原值保留 |

`entity_part1 +0x00..+0x20` 是保留零区，`+0x24/+0x28/+0x2C` 保留运行状态。0x34 字节版本的 `+0x30 runtime_force_or_ai_side_30` 在新增时按父势力 1-based 序号初始化。

## `stage.ini`

文件起始为 `main_count:u4`，后续所有对象使用 `size:u4 + payload[size]`。第二个 DWORD 是第一条主块的 `size=224`，不是全局 `main_stride`。

- 普通武将块共 228 字节：`+0x00 size=224`，`+0x04..+0x17` 为 20 字节 Big5 标题/类型槽，`+0x18..+0xDB` 为 49 个连续小端 `u4`，`+0xDC/+0xE0` 分别镜像“最大武力/最大智力”。
- 武将 49 列依次为：人物编号、头像编号、所属君主、所在地、统御力、兵种号、等级、带兵数、武力、智力、忠诚值、经验值、火系 3 列、石系 3 列、雷系 3 列、斩系 3 列、枪系 3 列、箭系 3 列、说服、鼓舞、大喝、迷惑、必杀、行动状态、被关、读取、属性、参照自己、警戒、追捕、撤退、行动方针、伏兵、叛变国 ID、最大带兵、最大武力、最大智力。
- 主块流之后是 `city_count:u4`。每座城池共 100 字节：`+0x00 size=92`，`+0x04` 为保留前导值，`+0x08..+0x1B` 为 20 字节 Big5 标题/类型槽，`+0x1C..+0x5F` 为 17 个连续小端 `u4`，`+0x60 size=0` 为次块。
- 城池 17 列依次为：都市索引、房子属性、城规模、人口、金、粮、待命士兵、开发值、商业值、治安值、开发上限、商业上限、治安上限、座标X、座标Y、太守、武将。

已有行按 `fieldLocations[表][row_id][列].byteOffset` 原位写回。新增行号与业务索引分离，城池标题取当前 `site_name`，未直接编辑的数值列从合法模板继承。新增武将按 228 字节完整块追加到全部既有主块末尾，并更新文件起始的 `main_count`；游戏以主块 1-based 物理序号解释人物 ID，因此不得插在特殊武将块之前；新增城池按 100 字节双块插入城池区末尾，并在主块插入位移后的 `city_count` 位置更新计数。两类记录均不做步长补齐，后续未知块逐字节保留。

## `History.txt`

`History.txt` 是 CP950 制表符分隔表。第一行 `rawHeaders` 原样保留，数据列按 `headers` 原顺序写回，行尾统一为 CRLF。

- 主键列依次匹配 `編號/编号/人物編號/人物编号`。
- 名称列依次匹配 `武將名/武将名/姓名/名稱/名称`。
- 其他列不猜测语义，直接使用原表头作为字段名。
- 新增行先把所有列初始化为 0，再写入人物 ID 与名称；删除行从输出集合移除。

## Patch 转换

组合 Patch 保存 `.m` Cell、`.dor` 城门、`.stg` 场景、`stage.ini` 武将母表和 `History.txt` 行级变化。新增使用 `op=add` 和完整 `after`，修改使用字段级 `before/after`，删除使用 `op=delete`。导入先完成全部冲突检查，再原子应用。