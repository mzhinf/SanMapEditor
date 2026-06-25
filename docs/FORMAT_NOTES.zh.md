# 三国霸业二进制格式笔记（中文）

本文只保留当前仍然有效、且已经通过脚本或样本验证的结论。
每条结论尽量标明证据级别：

- `已确认`：已经有脚本、样本统计或 round-trip 支撑。
- `高置信推断`：已有较强证据，但还没完成最终字段命名。
- `待验证`：目前只是方向，不应直接用于写回。

## 1. 文件角色总览

| 文件 | 当前理解 | 证据级别 |
| --- | --- | --- |
| `stageNN.m` | 地图主表，决定每个 cell 的地形/叠加/物件索引与附加字节 | 已确认 |
| `stageNN.s` | 固定 160x160 单字节网格，疑似小地图/缓存/遮罩伴随层 | 高置信推断 |
| `stageNN.x` | 固定 160x160 单字节网格，较 `.s` 更像完整颜色缓存 | 高置信推断 |
| `stageNN.stg` | 关卡语义表，包含城池/势力/武将/兵种等实体记录 | 高置信推断 |
| `stageNN.evt` | 事件/脚本表，包含目标、提示、对话与控制命令 | 高置信推断 |
| `stageNN.spr` | 单位/士兵相关 sidecar，可为空 | 高置信推断 |
| `stageNN.dor` | 门/入口/通道相关 sidecar，可为空 | 高置信推断 |
| `kingdom.cel` | 地图图形资源容器 | 已确认 |
| `kingdom.atr` | `kingdom.cel` 的属性/索引伴随表 | 已确认 |
| `stage.ini` | 全局二进制母表，不是文本 ini | 已确认 |

## 2. `.m`：地图主表

### 2.1 文件头

`.m` 文件头固定 16 字节：

| 偏移 | 类型 | 含义 | 证据级别 |
| --- | --- | --- | --- |
| `0x00` | `u32` little-endian | 地图宽度（cell） | 已确认 |
| `0x04` | `u32` little-endian | 地图高度（cell） | 已确认 |
| `0x08` | `char[8]` | 固定魔数 `Hello1.0` | 已确认 |
| `0x10` | `record[]` | 紧接 cell 记录区 | 已确认 |

文件大小公式：

```text
16 + width * height * 16
```

### 2.2 每个 cell 的 16 字节记录

| cell 内偏移 | 类型 | 字段名 | 当前理解 | 证据级别 |
| --- | --- | --- | --- | --- |
| `+0x00` | `int16` | `acwx` | 基础地形 tile 索引 | 已确认 |
| `+0x02` | `int16` | `acwy` | 叠加/过渡 tile 索引，`-1` 表示无 | 已确认 |
| `+0x04` | `int16` | `acwz` | 建筑/物件索引，`-1` 表示无 | 已确认 |
| `+0x06` | `int16` | `word06` | 当前样本基本为 0 | 已确认存在，语义待定 |
| `+0x08` | `u8` | `byte08` | 少量非零的辅助标志 | 待验证 |
| `+0x09` | `u8` | `byte09` | 0/1 分布明显，疑似通行/遮挡候选位 | 高置信推断 |
| `+0x0A` | `u8` | `byte10` | 物件/地形类别候选位；EXE 中有 `0x65..0x6E` 比较 | 高置信推断 |
| `+0x0B` | `u8` | `byte11` | footprint 子索引候选位；在部分关卡呈 36 格分组 | 高置信推断 |
| `+0x0C` | `u8` | `byte12` | 多数为 0 | 待验证 |
| `+0x0D` | `u8` | `final_palette` | 最终缓存/小地图相关颜色索引候选位 | 高置信推断 |
| `+0x0E` | `u8` | `byte14` | 多数为 0 | 待验证 |
| `+0x0F` | `u8` | `byte15` | 多数为 0 | 待验证 |

结论：地图编辑器不能只保存三层索引，必须完整保留 16 字节记录，才能安全 round-trip。

## 3. `kingdom.cel/.atr`：地图图形资源

### 3.1 图层分工

