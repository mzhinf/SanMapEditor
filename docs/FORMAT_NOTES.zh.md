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
| `stageNN.dor` | 城门分组与记录表，可为空 | 已确认 |
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

字段名称、类型和顺序严格对应 `src/san_tools/ksy/m.ksy`：

| 偏移 | 类型 | KSY 字段 | 当前理解 | 证据级别 |
| --- | --- | --- | --- | --- |
| `+0x00` | `s2` | `acwx` | 基础地形 tile 索引 | 已确认 |
| `+0x02` | `s2` | `acwy` | 叠加/过渡 tile 索引，`-1` 表示空层 | 已确认 |
| `+0x04` | `s2` | `acwz` | 建筑/物件 tile 索引，`-1` 表示空层 | 已确认 |
| `+0x06` | `bytes[2]` | `reserved0` | 固定零保留区 | 已确认 |
| `+0x08` | `u1` | `terrain_tag` | 地形标签；已开放字段级编辑，完整游戏语义仍需验证 | 高置信推断 |
| `+0x09` | `u1` | `blocked` | 通行阻挡标记 | 已确认 |
| `+0x0A` | `u1` | `site_trigger` | 据点触发范围；现有样本中 `239` 常用于城门 | 已确认 |
| `+0x0B` | `u1` | `site_area` | 据点核心区域编号 | 高置信推断 |
| `+0x0C` | `bytes[1]` | `reserved1` | 固定零保留区 | 已确认 |
| `+0x0D` | `u1` | `minimap_color` | 小地图调色板索引 | 已确认 |
| `+0x0E` | `bytes[2]` | `reserved2` | 固定零保留区 | 已确认 |

结论：地图编辑器不能只保存三层索引，必须按上述顺序完整保留 16 字节记录，才能安全 round-trip。

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

游戏有效样本确认的物理布局是：

```text
main_count:u4
+ main_count 个 (size:u4 + payload[size]) 主块
+ city_count:u4
+ city_count 个城池双块：主块 (size=92 + payload) + 次块 (size=0)
+ 其余全局资源块
```

`data/game/stage.ini` 中 `main_count=277`，277 个主块的 `size` 均为 224，主块流结束及 `city_count` 偏移为 63160；`city_count=42`，城池双块结束于 67364。前 272 个主块映射普通武将，余下 5 个主块仍是人物 ID 273..277 的特殊武将。新增人物 ID 278 起必须追加在这 277 个主块之后，保证内部人物编号、`.stg` 引用与主块 1-based 物理序号一致。旧解析器使用“8 字节头、224 字节主视图、76 字节尾视图”实现兼容工作簿和字节一致回写，但该视图不是新增对象时可使用的物理记录边界。

现有脚本：

- `python -m san_tools run export-stage-ini-json`
- `python -m san_tools run build-stage-ini`
- `python -m san_tools run export-stage-ini-workbook`
- `python -m san_tools run import-stage-ini-workbook`
- `python -m san_tools run build-stage-ini-from-workbook`

这些脚本已经能在未修改工作簿的情况下回写出与原始 `stage.ini` 字节完全一致的新文件。

### 4.2 与 `data/text` 文本表的映射

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

- 原版 `stage00.stg`、`stage01.stg` 到 `stage45.stg` 中存在的全部样本。
- 扩展样本 `new_san/stage01.stg` 到 `stage04.stg`。
- 用户扩展样本 `new-stage01.stg`。

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

- `+0x058..+0x130` 是 AI/行动模板参数表。
- `+0x134..+0x20C` 是固定零保留带。
- `+0x210..+0x278` 是运行时状态字段组，回写时保留。
- `+0x27C`、`+0x280`、`+0x284`、`+0x288`、`+0x28C` 是可选 Entity 控制 flag，非 0 时在主实体列表后追加一个 `Entity`。
- `+0x2AC` 在当前 42 个样本中固定为 `0`，是保留字段，不作为额外 Entity 数量解析。

`entity_part1` / `entity_part2`：

