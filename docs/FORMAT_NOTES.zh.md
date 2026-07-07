# 三国霸业二进制格式笔记（中文）

本文只保留当前仍然有效、且已经通过脚本、样本统计或 round-trip 验证的结论。

证据级别约定：

- `已确认`：已经有脚本、样本统计或回写验证支撑。
- `高置信推断`：已有较强证据，但字段命名或写回边界还未完全收口。
- `待验证`：目前只是方向，不能直接用于写回。

## 1. 文件角色总览

| 文件 | 当前理解 | 证据级别 |
| --- | --- | --- |
| `stageNN.m` | 地图主表，决定每个 cell 的地形、叠加、物件索引与附加字节 | 已确认 |
| `stageNN.s` | 固定 160x160 单字节网格，疑似小地图相关 sidecar | 高置信推断 |
| `stageNN.x` | 固定 160x160 单字节网格，比 `.s` 更像完整颜色缓存 | 高置信推断 |
| `stageNN.stg` | 关卡语义表，包含势力、城池、武将、士兵等记录 | 已确认 |
| `stageNN.evt` | 事件/脚本表，包含文本与控制命令混合记录 | 高置信推断 |
| `stageNN.spr` | 单位相关 sidecar，可为空 | 高置信推断 |
| `stageNN.dor` | 门、入口或通道相关 sidecar，可为空 | 高置信推断 |
| `kingdom.cel` | 地图图形资源容器 | 已确认 |
| `kingdom.atr` | `kingdom.cel` 的索引/属性伴随文件 | 已确认 |
| `stage.ini` | 全局二进制母表，不是文本 ini | 已确认 |

## 2. `.m`：地图主表

### 2.1 文件头

`.m` 文件头固定 16 字节：

```text
0x00: u32 width
0x04: u32 height
0x08: char[8] = "Hello1.0"
0x10: cell records ...
```

文件大小公式：

```text
16 + width * height * 16
```

### 2.2 每个 cell 的 16 字节记录

当前稳定理解如下：

| 偏移 | 类型 | 字段名      | 当前理解                                                            | 证据级别 |
| --- | --- |----------|-----------------------------------------------------------------| --- |
| `+0x00` | `int16` | `acwx`   | 基础地形 tile 索引                                                    | 已确认 |
| `+0x02` | `int16` | `acwy`   | 叠加/过渡 tile 索引，`-1` 表示空层                                         | 已确认 |
| `+0x04` | `int16` | `acwz`   | 建筑/物件 tile 索引，`-1` 表示空层                                         | 已确认 |
| `+0x06` | `u16` | `flags`  | reserved0 当前全量样本恒为 `0`，可视作填充/保留字节                               | 高置信推断 |
| `+0x08` | `u8` | `byte08` | land_water_hint 多数用于陆地/水面交界与码头一类切换点，辅助在陆地模型与水上模型之间切换；但仍有少量码头未标记 | 高置信推断 |
| `+0x09` | `u8` | `byte09` | blocked 通行标记：`0` 可通行、`1` 不可通行；常见于城墙、山寨、水陆交界、森林、山石等不可通行区         | 已确认 |
| `+0x0A` | `u8` | `byte10` | site_trigger 城池、山寨等建筑触发范围；`byte10=239` 表示城门                     | 已确认 |
| `+0x0B` | `u8` | `byte11` | site_area 进入城池、山寨、军寨的触发范围编号；同一目标区域共用同一 id                       | 高置信推断 |
| `+0x0C` | `u8` | `byte12` | reserved1 当前全量样本恒为 `0`，可视作填充/保留字节                               | 已确认 |
| `+0x0D` | `u8` | `byte13` | minimap_color 小地图渲染颜色索引                                         | 已确认 |
| `+0x0E` | `u8` | `byte14` | reserved2 当前全量样本恒为 `0`，可视作填充/保留字节                               | 已确认 |
| `+0x0F` | `u8` | `byte15` | reserved3 当前全量样本恒为 `0`，可视作填充/保留字节                               | 已确认 |

结论：地图编辑器不能只保存三层索引，必须完整保留 16 字节记录，才能安全 round-trip。

## 3. `kingdom.cel/.atr`：地图图形资源

### 3.1 图层角色

- `acwx`：基础地形，决定地表主体。
- `acwy`：叠加层，常见于道路、边缘过渡、水边修饰等。
- `acwz`：建筑和大物件层，包含城池、关隘、树木等需要额外 z-order 处理的资源。