| 图层 | 当前理解 | 证据级别 |
| --- | --- | --- |
| `acwx` | 基础地形层 | 已确认 |
| `acwy` | 道路、岸线、边缘、过渡等叠加层 | 已确认 |
| `acwz` | 建筑、树木、城池等物件层 | 已确认 |

### 3.2 渲染方式

- `acwx/acwy` 不是直接的 20x20 方块，而是 packed diamond scanline。
- 真实地面 tile 目标尺寸是 `40x20`。
- 当前已经恢复的屏幕坐标变换：

```text
screen_x = col * 40 + (20 if row is odd else 0)
screen_y = row * 10
```

这不是传统完整菱形棋盘，而是 staggered isometric 网格。

### 3.3 `acwz` 锚点

`acwz` 资源头至少包含：

| 偏移 | 类型 | 含义 | 证据级别 |
| --- | --- | --- | --- |
| `+0x00` | `u32` | `xAnchor` | 已确认 |
| `+0x04` | `u32` | `yAnchor` | 已确认 |
| `+0x08` | `u32` | `width` | 已确认 |
| `+0x0C` | `u32` | `height` | 已确认 |
| `+0x10` | `u32` | 临时指针/未知 | 待验证 |

当前渲染器使用的放置公式：

```text
dest_x = tile_screen_x + 20 - xAnchor
dest_y = tile_screen_y + 20 - yAnchor
```

这已经能与 `stage11.png` 的真实游戏截图较好对齐，但 `acwz` 的完整 z-order / footprint 还没有完全收口。

## 4. `stage.ini`：全局二进制母表

这是当前最重要的全局数据文件之一。

### 4.1 文件整体结构

`stage.ini` 不是文本 ini，而是：

```text
8-byte header
+ 277 * 224-byte main records
+ 174 * 76-byte tail records
```

当前样本的实际头信息：

| 字段 | 值 |
| --- | --- |
| `main_count` | `277` |
| `main_stride` | `224` |
| `tail_offset` | `62056` |
| `tail_stride` | `76` |
| `tail_count` | `174` |
| `file_size` | `75280` |

### 4.2 文件头

| 偏移 | 类型 | 含义 | 证据级别 |
| --- | --- | --- | --- |
| `0x00` | `u32` | 主表记录数 `main_count` | 已确认 |
| `0x04` | `u32` | 主表步长 `main_stride` | 已确认 |
| `0x08` | bytes | 主表记录区开始 | 已确认 |

### 4.3 主表：`277 * 224` 字节

当前理解：

- 主表主要承载全局武将/角色母表。
- 样本里可直接解出大量人物名。
- 当前脚本导出时保留了：
  - `raw_hex`
  - `u16_words`
  - `u32_dwords_preview`
  - 文本字段

当前家族分布：

| family | 数量 |
| --- | --- |
| `general_master` | `214` |
| `main_named_record` | `60` |
| `special_character` | `3` |

说明：

- 主表字段细节还没完全命名。
- 但结构已经足够稳定，可以安全导出、重建、保留未知字节。

### 4.4 尾表：`174 * 76` 字节

尾表结构风格与 `.stg` 很接近，混有城市、兵种、山寨/盗贼、技能文本等全局记录。

当前家族分布：

| family | 数量 |
| --- | --- |
| `text_mixed_record` | `120` |
| `troop_entry` | `26` |
| `city_92_family` | `18` |
| `city_or_structure` | `6` |
| `bandit_entry` | `3` |
| `scenario_title` | `1` |

当前已经能稳定支持的理解：

- `troop_entry`：全局兵种/部队原型候选记录。
- `city_92_family` / `city_or_structure`：城市或据点相关记录。
- `text_mixed_record`：技能、说明、混合文本字典。

### 4.5 `stage.ini` 与 `uft8-game-txt/` 的关系

当前已建立稳定映射：

| txt 文件 | relation | mapped_rows | 说明 |
| --- | --- | --- | --- |
| `general.txt` | `direct_with_trailer` | `272` | 走主表原始 dword 流，稳定步长 `57 dwords` |
| `castle.txt` | `direct_with_trailer` | `42` | 走尾表原始 dword 流，稳定步长 `25 dwords` |
| `magic.txt` | `direct` | `24` | 走尾表原始 dword 流，稳定步长 `19 dwords` |
| `soldier.txt` | `direct_with_trailer` | `76` | 走尾表原始 dword 流，稳定步长 `20 dwords` |
| `History.txt` | `supplemental` | `213` | 仅辅助查看，不参与自动回写 |