- `entity_part1 +0x00..+0x20` 是固定零保留/填充区，不是运行时所属势力。
- `entity_part1 +0x24/+0x28/+0x2C` 是运行时字段，回写时保留。
- `entity_part1 +0x30` 只存在于 `0x34` 字节变体，是运行时势力/AI 阵营候选，但不保证等于父 Force 序号。
- `entity_part2 +0x00..+0x13` 是 Big5 定长实体名。
- `entity_part2 +0x14` 起与 `general.txt` 数值列对齐：人物编号、头像编号、所属君主、所在地、统御、兵种、等级、带兵数、武力、智力、忠诚、经验、技能位、AI 方针、最大带兵/武力/智力等。
- `entity_part2 +0xD8/+0xDC` 是 `general.txt` 未覆盖的尾部保留字段。

### 5.4 尾区规则

主对象流结束后的 `after_forces_tail` 不是固定长度：

- 若尾区大于 `0xA0`，当前按“前置尾区 + 最后 `0xA0` 字节候选尾块”保留。
- 若尾区小于或等于 `0xA0`，则整个尾区都作为小尾块保留。
- 尾区全部按 4 字节对齐的 `u32` words 保存；大剧本尾区中可检测到 entity-like 片段，但完整列表逻辑尚未完全收口，因此不应自动重排或重算。

### 5.5 旧 76 字节工作簿链路的适用范围

`export-stg-workbook` 与 `import-stg-workbook` 命令导出的 76 字节记录工作簿仍可作为 `stage01.stg` 的局部编辑兼容链路使用，尤其是 `city_state` 中已确认的候选字段回写。

但它现在不是 `.stg` 的主格式定义：

1. 新增结构定义、文档和 Kaitai 描述应以块流模型为准。
2. 旧工作簿的 `raw_records.raw_hex` 只能视为兼容导出视图。
3. 未解字段仍必须保持原始字节，不能按 76 字节视图重算对象边界。
4. 若后续扩展编辑器写回 `.stg`，优先接入 `src/san_tools/codecs/stg_stream_codec_refactored.py` 的块流 roundtrip 能力。

## 6. `.evt/.spr/.dor/.s/.x`：sidecar 现状

### `.evt`

- 当前最稳的结构观察是：8 字节头 + 72 字节记录体。
- 已新增 `python -m san_tools run analyze-evt-resources`，会把全量统计写入 `derived/sidecar_analysis/evt_resource_linkage.json`。
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
- 已新增 `python -m san_tools run analyze-minimap-sidecars`，会把全量统计写入 `derived/sidecar_analysis/minimap_sidecar_analysis.json`。
- 已新增 `python -m san_tools run build-minimap-sidecars`，按当前最稳的规则把 `.m` 转回 `.s/.x`：上 `128` 行由 `.m` 的 `minimap_color` 缩放生成，下 `32` 行直接保留原始 sidecar 尾区。
- 已更新 `python -m san_tools run apply-editor-patch`，编辑器 patch 写回 `.m` 后会默认同步生成同名 `.s/.x`，闭环沿用同一套“上 128 行派生、下 32 行保留”的保守规则。
- `export-editor-bundle` 导出的 `stage.json` 会携带 `.s/.x` 尾区参考；编辑器导出沿用同一套保守生成规则。
- 在 33 个带 `.m/.s/.x` 的关卡里，`.s` 与 `.x` 平均仍有 `0.80094` 的逐字节相同率，说明二者高度相关。
- 若只比较有效区，上 `128` 行中，`.m minimap_color -> 160x128` 与 `.s/.x` 的平均匹配率分别为 `0.47098 / 0.620744`；`.x` 明显更接近 `.m` 派生结果。
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

1. `.m` 中 `terrain_tag` 的完整游戏语义，以及少量未标记码头/水陆交界是否还受资源或其他字段影响。
2. `.stg` 据点块和实体块中剩余未命名字段的完整含义。
3. `.evt` 如何引用地图坐标、对象和全局 ID。
4. 为什么 `.x` 在顶部有效区里始终比 `.s` 更接近 `.m` 派生结果，以及 `Emperor.exe` 是否还会做额外调色、标记或压缩。
