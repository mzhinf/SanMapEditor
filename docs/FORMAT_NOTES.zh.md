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
+ 76-byte mixed-template records
+ optional tail bytes
```

已知高置信结论：

- 城池、势力、武将、兵种文本都出现在 `.stg` 中。
- 这不是单模板表，而是多模板混合容器。
- 对齐分析后，至少能稳定区分：
  - `general_entry`
  - `faction_or_ruler`
  - `troop_entry`
  - `city_or_structure`

当前已知字段级线索：

- `general_entry.w02` 很像 `faction_id`
- `faction_or_ruler.w12` 很像 `faction_id`
- `troop_entry.w12/w14` 已能稳定形成兵种编码对
- `city_or_structure.w14` 很像 `place_id`

当前最值得继续追的方向：

1. `city_id`
2. `owner_id`
3. 关卡内地图坐标

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

1. `.stg` 的城市记录里，哪几个字段分别对应 `city_id / owner_id / coordinate`
2. `.evt` 如何把事件对象映射回地图
3. `.s/.x` 的真实生成流程和写回策略
4. `.m.byte08/09/10/11` 的最终语义
5. `acwz` 的完整 footprint 与 z-order