### 3.2 渲染网格

当前渲染器与 `Emperor.exe` 的实际画面已经可以稳定对齐，核心网格是 staggered isometric：

```text
screen_x = col * 40 + (20 if row is odd else 0)
screen_y = row * 10
```

已确认信息：

- 地表 tile 目标尺寸可按 `40x20` 处理。
- 最终游戏渲染不是单纯的大菱形拼图，而是受实际视口、遮挡和对象层顺序约束。
- `acwz` 仍需继续补完完整 footprint 与细粒度 z-order。

## 4. `stage.ini`：全局二进制母表

### 4.1 文件布局

当前回写链路依赖的稳定布局是：

```text
8 字节文件头
+ 277 * 224 字节主表
+ 174 * 76 字节尾表
```

现有脚本：

- `tools/export_stage_ini_tables.py`
- `tools/build_stage_ini.py`
- `tools/export_stage_ini_txt_workbook.py`
- `tools/import_stage_ini_txt_workbook.py`
- `tools/build_stage_ini_from_txt_workbook.py`

这些脚本已经能在未修改工作簿的情况下回写出与原始 `stage.ini` 字节完全一致的新文件。

### 4.2 与 `uft8-game-txt/` 的映射

当前已经确认的稳定映射：

| 文本文件 | 步长/组织方式 | 用途 |
| --- | --- | --- |
| `general.txt` | `57 dwords` 一组 | 武将主表原型 |
| `castle.txt` | `25 dwords` 一组 | 城池主表原型 |
| `magic.txt` | `19 dwords` 一组 | 技能/法术原型 |
| `soldier.txt` | `20 dwords` 一组 | 兵种原型 |
| `History.txt` | 辅助对照 | 主要用于比对，不直接参与自动回写 |

### 4.3 工作簿契约

`stage_ini_conversion_tables.xlsx` 是面向回写的纯转换工作簿，原则如下：

- 只保留 `row_id`、`title` 和必要业务列。
- 不把分析中间列、推断列混进转换链路。
- 未修改工作簿时，回写结果必须与原文件字节一致。

## 5. `.stg`：关卡语义表

### 5.1 当前稳定文件外形

`.stg` 当前以 EXE 对象流模型为准，不再使用早期“8 字节头 + 76 字节记录”的格式作为主结论。

```text
u32 present_or_version
Block root_part1 = u32 size + payload[0x48 或 0x4C]
Block root_part2 = u32 size + payload[0x34]
u32 force_count
Force * force_count
  Block force_part1 = u32 size + payload[0x60]
  Block force_part2 = u32 size + payload[0x7C 或 0x84]
  u32 site_list_pre_count_or_flag
  Site * force_part2.site_count
    Block site_part1 = u32 size + payload[0x58 或 0x5C]
    Block site_part2 = u32 size + payload[0x2B0]
    u32 primary_entity_count
    Entity * primary_entity_count
      Block entity_part1 = u32 size + payload[0x30 或 0x34]
      Block entity_part2 = u32 size + payload[0xE0]
    optional Entity blocks controlled by site_part2 +0x27C..+0x28C flags
after_forces_tail
```

每个 `Block` 的 `size` 都只表示 payload 长度，不包含 size 字段自身。当前 `src/san_tools/ksy/stg.ksy` 已按这个模型维护。

### 5.2 样本覆盖与验证

当前已用同一套块流规则验证 42 个 `.stg` 样本：

- 原版 `三国霸业/stage00.stg`、`stage01.stg` 到 `stage45.stg` 中存在的全部样本。
- 非原版 `三国霸业/SGBY_MAP/new_san/stage01.stg` 到 `stage04.stg`。
- `三国霸业/new-stage01.stg`。

验证结论：

- 42 个样本都能按块流结构走完整个文件边界。
- 42 个样本都能通过 `src/san_tools/codecs/stg_stream_codec_refactored.py` 做 byte-for-byte roundtrip。
- `new_san` 的 4 个大剧本使用同一结构，只是据点数量、实体数量和尾区长度不同。

### 5.3 已确认字段映射

`root_part1`：

- `+0x00..+0x0F` 是 Big5 定长剧本名。
- `+0x1C` 是剧本起始年份。
- `+0x20` 是剧本结束年份/关卡结束年。
- `+0x30` 是剧本 ID，通常与 `stageNN` 编号一致。
- `+0x34` 是剧本 ID 镜像或子编号，剧情剧本常与 `+0x30` 相同。