当前未发现直接映射：

- `config.txt`
- `data.txt`
- `datax.txt`
- `datay.txt`
- `HelpMessage.txt`

### 4.6 回写策略

当前 `stage.ini` 的回写遵循“已知字段覆盖，未知字节原样保留”：

1. 优先使用每条记录原始 `raw_hex` 作为写回基底。
2. 仅替换已确认映射到 Excel / JSON 的字段。
3. 如果缺少 `raw_hex`，再退回使用 `u16_words` 重打包。

这套策略已经验证成功：

- `tools/build_stage_ini.py` 可把 `stage_ini_tables.json` 回写成与原始文件字节完全一致的新文件。
- `tools/build_stage_ini_from_txt_workbook.py` 可把未修改的 `stage_ini_conversion_tables.xlsx` 回写成与原始文件字节完全一致的新文件。

## 5. `.stg`：关卡语义表

当前把 `.stg` 理解为：

```text
8-byte header
+ N * 76-byte mixed-template records
+ optional tail bytes
```

`stage01.stg` 的当前实测：

| 项目 | 值 | 证据级别 |
| --- | --- | --- |
| 文件大小 | `190208` 字节 | 已确认 |
| 文件头 | `01 00 00 00 4c 00 00 00`，按 u16 为 `[1, 0, 76, 0]` | 已确认 |
| 记录步长 | `76` 字节 | 已确认 |
| 完整记录数 | `2502` 条 | 已确认 |
| 尾部剩余 | `48` 字节 | 已确认 |

重要修正：`.stg` 不能只导出“有文本的记录”。大量无文本的 `binary_record / zero_record` 是城池、武将、士兵块之间的续记录或填充记录，必须保留原始顺序。

### 5.1 当前层级模型

`stage01.stg` 当前最合理的读法是顺序脚本：

```text
剧本标题
-> 势力/特殊块
   -> 城池块
      -> 城内武将
      -> 城内士兵
      -> 附属二进制记录
```

`tools/export_stg_hierarchy.py` 对 `stage01` 的当前导出结果：

| 统计项 | 值 |
| --- | --- |
| 原始记录数 | `2502` |
| 势力/特殊块 | `10` |
| 城池块 | `38` |
| 武将记录 | `86` |
| 士兵记录 | `42` |

已能直接观察到的块结构示例：

| 势力块 | 城池块 | 例子 |
| --- | --- | --- |
| `劉備` | `平原` | `劉備 / 關羽 / 張飛 / 糜竺 / 糜芳 ...` 后接 3 条士兵记录 |
| `曹操` | `陳留` | `夏侯淵 / 曹仁 / 曹休 / 曹洪 / 樂進 ...` 后接 3 条士兵记录 |
| `孫堅` | `長沙` | `孫堅 / 黃蓋 / 韓當 / 朱治 / 程普 ...` 后接 3 条士兵记录 |
| `劉表` | `襄陽 / 江夏 / 江陵` | 每座城后接该城武将与士兵记录 |
| `中立國` | `襄平 / 北平 / 薊 / 晉陽 / 鄴 ...` | 中立城池可有武将，也可没有士兵记录 |

因此，当前 owner/所属关系优先由“记录顺序里的势力块包含关系”解释，而不是优先寻找单个散落 `owner_id` 字段。

### 5.2 当前可区分的记录家族与锚点

`.stg` 是 76 字节混合模板容器，当前可用的主要线索如下：

| 锚点/家族 | 当前理解 | 证据级别 |
| --- | --- | --- |
| `96` | 势力/特殊块锚点。可能被识别成 `faction_or_ruler`、`faction_96_family`，也可能因为文本偏移显示为 `text_mixed_record`，例如 `劉備 | 家`。 | 高置信推断 |
| `92` | 城池块锚点。可能落在 `city_92_family`、`city_or_structure`、`text_mixed_record` 等不同 family 名下。 | 高置信推断 |
| `224` | 武将或士兵记录锚点。结合 `History.txt` 与兵种名区分 `general_entry / troop_entry`。 | 高置信推断 |
| `binary_record` | 无文本非零续记录。当前必须跟随原始顺序保留，不能丢弃。 | 已确认 |
| `zero_record` | 全零记录或填充记录。当前同样保留。 | 已确认 |

