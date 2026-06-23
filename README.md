# 三国霸业地图复原工具

这个仓库保存对《三国霸业》地图与资源格式的复原脚本、格式笔记和阶段性规划。原始游戏文件保留在 `三国霸业/`，生成物默认写入 `derived/`；这两个目录都不提交到 git。

## 环境

推荐使用 Codex bundled Python：

```powershell
$py = 'C:\Users\mzhinf\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

脚本会自动在当前目录或子目录里寻找包含 `Emperor.exe` 的游戏目录。默认 palette 暂时使用 `tools/palette.py` 中的 `SAN_RGB_PALETTE`；如需对比外部 BMP 色盘，可以通过 `--palette BIGMAP01.bmp` 或其他 BMP 文件名显式指定。

## 常用脚本

### `tools/analyze_assets.py`

盘点游戏目录、PE 基本信息、可见字符串、阶段文件尺寸和格式线索。

```powershell
& $py tools/analyze_assets.py .
```

用途：第一次接触新拷贝的游戏目录时确认资源是否完整，也可复核 `Emperor.exe` 是否仍引用相同文件名。

### `tools/export_map_previews.py`

导出早期诊断图：`.m` 最终缓存图、`.s/.x` 网格图，以及 DAT 容器预览表。

```powershell
& $py tools/export_map_previews.py .
```

主要输出：

- `derived/maps/*_m.png`
- `derived/grids/*_s.png`、`derived/grids/*_x.png`
- `derived/dat_sheets/*_sheet.png`

说明：这些图适合诊断资源关系；`grids` 更像小地图或缓存层，不是最终的可编辑大地图。

### `tools/extract_kingdom.py`

解析 `kingdom.cel` / `kingdom.atr`，导出 CEL/ATR 表格和 tile sheet。

```powershell
& $py tools/extract_kingdom.py .
```

主要输出：

- `derived/kingdom/kingdom_atr_records.tsv`
- `derived/kingdom/kingdom_cel_chunks.tsv`
- `derived/kingdom/cel_acwx_sheet.png`
- `derived/kingdom/cel_acwy_sheet.png`
- `derived/kingdom/cel_acwz_sheet.png`

说明：此脚本保留了较早的扫描式解析结果，用于人工检查资源；最终地图渲染应优先参考 `render_m_cel_map.py` 的 counted CEL 解析。

### `tools/stitch_kingdom_tiles.py`

生成 `acwz` 城池/建筑条带的手工拼接预览，以及 `acwx/acwy` 6x6 meta sheet。

```powershell
& $py tools/stitch_kingdom_tiles.py .
```

主要输出：

- `derived/kingdom/acwz_stitched_city_center.png`
- `derived/kingdom/acwx_meta_6x6_sheet.png`
- `derived/kingdom/acwy_meta_6x6_sheet.png`

说明：`acwz` 独立拼接目前只作为观察参考；真实地图应按照 `.m` 记录和 `Emperor.exe` 的 anchor/z-order 逻辑绘制。

### `tools/export_m_layers.py`

把 `.m` 记录拆成可编辑的多层索引和辅助 flag 文件。

```powershell
& $py tools/export_m_layers.py .
```

主要输出：

- `derived/m_layers/stageNN/acwx.i16`
- `derived/m_layers/stageNN/acwy.i16`
- `derived/m_layers/stageNN/acwz.i16`
- `derived/m_layers/stageNN/byte08.bin`
- `derived/m_layers/stageNN/byte09.bin`
- `derived/m_layers/stageNN/byte10.bin`
- `derived/m_layers/stageNN/byte11.bin`
- `derived/m_layers/stageNN/final_palette.bin`
- `derived/m_layers/m_record_summary.tsv`
- `derived/m_layers/kingdom_blocks.json`

说明：这些是编辑器数据模型的雏形。预览图是属性/索引诊断图，不等同于最终游戏画面。


### `tools/export_editor_bundle.py`

Builds the first editor-ready bundle: a rendered CEL map image, editable record JSON, and a static HTML editor.

```powershell
& $py tools/export_editor_bundle.py . --stage stage11
```

Outputs:

- `derived/editor/stage11/map.png`
- `derived/editor/stage11/stage.json`
- `derived/editor/stage11/editor.html`
- `derived/editor/index.json`

Current editor scope: map browsing, zoom/pan, stagger cell picking, `.m` record inspection, local `acwx/acwy/acwz` edits, and JSON patch export. It does not overwrite the original `.m` files yet.

### `tools/render_m_cel_map.py`

使用 `stageNN.m` 的 `acwx/acwy/acwz` 索引和 `kingdom.cel` 真实像素绘制游戏地图。

```powershell
& $py tools/render_m_cel_map.py . --stage stage11 --layout stagger --layers xyz --crop 93 57 1642 1684 --scale 2
```

常用参数：

- `--stage stage11`：选择 `stageNN.m`。
- `--layout stagger`：默认布局；已和 `Emperor.exe` / `stage11.png` 对齐。
- `--layers xyz`：`x=acwx` 基础地形，`y=acwy` 叠加/过渡，`z=acwz` 物件/建筑。
- `--crop X Y W H`：渲染后裁切视口。
- `--scale 2`：最近邻放大，便于和截图对比。
- `--palette SAN_RGB_PALETTE`：默认值，来自 `tools/palette.py`；可显式指定 BMP palette 做对比，非默认 palette 输出文件名会附加 `_pal<name>`。

当前确认的地图坐标变换：

```text
screen_x = col * 40 + (20 if row is odd else 0)
screen_y = row * 10
```

`stage11` 的截图级对比命令会生成：

```text
derived/cel_maps/stage11_stagger_xyz_viewport93_57_1642_1684_scale2.png
```

## Palette 结论

`Emperor.exe` 的 PE resource 中没有 `RT_BITMAP`，目前没有发现内嵌 DIB palette。EXE 导入了 `SetSystemPaletteUse`、`GetSystemPaletteEntries` 和 `DirectDrawCreate`，并在字符串表中引用外部 BMP 文件，包括 `stage.bmp`。

实机截图校准显示：河流常用索引 `11/12/13` 在 `BIGMAP01.bmp`、`mainmenu.bmp` 等通用 palette 中是蓝色，和 `derived/stage11.png` 一致；`stage.bmp` 将这些索引映成亮绿。当前工具默认使用 `tools/palette.py` 的 `SAN_RGB_PALETTE`，便于后续集中调整。


## 下一步地图编辑器方案

1. 数据模型层：以 `.m` 的 16 字节记录为主表，拆出 `acwx/acwy/acwz` 三个 int16 图层、辅助 flag 字节、最终 cache 字节，并保留原始 record 以支持无损 round-trip。
2. 渲染/选取层：把 `render_m_cel_map.py` 的 stagger world-to-screen 逻辑模块化，提供 cell-to-screen、screen-to-cell、tile footprint、object anchor 和 z-order 查询。
3. 资源面板：从 `kingdom.cel/.atr` 生成可搜索 tile/object palette，按 `acwx` 地形、`acwy` 过渡/道路/岸线、`acwz` 建筑/物件分组。
4. 编辑操作：先实现基础地形绘制、overlay 绘制、object 放置/删除，再补 passability、事件、单位和城门数据。
5. 保存策略：第一阶段只写新的 `.m` 副本和 JSON sidecar；第二阶段在验证 record 字段语义后支持覆盖导出完整 `stageNN.*` 组合。
6. 验证闭环：每次编辑后生成 CEL 渲染预览，与原图或游戏截图对比；对关键 stage 保留小型自动回归测试。

优先级最高的未解问题：`acwz` 的完整 z-order/footprint、`byte08/09/10/11` 的语义、`.spr/.dor/.evt/.stg` 与地图对象之间的引用关系。