`root_part2`：

- `+0x14` 是势力数量镜像候选，当前样本通常等于顶层 `force_count`。

`force_part1` / `force_part2`：

- `force_part1 +0x00..+0x13` 是 Big5 定长势力名。
- `force_part1 +0x14` 是 1-based 势力序号候选。
- `force_part1 +0x18` 是君主/代表武将人物编号候选。
- `force_part2 +0x00` 是该势力拥有的据点数量，EXE 按此值循环读取 `Site`。
- `force_part2 +0x04` 是 1-based 势力序号镜像候选。

`site_part1`：

- `+0x00..+0x13` 是 Big5 定长据点名。
- `+0x14` 起与 `castle.txt` 数值列对齐：都市索引、房子属性、城规模、人口、金、粮、待命士兵、开发/商业/治安、上限、坐标、太守、武将。
- 0x5C 版本比 0x58 版本多一个尾部保留 `u32`，回写时应保留原值。

`site_part2`：

- `+0x27C`、`+0x280`、`+0x284`、`+0x288`、`+0x28C` 是可选 Entity 控制 flag，非 0 时在主实体列表后追加一个 `Entity`。
- `+0x2AC` 是额外 Entity 数量候选；当前 42 个样本中为 0。
- 其余区域按运行态/AI 保留 `u32` 处理，不清零、不重排。

`entity_part1` / `entity_part2`：

- `entity_part1 +0x00` 是运行时所属势力序号候选。
- `entity_part2 +0x00..+0x13` 是 Big5 定长实体名。
- `entity_part2 +0x14` 起与 `general.txt` 数值列对齐：人物编号、头像编号、所属君主、所在地、统御、兵种、等级、带兵数、武力、智力、忠诚、经验、技能位、AI 方针、最大带兵/武力/智力等。
- `entity_part2 +0xD8/+0xDC` 是 `general.txt` 未覆盖的尾部保留字段。

### 5.4 尾区规则

主对象流结束后的 `after_forces_tail` 不是固定长度：

- 若尾区大于 `0xA0`，当前按“前置尾区 + 最后 `0xA0` 字节候选尾块”保留。
- 若尾区小于或等于 `0xA0`，则整个尾区都作为小尾块保留。
- 尾区全部按 4 字节对齐的 `u32` words 保存；大剧本尾区中可检测到 entity-like 片段，但完整列表逻辑尚未完全收口，因此不应自动重排或重算。

### 5.5 旧 76 字节工作簿链路的适用范围

`tools/export_stg_workbook.py` / `tools/import_stg_workbook.py` 的 76 字节记录工作簿仍可作为 `stage01.stg` 的局部编辑兼容链路使用，尤其是 `city_state` 中已确认的候选字段回写。

但它现在不是 `.stg` 的主格式定义：

1. 新增结构定义、文档和 Kaitai 描述应以块流模型为准。
2. 旧工作簿的 `raw_records.raw_hex` 只能视为兼容导出视图。
3. 未解字段仍必须保持原始字节，不能按 76 字节视图重算对象边界。
4. 若后续扩展编辑器写回 `.stg`，优先接入 `src/san_tools/codecs/stg_stream_codec_refactored.py` 的块流 roundtrip 能力。

## 6. `.evt/.spr/.dor/.s/.x`：sidecar 现状

### `.evt`

- 当前最稳的结构观察是：8 字节头 + 72 字节记录体。
- 已新增 `tools/analyze_evt_resources.py`，会把全量统计写入 `derived/sidecar_analysis/evt_resource_linkage.json`。
- 全量结果显示：38 个 `.evt` 都能对上对应 `TalkNN.txt`，说明 `TalkNN.txt` 可以视为事件文本资源池。
- `stage17.txt` 是可读的 CP950 松散脚本原型，能和 `stage17.evt` 中的 `呂翔死`、`徐庶回軍寨`、`碼頭` 等标签互相印证。
- `stage01.txt` 不是普通文本，而是二进制 blob；不能把所有 `stageNN.txt` 都当成剧情脚本。
- 当前最稳定的 ASCII 命令 token 是 `talk`、`VIEW`、`MAP`、`MAPALL`、`MOVE`、`TIME`、`TIMEOVER`。
- `新增流程`、`流程`、`y程` 这类内容大量来自命令区与文本解码重叠，不能直接视为稳定字段名。
- 仅凭“小整数也落在 Talk 段号空间内”还不能认定它就是文本引用；坐标引用、对象引用和全局 id 仍需继续收口。