旧版 `family_guess` 只是启发式分类名，不是文件内字段名。尤其是 `city_or_structure` 不能再简单解释成“模板/标签型记录”：例如 `薊 | W城市3`、`鄴 | W城市` 在当前层级导出中会作为中立城池块边界。

### 5.3 `general_entry` 归一化线索

对 `general_entry` 记录按 `224` 锚点、目标列 `n04` 归一化后，当前最稳的解释是：

| 归一化列 | 当前理解 | 证据级别 |
| --- | --- | --- |
| `n02` | 势力/块编号候选值，仍需结合顺序层级解释 | 高置信推断 |
| `n16` | 武将编号候选值 | 高置信推断 |
| `n18` | 额外属性/排序值候选位 | 待验证 |

样本依据：

- 旧版 `tools/export_stg_phase7_links.py` 对 `stage01.stg` 导出的 `general_rows.csv` 中，66 条能对到 `History.txt` 的记录里，有 52 条满足 `general_id_candidate == history_general_id`。
- 新版层级导出会额外把 `entity_224_family / text_mixed_record` 中能命中 `History.txt` 的记录归为武将，因此 `stage01` 当前可识别 86 条武将记录。

### 5.4 势力块线索

`96` 锚点比 `faction_or_ruler` 这个旧 family 名更可靠。当前已确认 `stage01` 中至少有如下势力/特殊块边界：

- `劉備`
- `曹操`
- `孫堅`
- `劉焉`
- `劉表`
- `馬騰`
- `袁紹`
- `董卓`
- `中立國`
- `盜賊`

说明：

- `劉備 | 家` 这类记录会同时命中 `History.txt` 武将名和 `96` 锚点；它应优先解释为势力块开头，而不是普通武将记录。
- `faction_or_ruler.n12` 这类“槽位”仍有排查价值，但不能直接等同于 owner 字段。

### 5.5 城池块线索

城池块不是只存在于 `city_92_family`。当前城池边界来源包括：

- `city_92_family`：最容易归一化，20 条记录的 `city_id / city_size` 与 `castle.txt` 20/20 对齐。
- `text_mixed_record`：例如 `平原`、`長沙`、`成都`、`江州`、`北平`，部分记录的 `92` 锚点落在附近或偏移位置。
- `city_or_structure`：例如 `薊 | W城市3`、`鄴 | W城市`，当前在中立城池块中出现。

对 `city_92_family` 记录按 `92` 锚点归一化后，仍然保留这些高置信字段：

| 归一化列 | 当前理解 | 证据级别 |
| --- | --- | --- |
| `n12` | 城市索引 `city_id` | 高置信推断 |
| `n16` | 城市规模 `city_size` | 高置信推断 |
| `n18/n20/n22` | 当前人口/金/粮候选值 | 待验证 |
| `n26/n28/n30` | 当前开发/商业/治安候选值 | 待验证 |

`stage01` 的直接验证结果：

- 20 条 `city_92_family` 城市记录全部满足 `city_id_candidate == castle_city_id`。
- 20 条 `city_92_family` 城市记录全部满足 `city_size_candidate == castle_city_size`。
- 城市坐标可通过 `city_id` 稳定反查到 `castle.txt` / `stage.ini` 城市母表，例如：
  - `陳留 -> city_id 10 -> (217, 388)`
  - `襄陽 -> city_id 22 -> (109, 824)`
  - `建業 -> city_id 30 -> (323, 728)`

### 5.6 城池状态字段候选

`tools/export_stg_city_troop_analysis.py` 会把每个城池块开头若干记录拼成连续 u16 流，再定位 `city_id` 字段：

- 有 `92` 锚时：`city_id = anchor_92 + 12`。
- 无 `92` 锚时：按 `city_id / city_size / population` 组合搜索，例如 `平原`。

