# Task Plan: 三国霸业地图复原

## Goal
解析 `三国霸业/Emperor.exe` 和游戏资源格式，提取并复原可用于制作地图编辑器的地图数据与可视化结果。

## Current Phase
Phase 5

## Phases

### Phase 1: 目录盘点与格式假设
- [x] 确认用户目标：为地图编辑器复原游戏地图
- [x] 盘点游戏目录与地图/资源候选文件
- [ ] 初步识别 exe、stage、dat、cel/atr 等格式关系
- **Status:** in_progress

### Phase 2: 静态分析 Emperor.exe
- [ ] 提取可读字符串、文件名引用、资源表
- [ ] 判断 exe 是否包含压缩/打包资源或仅引用外部文件
- [ ] 记录地图相关加载逻辑线索
- **Status:** pending

### Phase 3: 解析地图与资源文件
- [ ] 推断 `stageNN.*` 文件用途和尺寸
- [ ] 解析 tileset/图片资源容器
- [ ] 输出结构化地图数据说明
- **Status:** pending

### Phase 4: 复原地图渲染
- [ ] 编写可重复运行的解析/导出脚本
- [ ] 生成至少一个 stage 的地图预览图
- [ ] 对比已有 BMP/资源特征验证坐标、尺寸、调色板
- **Status:** pending

### Phase 5: 编辑器基础交付
- [ ] 整理格式文档
- [ ] 提供后续地图编辑器可用的数据模型或 viewer 原型
- [ ] 汇报已复原范围、限制和下一步
- **Status:** pending

## Key Questions
1. `stageNN.m/.s/.x/.stg/.spr/.dor/.evt` 分别保存什么数据？
2. `kingdom.cel/.atr`、`Graphics.dat`、`Selects.dat`、`windows.dat` 是否是地图 tileset/精灵容器？
3. `Emperor.exe` 中是否有可提取资源，还是主要提供文件格式和加载逻辑线索？
4. 地图尺寸、tile 尺寸、调色板和对象坐标如何编码？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 先做静态格式复原，再做编辑器 UI | 没有格式就无法可靠编辑，先拿到可验证的地图渲染闭环。 |
| 将脚本和导出结果放在项目根目录下的新工具/输出路径 | 避免改动原始游戏目录，便于重复运行和对比。 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Windows `python` 命令不可用 | 1 | 后续改用 Codex bundled runtime、可用 venv，或 PowerShell/Node 解析。 |

## Notes
- 原始游戏目录：`H:\Workstation\san\三国霸业`
- 需要保护原始资源文件，只读分析，导出结果另存。


## Update 2026-06-23 Recovery Milestone
- Phase 1/2/3/4 practical milestone reached: identified external map/resource formats, parsed `Emperor.exe` strings, decoded `.m` rendered maps, decoded `.s/.x` grids, and decoded DAT image containers.
- Phase 5 is in progress: delivered scripts, recovered outputs, format notes, and a local viewer prototype.
- Remaining work for a full editor: round-trip writing, semantic record decoding for `.stg/.spr/.dor/.evt`, and deeper `kingdom.cel/.atr` analysis.

## Update 2026-06-23 ACWZ Centering
- Added a focused alignment phase after user review: `acwz` city/object strips should be stitched with vertical centering, not bottom-only alignment.
- Created repeatable script `tools/stitch_kingdom_tiles.py`.
- Current preferred preview: `derived/kingdom/acwz_stitched_city_center.png`.
- Remaining related work: infer automatic `acwz` group boundaries across all 4,214 chunks and confirm sprite anchors against stage object placement.

## Update 2026-06-23 M Layer Export
- Shifted focus from acwz sprite stitching to editable .m multilayer map recovery.
- Added tools/export_m_layers.py and generated derived/m_layers for all stage*.m files.
- Next work: decode byte08/byte09 passability/terrain flags, byte10 object/state variants, and byte11 6x6 footprint subindex semantics.


## Update 2026-06-23 True CEL Map Rendering
- Corrected course after user review: m_layers is diagnostic index extraction, not visual reconstruction.
- Added tools/render_m_cel_map.py to draw real kingdom.cel acwx/acwy/acwz resources using Emperor.exe diamond scanline logic.
- Generated real map previews in derived/cel_maps; iso layout is the current valid renderer direction.
- Next: refine acwz z-order/footprint and extract exact world-to-screen transform from Emperor.exe.

