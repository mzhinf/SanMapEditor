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

| 偏移 | 类型 | 字段名 | 当前理解 | 证据级别 |
| --- | --- | --- | --- | --- |
| `+0x00` | `int16` | `acwx` | 基础地形 tile 索引 | 已确认 |
| `+0x02` | `int16` | `acwy` | 叠加/过渡 tile 索引，`-1` 表示空层 | 已确认 |
| `+0x04` | `int16` | `acwz` | 建筑/物件 tile 索引，`-1` 表示空层 | 已确认 |
| `+0x06` | `u16` | `flags` | 与地块状态相关，但尚未完全命名 | 高置信推断 |
| `+0x08` | `u8` | `byte08` | 少量非零的辅助标记 | 待验证 |
| `+0x09` | `u8` | `byte09` | 0/1 分布明显，疑似通行或遮挡标记 | 高置信推断 |
| `+0x0A` | `u16` | `byte10_u16` | 与物件类别或额外状态有关 | 待验证 |
| `+0x0C` | `u16` | `field1` | 未解字段，编辑时必须保留 | 待验证 |
| `+0x0E` | `u16` | `field2` | 未解字段，编辑时必须保留 | 待验证 |

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

### 5.1 文件外形

当前脚本按以下方式处理 `.stg`：

```text
8 字节文件头
+ N 条 76 字节记录
+ 尾部余数字节
```

以 `stage01.stg` 为例：

- `record_count = 2502`
- `stride = 76`
- `tail_bytes = 48`

### 5.2 当前稳定读取方式

`.stg` 不能只导出“有文本的记录”。大量 `binary_record`、`zero_record` 也是层级结构的一部分，必须保留原始顺序。

当前最稳定的解释方式是：

- 先按原始顺序读取全部 76 字节记录。
- 再按势力块、城池块、武将/士兵附属块恢复层级。
- `family_guess`、`text_layout`、`city_92_family` 这类名字都是分析脚本的标签，不是文件内原生字段名。

其中：

- `city_92_family` 只是“命中 92 锚点的城市记录家族”这个分析名。
- `faction_or_ruler`、`text_mixed_record` 等同样是导出期分类名，不能直接当作二进制字段名使用。

### 5.3 `stage01.stg` 已确认的城池状态定位

`tools/export_stg_city_troop_analysis.py` 会把城池块起始后的若干条记录展开成连续 `u16` 流，再定位 `city_id` 附近的字段。

当前已能稳定导出的字段包括：

- `city_id`
- `city_size`
- `population`
- `gold`
- `grain`
- `dev`
- `commerce`
- `security`
- `dev_max`
- `commerce_max`
- `security_max`
- `map_x`
- `map_y`
- `prefect_general_id_candidate`

这些字段已经进入 `.stg` Excel 工作簿中的 `city_state` sheet，并具备回写能力。

### 5.4 `.stg` Excel 工作簿契约

`tools/export_stg_workbook.py` 导出的工作簿包含：

- `说明`
- `meta`
- `raw_records`
- `hierarchy_records`
- `force_city_summary`
- `city_state`
- `troop_candidates`

回写规则：

1. 优先以 `raw_records.raw_hex` 重建每条 76 字节记录。
2. 只覆盖 `city_state` 中已经确认映射的 `candidate_*` 字段。
3. 未解字段一律保持原始字节。
4. `meta.header_hex`、`meta.tail_hex` 必须原样写回。

现有验证：

- 未修改工作簿时，默认模式和 `--no-city-state` 模式都能回写出与原始 `stage01.stg` 字节完全一致的文件。
- 修改 `candidate_population` 后，只会改动预期的单个 `u16` 字段。

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

- 疑似与门、入口、通道或场景触发边界有关。
- 可为空。

### `.s/.x`

- 两者大小都固定为 `160 * 160 = 25600` 字节。
- 已新增 `tools/analyze_minimap_sidecars.py`，会把全量统计写入 `derived/sidecar_analysis/minimap_sidecar_analysis.json`。
- 已新增 `tools/build_minimap_sidecars.py`，按当前最稳的规则把 `.m` 转回 `.s/.x`：上 `128` 行由 `.m` 的 `final_palette` 缩放生成，下 `32` 行直接保留原始 sidecar 尾区。
- 在 33 个带 `.m/.s/.x` 的关卡里，`.s` 与 `.x` 平均仍有 `0.80094` 的逐字节相同率，说明二者高度相关。
- 若只比较有效区，上 `128` 行中，`.m final_palette -> 160x128` 与 `.s/.x` 的平均匹配率分别为 `0.47098 / 0.620744`；`.x` 明显更接近 `.m` 派生结果。
- 若采用“上 128 行派生 + 下 32 行保留”的保守写回策略，生成结果与原始 `.s/.x` 的平均全图匹配率分别为 `0.576784 / 0.696596`，且尾区匹配率恒为 `1.0`。
- 跨关卡统计里，第 `128..141` 行和 `150..159` 行都出现了 `>= 0.95` 的静态一致度，`159` 行达到 `1.0`，说明底部存在明显公共尾区或缓存区。
- 当前可以把 `.s/.x` 视为“顶部有效缩略图 + 底部公共尾区/缓存区”的组合；但它们是否还叠加了 `Emperor.exe` 内的额外调色、标记或压缩流程，仍需继续确认。
## 7. 写回策略

当前统一采用“保底原始字节 + 局部覆写”的策略：

1. 优先保留原始记录。
2. 只修改已经确认偏移的字段。
3. 未确认字段不重算、不清零、不移位。
4. 所有导入脚本都必须支持与原文件逐字节比较。

这是目前最稳妥、也最适合继续逆向扩展的方案。

## 8. 当前未解问题

1. `.m` 中 `flags / byte08 / byte09 / byte10_u16 / field1 / field2` 的最终语义。
2. `.stg` 城池块和士兵块里剩余未命名字段的完整含义。
3. `.evt` 如何引用地图坐标、对象和全局 id。
4. `.s/.x` 顶部有效区之外，是否还存在 `Emperor.exe` 内的额外调色、标记或压缩步骤。
5. `acwz` 物件的完整 footprint 与最终 z-order 规则。