定位到 `city_id` 后，当前字段候选如下：

| 相对 `city_id` 的 u16 偏移 | 当前理解 | `stage01` 验证 |
| --- | --- | --- |
| `+0` | 城市索引 `city_id` | 38/38 对齐 `castle.txt` |
| `+2` | 房子属性/保留零值候选 | 待验证 |
| `+4` | 城规模 `city_size` | 38/38 对齐 `castle.txt` |
| `+6` | 当前人口 | 高置信推断 |
| `+8` | 当前金 | 高置信推断 |
| `+10` | 当前粮 | 高置信推断 |
| `+12` | 保留/待命士兵候选 | 待验证 |
| `+14` | 当前开发值 | 高置信推断 |
| `+16` | 当前商业值 | 高置信推断 |
| `+18` | 当前治安值 | 高置信推断 |
| `+20` | 开发上限 | 高置信推断 |
| `+22` | 商业上限 | 高置信推断 |
| `+24` | 治安上限 | 高置信推断 |
| `+26` | 地图 X | 38/38 对齐 `castle.txt` |
| `+28` | 地图 Y | 38/38 对齐 `castle.txt` |
| `+30` | 太守/城主武将 id 候选 | 23 条能映射 `History.txt`，其中 22 条在本城武将列表内 |

这个结论修正了旧的“只在单条 `city_92_family` 记录内 wrap 归一化”的理解。城池状态字段经常跨过 76 字节记录边界，必须把城池块头部作为连续流读取。

### 5.7 士兵记录候选

`troop_entry` 当前按 `224` 锚点展开，并通过层级模型挂回所属城池。`stage01` 当前识别 42 条士兵记录。

已知线索：

- 士兵文本包括 `步兵`、`槍兵`、`騎兵`、`弓箭兵`、`投石車`。
- 归一化后 `t36` 常与势力/块编号一致，例如刘备块为 `1`、曹操块为 `2`、孙坚块为 `3`。
- `t12/t14/t22/t24/t26/t32` 等列存在重复模式，但还不能最终命名为数量、等级或兵种 id。

因此士兵记录目前只进入候选表，不进入写回字段定义。

### 5.8 关于 `slot/context_owner_slot_consensus` 的降级说明

旧版 `tools/export_stg_phase7_links.py` 里出现的：

- `slot_candidate`
- `context_prev_slot`
- `context_next_slot`
- `context_owner_slot_consensus`

现在全部降级为“历史排查线索”。它们不是 `.stg` 中已经确认的字段名，也不能再作为 owner 结论使用。

当前 owner/所属关系的优先解释是：

1. 先按原始记录顺序识别势力块。
2. 再按城池名、`92` 锚点、`castle.txt` 识别城池块。
3. 后续武将/士兵记录挂到当前城池块。
4. 若后续找到直接 owner 字段，再用它校正层级模型。

### 5.9 `.stg` 字节级构成与转换脚本契约（已确认）

本节按“只看文档也能重写转换脚本”的粒度记录 `.stg` 的当前可逆结构。以下结论已经用 `stage01.stg -> Excel -> stage01.stg` 字节级 round-trip 验证。

#### 5.9.1 文件整体布局

`.stg` 当前按固定头、固定步长记录链、尾部余数字节读取：

```text
file = header[8]
     + records[record_count] * 76 bytes
     + tail[tail_bytes]

payload_size = file_size - 8
record_count = payload_size // 76
tail_bytes = payload_size % 76
record_i_offset = 8 + i * 76
```

`stage01.stg` 实测值：

| 项目 | 值 | 写回要求 |
| --- | --- | --- |
| `file_size` | `190208` | 导入后大小必须一致，除非用户明确编辑字段 |
| `header_hex` | `010000004c000000` | 原样保留 |
| `header_u16_words` | `[1, 0, 76, 0]` | 可作为调试显示，不用于重新推导 |
| `stride` | `76` | 当前导入器只支持该步长 |
| `record_count` | `2502` | `raw_records` 必须覆盖 `0..2501` |
| `tail_bytes` | `48` | 原样保留 |

#### 5.9.2 单条记录结构

每条记录固定 76 字节，可稳定展开为 38 个 little-endian `u16`：

