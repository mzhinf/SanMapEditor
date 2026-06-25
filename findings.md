# Findings

## 项目目标

围绕《三国霸业》实现一条完整链路：

1. 从原始游戏目录中恢复真实地图。
2. 建立可编辑的地图数据模型。
3. 明确全局母表与关卡 sidecar 的关系。
4. 逐步补齐安全回写能力。

## 当前稳定结论

### 1. `.m` 是地图主表

- 文件头固定 16 字节：`width`、`height`、`Hello1.0`
- 每个 cell 固定 16 字节
- 前 6 字节对应：
  - `acwx`
  - `acwy`
  - `acwz`
- 其余字节不是噪声，编辑器必须保留

### 2. `kingdom.cel/.atr` 是地图资源核心

- `acwx`：基础地形
- `acwy`：叠加/过渡
- `acwz`：建筑/物件

当前渲染器已能按真实资源绘制地图，而不是只画索引诊断图。

### 3. `Emperor.exe` 已给出关键渲染逻辑

- 地图使用 staggered isometric 网格
- 当前稳定的 world-to-screen：

```text
screen_x = col * 40 + (20 if row is odd else 0)
screen_y = row * 10
```

- `acwz` 资源带 `xAnchor/yAnchor`

### 4. `stage.ini` 是全局二进制母表

- 不是文本 ini
- 当前样本结构：
  - 头：8 字节
  - 主表：`277 * 224`
  - 尾表：`174 * 76`
- 已能导出 JSON、Excel，并回写出字节完全一致的新文件

### 5. `uft8-game-txt` 与 `stage.ini` 存在强关联

已确认关联：

- `general.txt`
- `castle.txt`
- `magic.txt`
- `soldier.txt`
- `History.txt`（辅助）

当前稳定步长：

- `general.txt` -> `57 dwords`
- `castle.txt` -> `25 dwords`
- `magic.txt` -> `19 dwords`
- `soldier.txt` -> `20 dwords`

### 6. sidecar 文件不是装饰

- `.stg`：城池/势力/武将/兵种语义层
- `.evt`：事件/脚本层
- `.spr`：单位层，可为空
- `.dor`：门/入口层，可为空
- `.s/.x`：固定网格缓存/小地图候选层

这说明完整编辑器不能只改 `.m`。

### 7. `stage01.stg` 已恢复为可读的顺序层级

- `.stg` 必须按原始 76 字节记录链处理，不能只看有文本的记录。
- `stage01.stg` 实测为 8 字节头、2502 条完整记录、48 字节尾部。
- 当前层级导出可得到 10 个势力/特殊块、38 个城池块：例如 `劉備 -> 平原`、`曹操 -> 陳留`、`孫堅 -> 長沙`、`劉表 -> 襄陽/江夏/江陵`、`中立國 -> 襄平/北平/薊/...`。
- `city_92_family` 仍是最稳的字段子集：20 条记录全部对上 `castle.txt` 的 `city_id / city_size`。
- 完整城池块不只落在 `city_92_family`，还会因偏移差异落到 `text_mixed_record`、`city_or_structure`。


### 8. `.stg` Excel 互转链路已闭合

- 新增 `tools/export_stg_workbook.py` 与 `tools/import_stg_workbook.py`。
- `raw_records.raw_hex` 是 `.stg` 的字节级回写保底源，`meta.header_hex` 和 `meta.tail_hex` 原样保留。
- `city_state` 按“城池起始记录 + 连续 u16 流 + city_id_stream_index + 相对偏移”回写，字段可以跨 76 字节记录边界。
- `stage01.stg -> outputs/stg_workbooks/stage01_stg.xlsx -> derived/sidecar_analysis/stg_workbooks/stage01_from_workbook.stg` 已验证字节完全一致，sha256 为 `4857f3cddcae71bb807379d27175d6a23c97410013e27f3fdf1e215099c281e0`。
- 修改第一个城池人口 `1200 -> 1201` 的烟测只产生 1 个字节差异，证明 `city_state` 覆盖路径能精准落点。

## 当前高置信推断

### `.m` 附加字节

- `byte09` 疑似通行/遮挡候选位
- `byte10` 疑似物件/类别位
- `byte11` 疑似 footprint 子索引
- `final_palette` 疑似最终缓存/小地图颜色索引

### `.stg`

- 是 8 字节头 + 76 字节混合模板记录链 + 可选尾字节。
- 当前按顺序层级解释 owner：势力块包含城池块，城池块包含武将/士兵/附属记录。
- 主要锚点：`96` 势力块、`92` 城池块、`224` 武将/士兵记录。
- 城池状态字段已按连续 u16 流定位：`city_id`、`city_size`、`map_x`、`map_y` 在 `stage01` 38/38 对齐。
- `city_id+6/+8/+10` 高置信对应当前人口/金/粮，`+14/+16/+18` 高置信对应开发/商业/治安，`+20/+22/+24` 高置信对应三项上限。
- `city_id+30` 是太守/城主武将 id 候选：23 条能映射到 `History.txt`，其中 22 条在本城武将列表内。
- 士兵记录已按 `224` 锚点挂回城池，但数量/等级字段仍待命名。
- `slot/context_owner_slot_consensus` 已降级为旧版排查线索，不再作为 owner 结论。

### `.evt`

- 是 72 字节混合模板命令容器
- 混合了控制词、文本、目标/提示/对话内容

### `.s/.x`

- `.x` 比 `.s` 更像完整颜色缓存
- `.s` 更像遮罩或更保守的伴随层

## 已验证的回写能力

### 地图编辑

- 浏览器编辑器可输出 JSON patch
- `tools/apply_editor_patch.py` 可把 patch 安全写入复制出的 `.m`

### `stage.ini`

- `tools/build_stage_ini.py`：JSON -> `stage.ini`，字节级一致
- `tools/build_stage_ini_from_txt_workbook.py`：Excel -> `stage.ini`，字节级一致

## 当前最值得继续研究的方向

1. `.stg` 城池状态字段的安全写回规则
2. 士兵记录中的数量、等级、兵种 id 字段最终命名
3. `.evt` 如何引用地图对象、坐标与全局 id
4. `.s/.x` 的真实生成与回写路径
5. `acwz` 的完整 footprint 与 z-order

## 文档决策

从本次开始，所有新增有效结论必须同步进入：

- `README.md`
- `docs/FORMAT_NOTES.zh.md`
- `task_plan.md`
- `progress.md`
- `findings.md`

不再接受“脚本已改、文档以后再补”的做法。