### `.spr`

- 与单位或战场对象有关。
- 可为空。

### `.dor`

- 文件头固定为 ASCII `Door    Data` + `u32 record_size`，当前已确认 `record_size = 0x3C`。
- 头后按“分组”组织：`u32 count` + `count * 0x3C` 记录，遇到 `count = 0` 结束，不是先前猜测的单一平铺记录区。
- `src/san_tools/analysis/analyze_dor.py` 当前已稳定导出以下字段：`group/index`、`door_x`、`door_y = raw[1] * 2 + 4`、`dir`、`site_x`、`site_y`、`unk_28`、`unk_2c`、`extra`、`raw`。
- 当前可把一个 group 视为同一据点下的一组城门记录，后续可以继续与 `.stg` 中的据点坐标做归属绑定。
- `Emperor.exe` 里，`.spr/.dor/.evt` 与 `.m/.s/.x` 仍分属两组扩展名引用簇，说明 `.dor` 是与 `.m` 并列的关卡 sidecar。
- 可为空。

### `.s/.x`

- 两者大小都固定为 `160 * 160 = 25600` 字节。
- 已新增 `tools/analyze_minimap_sidecars.py`，会把全量统计写入 `derived/sidecar_analysis/minimap_sidecar_analysis.json`。
- 已新增 `tools/build_minimap_sidecars.py`，按当前最稳的规则把 `.m` 转回 `.s/.x`：上 `128` 行由 `.m` 的 `byte13 / minimap_color` 缩放生成，下 `32` 行直接保留原始 sidecar 尾区。
- 已更新 `tools/apply_editor_patch.py`，编辑器 patch 写回 `.m` 后会默认同步生成同名 `.s/.x`，闭环沿用同一套“上 128 行派生、下 32 行保留”的保守规则。
- 已更新 `tools/export_editor_bundle.py` 与编辑页模板：导出的 `stage.json` 会携带 `.s/.x` 尾区参考，编辑页侧边栏固定为 `Minimap -> Cell -> Record -> Resources -> Stage`，并支持直接一键导出 `.m/.s/.x`。
- 在 33 个带 `.m/.s/.x` 的关卡里，`.s` 与 `.x` 平均仍有 `0.80094` 的逐字节相同率，说明二者高度相关。
- 若只比较有效区，上 `128` 行中，`.m byte13/minimap_color -> 160x128` 与 `.s/.x` 的平均匹配率分别为 `0.47098 / 0.620744`；`.x` 明显更接近 `.m` 派生结果。
- 若采用“上 128 行派生 + 下 32 行保留”的保守写回策略，生成结果与原始 `.s/.x` 的平均全图匹配率分别为 `0.576784 / 0.696596`，且尾区匹配率恒为 `1.0`。
- 跨关卡统计里，第 `128..141` 行和 `150..159` 行都出现了 `>= 0.95` 的静态一致度，`159` 行达到 `1.0`，说明底部存在明显公共尾区或缓存区。
- 当前可以把 `.s/.x` 视为“顶部有效缩略图 + 底部公共尾区/缓存区”的组合；但它们是否还叠加了 `Emperor.exe` 内的额外调色、标记或压缩流程，仍需继续确认。

## 7. 写回策略

当前统一采用“保底原始字节 + 局部覆写”的策略：

1. 优先保留原始记录。
2. 只修改已经确认偏移的字段。
3. 未确认字段不重算、不清零、不移位。
4. 所有导入脚本都必须支持与原文件逐字节比较。
5. `.m` 相关闭环在能够重建 sidecar 时，也优先保留原始 `.s/.x` 尾区，只覆写已经确认的顶部有效区。

这是目前最稳妥、也最适合继续逆向扩展的方案。

## 8. 当前未解问题

1. `.m` 中 `flags` 的最终语义，以及 `byte08` 那些未被标记的码头/水陆交界是否还受其他字段或资源兜底。
2. `.stg` 城池块和士兵块里剩余未命名字段的完整含义。
3. `.evt` 如何引用地图坐标、对象和全局 id。
4. 根据 `.dor` 的 `site_x/site_y` 与 `.stg` 的城池坐标建立稳定的“城门 -> 据点”归属表，并接入编辑器联动。
5. 为什么 `.x` 在顶部有效区里始终比 `.s` 更接近 `.m` 派生结果，以及 `Emperor.exe` 是否还会做额外调色、标记或压缩。