```text
record = raw[76]
word[j] = u16_le(record[j*2 : j*2+2]), 0 <= j < 38
```

当前不要按 family 重新打包记录。正确写回策略是：

1. 读取 `raw_hex` 作为 76 字节原始记录。
2. 对已确认字段，在这 76 字节 buffer 上覆盖对应 `u16`。
3. 未确认字节、文本、填充记录、跨记录连续字段全部原样保留。

#### 5.9.3 `raw_records` 工作表契约

`raw_records` 是 `.stg` 回写的保底数据源。最少必须包含：

| 列名 | 类型 | 用途 |
| --- | --- | --- |
| `record_index` | int | 记录序号，必须连续覆盖 `0..record_count-1` |
| `file_offset` | int | 调试用，理论值为 `8 + record_index * 76` |
| `family_guess` | text | 启发式分类，仅辅助阅读，不参与重建 |
| `texts_joined` | text | 当前能解出的 CP950 文本，仅辅助阅读 |
| `raw_hex` | hex string | 76 字节记录的权威来源，导入时必须长度为 152 个十六进制字符 |
| `w00..w37` | int | `raw_hex` 的 u16 展开，辅助检查；导入不依赖这些列重建 |

导入算法：

```text
records = array[record_count]
for each row in raw_records:
    i = int(row.record_index)
    records[i] = bytes.fromhex(row.raw_hex)
    assert len(records[i]) == 76
assert every i in 0..record_count-1 exists
rebuilt = bytes.fromhex(meta.header_hex) + b''.join(records) + bytes.fromhex(meta.tail_hex)
```

#### 5.9.4 `meta` 工作表契约

`meta` 是键值表，至少需要：

| key | 用途 |
| --- | --- |
| `stage` | 关卡名，例如 `stage01` |
| `source_path` | 原始文件路径，仅用于审计 |
| `file_size` | 原文件大小，仅用于审计 |
| `header_size` | 当前固定为 `8` |
| `stride` | 当前固定为 `76` |
| `record_count` | 完整记录数 |
| `tail_bytes` | 尾部余数字节数 |
| `header_hex` | 8 字节文件头，必须原样写回 |
| `tail_hex` | 尾部余数字节，必须原样写回 |

#### 5.9.5 已确认可编辑的 `city_state` 连续字段

`city_state` 不是单条记录内字段，而是从城池块起始记录开始，把若干 76 字节记录连续展开为 u16 流后定位。定位方式：

```text
stream = words(source_record_index) + words(source_record_index+1) + ...
if stream contains 92:
    city_id_stream_index = index_of_first_92 + 12
else:
    city_id_stream_index = first index where:
        stream[index] == expected_city_id
        1 <= stream[index + 4] <= 5
        500 <= stream[index + 6] <= 5000
```

字段偏移以 `city_id_stream_index` 为基准，单位是 `u16`：

| Excel 列 | 相对偏移 | 当前含义 | 写回级别 |
| --- | ---: | --- | --- |
| `candidate_city_id` | `+0` | 城市 id | 已确认，可编辑但通常不建议改 |
| `candidate_house_type_or_zero` | `+2` | 房子属性/保留零值候选 | 待验证，默认保留 |
| `candidate_city_size` | `+4` | 城市规模 | 已确认 |
| `candidate_population` | `+6` | 当前人口 | 高置信推断 |
| `candidate_gold` | `+8` | 当前金 | 高置信推断 |
| `candidate_grain` | `+10` | 当前粮 | 高置信推断 |
| `candidate_reserved_after_grain` | `+12` | 保留/待命士兵候选 | 待验证 |
| `candidate_dev` | `+14` | 当前开发 | 高置信推断 |
| `candidate_commerce` | `+16` | 当前商业 | 高置信推断 |
| `candidate_security` | `+18` | 当前治安 | 高置信推断 |
| `candidate_dev_max` | `+20` | 开发上限 | 高置信推断 |
| `candidate_commerce_max` | `+22` | 商业上限 | 高置信推断 |
| `candidate_security_max` | `+24` | 治安上限 | 高置信推断 |
| `candidate_map_x` | `+26` | 地图 X | 已确认 |
| `candidate_map_y` | `+28` | 地图 Y | 已确认 |
| `candidate_prefect_general_id_candidate` | `+30` | 太守/城主武将 id 候选 | 高置信推断 |

