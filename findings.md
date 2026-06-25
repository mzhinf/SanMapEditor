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

### 7. `stage01.stg` 的城市实例已能稳定落回全局城市母表

- 真正的关卡城市实例当前主要出现在 `city_92_family`。
- `tools/export_stg_phase7_links.py` 对 `stage01.stg` 的导出结果里：
  - 20 条城市记录全部满足 `city_id_candidate == castle_city_id`
  - 20 条城市记录全部满足 `city_size_candidate == castle_city_size`
- 因此对 `stage01` 而言，城市坐标已经可以经 `city_id` 稳定反查到 `castle.txt` / `stage.ini` 城市母表。

## 当前高置信推断

### `.m` 附加字节

- `byte09` 疑似通行/遮挡候选位
- `byte10` 疑似物件/类别位
- `byte11` 疑似 footprint 子索引
- `final_palette` 疑似最终缓存/小地图颜色索引

### `.stg`

- 是 76 字节混合模板记录容器
- 已能区分 `general_entry`、`faction_or_ruler`、`troop_entry`、`city_92_family`、`city_or_structure`
- 当前最稳的归一化字段：
  - `general_entry.n02` -> 势力槽位候选值
  - `general_entry.n16` -> 武将编号候选值
  - `faction_or_ruler.n12` -> 势力槽位候选值
  - `faction_or_ruler.n14` -> 君主武将编号候选值
  - `city_92_family.n12` -> 城市索引 `city_id`
  - `city_92_family.n16` -> 城市规模 `city_size`
  - `city_92_family.n18/n20/n22` -> 当前人口/金/粮候选值
  - `city_92_family.n26/n28/n30` -> 当前开发/商业/治安候选值
- `city_or_structure` 仍更像模板/标签型记录，尚未和实际城市实例完全并上
- `owner_id` 直接字段尚未锁定，但可先用相邻槽位推导出一批 `context_owner_slot_consensus`

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

1. `.stg` 城市记录中的直接 `owner_id` 字段
2. `city_92_family` 与 `city_or_structure` 的完整分工
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