写回公式：

```text
stream_index = city_id_stream_index + relative_offset
absolute_record_index = source_record_index + stream_index // 38
word_index = stream_index % 38
byte_offset_in_record = word_index * 2
records[absolute_record_index][byte_offset_in_record : byte_offset_in_record+2]
    = u16_le(new_value)
```

注意：这个公式允许字段跨 76 字节记录边界。旧的“只在单条 `city_92_family` 内 wrap”做法已经废弃。

#### 5.9.6 当前脚本与验证结果

当前互转脚本：

- `tools/export_stg_workbook.py`：导出 `meta`、`raw_records`、层级表、`city_state`、`troop_candidates`。
- `tools/import_stg_workbook.py`：从 workbook 回写 `.stg`，默认应用 `city_state` 覆盖；可用 `--no-city-state` 只做 raw round-trip。

验证命令与结果：

```powershell
& $py tools/export_stg_workbook.py . --stage stage01 --out outputs/stg_workbooks/stage01_stg.xlsx
& $py tools/import_stg_workbook.py outputs/stg_workbooks/stage01_stg.xlsx . --out derived/sidecar_analysis/stg_workbooks/stage01_from_workbook.stg --compare-with 三国霸业/stage01.stg
```

未修改工作簿时：

| 模式 | 结果 |
| --- | --- |
| 默认应用 `city_state` | 与原 `stage01.stg` 字节完全一致，sha256 `4857f3cddcae71bb807379d27175d6a23c97410013e27f3fdf1e215099c281e0` |
| `--no-city-state` | 与原 `stage01.stg` 字节完全一致，同 sha256 |
| 烟测：第一个城池人口 `1200 -> 1201` | 仅 1 个字节变化，偏移 `0x1A4`，符合 little-endian u16 覆盖预期 |

#### 5.9.7 暂不回写的内容

- `troop_candidates` 当前只用于阅读，不进入自动写回字段定义。
- `hierarchy_records`、`force_city_summary` 用于解释势力/城池/武将/士兵顺序层级，不是重建 `.stg` 的唯一来源。
- `family_guess`、`text_layout`、`ascii_tokens` 都是导出脚本的分析产物，不应作为二进制格式的硬编码事实。

## 6. `.evt`：事件/脚本表

当前把 `.evt` 理解为：

```text
8-byte header
+ 72-byte mixed-template command records
+ optional tail bytes
```

已知高置信结论：

- 文件中能直接发现 `talk`、`VIEW`、`MAP`、`MOVE`、`OPEN`、`TIMEOVER` 等控制词。
- 同时还包含目标、提示、对话文本。
- 因此 `.evt` 更像“命令记录 + 文本参数”的混合脚本层，而不是单纯文本表。

当前最值得继续追的方向：

1. 事件记录如何引用地图坐标
2. 事件记录如何引用人物/城池/势力 id
3. 哪些字段与编辑器里的对象层直接关联

## 7. `.s` / `.x`：小地图/缓存候选层

当前已确认：

- 两者都是固定 `160 * 160 = 25600` 字节。
- `.x` 与 `.m.final_palette` 的重合度高于 `.s`。
- 在已采样关卡里，`.x` 常常比 `.s` 包含更多非 `240` 像素。

当前最稳妥的理解：

- `.x` 更像完整颜色缓存或更接近真实小地图的结果层。
- `.s` 更像遮罩、裁剪伴随层或更保守的缓存层。

但在没有 `Emperor.exe` 写回路径证据前，编辑器不应直接伪造 `.s/.x`。

## 8. 当前最重要的未解问题

1. `.stg` 势力块/城池块的直接字段边界与可写回范围
2. 城池块内人口、金、粮、士兵数量/兵种字段的最终命名
3. `.evt` 如何把事件对象映射回地图
4. `.s/.x` 的真实生成流程和写回策略
5. `.m.byte08/09/10/11` 的最终语义
6. `acwz` 的完整 footprint 与 z-order
