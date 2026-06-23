# Findings & Decisions

## Requirements
- 用户希望制作《三国霸业》地图编辑器。
- 当前任务重点是通过解析 `三国霸业/Emperor.exe` 并解包/解析游戏资源，复原游戏地图。
- 需要产出可复用的解析线索、资源解包结果和地图复原结果，为后续编辑器奠基。

## Research Findings
- 游戏目录包含大量显式地图关卡文件：`stageNN.dor/.evt/.m/.s/.spr/.stg/.x`。
- 多数 `stageNN.s` 和 `stageNN.x` 文件大小固定为 25600 字节，强烈暗示 160x160 单字节网格或 80x80 双字节网格。
- `stage01.m` 等 `.m` 文件体积较大且不同关卡间有重复大小，可能是预渲染地图块、压缩地图层或资源索引。
- `kingdom.cel` 约 9.1 MB，`kingdom.atr` 约 142 KB，可能是一组 CEL 图像/动画资源和属性表。
- `Emperor.exe` 大小约 487 KB，需静态提取字符串和 PE 资源来寻找格式加载逻辑。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 优先分析文件尺寸、熵、魔数、字符串引用 | 这是在不运行旧游戏 exe 的情况下最快建立格式假设的方法。 |
| 保留原始目录不写入，导出到工具目录或 `derived/` | 保护原始样本，方便重复分析。 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| 默认 `python` 不可用 | 将寻找 Codex bundled Python 或使用 PowerShell/Node 完成初期二进制解析。 |

## Resources
- 原始游戏目录：`H:\Workstation\san\三国霸业`
- 计划文件：`H:\Workstation\san\task_plan.md`
- 进展文件：`H:\Workstation\san\progress.md`

## Visual/Browser Findings
- 暂无浏览器或图像查看结果。

---
*Update this file after every 2 view/browser/search operations*
*This prevents visual information from being lost*

## Update 2026-06-23 Asset Audit
- Bundled Python is available at `C:\Users\mzhinf\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.
- `Emperor.exe` is a PE32 i386 executable with 4 sections: `.text`, `.rdata`, `.data`, `.rsrc`; resource directory RVA `0x9f000`, size 17904.
- `Emperor.exe` contains explicit filename references for `stage00.stg` through `stage46.stg`, `stage01.evt`, `stage01.dor`, `kingdom.cel`, `graphics.dat`, `windows.dat`, `selects.dat`, `heads.dat`, and editor-like filters `Text Files (*.STG)` / `ASCII Files (*.MAP)`.
- `.m` files have a clear structure: first 4 bytes width, next 4 bytes height, next 8 bytes ASCII `Hello1.0`, followed by `width * height` fixed 16-byte records. Examples: `stage20.m` = `112 * 356 * 16 + 16`, `stage39.m` = `126 * 400 * 16 + 16`, `stage01.m` = `336 * 1072 * 16 + 16`.
- `kingdom.cel` and `kingdom.atr` both start with count-like `0x1950` (6480) then `acwx`; `kingdom.atr` appears to repeat 6-byte attribute records containing the `acwx` marker and tile id/class bytes.
- `Graphics.dat`, `Selects.dat`, `windows.dat`, and `heads.dat` begin with a 32-bit count followed by monotonically increasing 32-bit offsets, suggesting indexed sprite/image containers.
- Issue: Bash-style heredoc failed in PowerShell; resolution was to create `tools/analyze_assets.py` as a repeatable script.

## Update 2026-06-23 Map Recovery Outputs
- `tools/export_map_previews.py` exports all available `.m` maps by default.
- Generated `derived/maps`: 33 recovered map PNGs.
- Generated `derived/grids`: 66 scaled logical grid previews from `.s` and `.x` files.
- Generated `derived/dat_sheets`: preview sheets for `Graphics.dat`, `Selects.dat`, `windows.dat`, and `heads.dat`.
- Visual verification: `stage01_m.png` reconstructs a complete colored campaign map with rivers, terrain, roads/settlements, and markers.
- Viewer created at `derived/viewer.html`; verified through `http://127.0.0.1:8765/viewer.html` with 33 stages and working M/S/X layer switching.
- Browser/file issues: direct `file://` was blocked by browser policy, so a local `127.0.0.1:8765` static server was used. The first viewer generation had PowerShell interpolation damage to JavaScript template literals; fixed with a placeholder-based HTML template.

## Update 2026-06-23 Kingdom Tile Work
- Reclassified `.s/.x` as minimap/cache candidates rather than final editable tile maps, matching the user's observation.
- Decoded `kingdom.cel/.atr` structure:
  - ATR has 6-byte `acwx/acwy/acwz` attribute records.
  - CEL has fixed 20x20 `acwx/acwy` chunks and variable-size `acwz` object/building chunks.
- Created `tools/extract_kingdom.py` to export CEL/ATR tables, tile sheets, and `.m` field0 reconstruction maps.
- Generated `derived/kingdom/kingdom_atr_records.tsv`, `kingdom_cel_chunks.tsv`, `cel_acwx_sheet.png`, `cel_acwy_sheet.png`, `cel_acwz_sheet.png`, and `stageNN_field0_attr.png` files.
- Verified visually that `acwx/acwy` are terrain tiles and `acwz` contains isometric building/object slices.
- Verified `.m` record field0 is a primary ATR/tile index: field0 attr rendering preserves map structure and matches final rendered pixels substantially on many stages.

## Update 2026-06-23 ACWZ Alignment
- User noted that `acwz` stitching should use vertical centering rather than simple bottom alignment.
- Generated `derived/kingdom/acwz_align_compare.png` comparing bottom, center, and naive header-y placement.
- Visual check confirms `center` alignment is the best current reconstruction for city/building sprites.
- `acwz` header's second integer often equals strip height, so it is not directly a final screen Y coordinate.
- Added `tools/stitch_kingdom_tiles.py`; it exports `acwz_stitched_city_center.png` and 6x6 `acwx/acwy` meta sheets.
- `acwx` consecutive 6x6 grouping looks like valid 120x120 terrain meta-tiles; `acwy` remains likely overlay/mask/transition data because 3x3/4x4/6x6 groupings all look fragmented.

## Update 2026-06-23 Emperor.exe ACWZ Draw Logic
- Installed and used Capstone to disassemble `Emperor.exe` locally.
- `kingdom.cel` loader is at file offset `0x27480` / VA `0x427480`.
- `acwz` draw branch is around file offset `0x19f0b` / VA `0x419f0b`.
- The draw branch reads the stage/map record word at `[record + 4]` as the `acwz` logical index, then looks up `0x473654[index]`.
- The decoded `acwz` header is used as anchor metadata:
  - `+0`: x anchor / x offset
  - `+4`: y anchor / y offset
  - `+8`: width
  - `+0x0c`: height
  - `+0x10`: temporary pixel buffer during load, freed after creating the surface
- Draw formula recovered from the exe: `dest_x = screen_x - header0`, `dest_y = screen_y - header1`, then width/height are clipped before DirectDraw Blt.
- For all 4,214 decoded `acwz` chunks, `header1 == height`, so every strip is bottom-anchored to its owning map cell baseline.
- Surface pointers are stored separately in a table around `0x4871fc`, with logical-to-surface short mapping at `0x47eaa8`.
- Generated `derived/kingdom/acwz_stitched_city_exe_anchor_x20.png`, a closer preview using `cell_x += 20`, `dest_x = cell_x - header0`, `dest_y = baseline - header1`, and transparent color 0 compositing.
- Remaining issue: a full city sprite is not a single image; it is multiple map cells referencing consecutive `acwz` strips. Exact vertical micro-alignment requires recovering each strip's real map cell `screen_y` from stage placement logic.

## Update 2026-06-23 M Record Multilayer Decode
- Rolled back the incorrect `acwz_stitched_city_exe_anchor_x20.png` experiment; current acwz stitching is parked, with `acwz_stitched_city_center.png` retained only as a visual reference.
- Corrected the kingdom resource model from a mixed marker scan to the counted block layout used by `Emperor.exe`:
  - `acwx` block: 6,480 logical slots, 2,052 ATR-present entries.
  - `acwy` block: 8,640 logical slots, 2,223 ATR-present entries.
  - `acwz` block: 17,280 logical slots, 2,069 ATR-present entries.
- `.m` record schema now has a stable first-pass interpretation:
  - `+0x00 int16`: `acwx` base terrain tile index; always present in observed stages.
  - `+0x02 int16`: `acwy` overlay/transition index; `-1` when absent.
  - `+0x04 int16`: `acwz` object/building/footprint index; `-1` when absent. Some non-negative entries point to empty logical slots, likely object footprint/occupancy cells.
  - `+0x06 int16`: observed zero in exported `.m` files.
  - `+0x08/+0x09`: auxiliary bytes; common values suggest terrain/object flags, not fully named yet.
  - `+0x0a`: variant/object byte. `Emperor.exe` compares this against `0x65..0x6e`, matching common values 101..110.
  - `+0x0b`: small subindex/group byte; often appears in 36-cell groups, likely footprint/subtile index.
  - `+0x0d`: final rendered palette index/cache byte.
  - `+0x0c/+0x0e/+0x0f`: observed zero in saved `.m` files; runtime renderer has mode/flag checks against related in-memory offsets.
- Added `tools/export_m_layers.py` to export editor-oriented layers under `derived/m_layers/`:
  - `acwx.i16`, `acwy.i16`, `acwz.i16`
  - `byte08.bin`, `byte09.bin`, `byte10.bin`, `byte11.bin`, `final_palette.bin`
  - `*_attr.png` previews and `meta.json` per stage
  - global `m_record_summary.tsv` and `kingdom_blocks.json`
- Visual layer check on `stage01` confirms: `acwx_attr` is the full base terrain; `acwy_attr` is contour/shore/road/transition overlay; `acwz_attr` is sparse object/city footprint placement.

## Update 2026-06-23 CEL-Based True Map Rendering
- User correctly pointed out that `derived/m_layers` previews are diagnostic/minimap-like because they visualize ATR `attr_hi` values rather than drawing real `kingdom.cel` resources.
- Recovered the real acwx/acwy terrain drawing pattern from `Emperor.exe`: fixed 400-byte CEL terrain chunks are packed diamond scanlines, not literal 20x20 square bitmaps.
- The executable uses a 20-row diamond table with row x-offset/packed-source/length:
  - lengths: `2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 38, 34, 30, 26, 22, 18, 14, 10, 6, 2`
  - x offsets: `19, 17, 15, 13, 11, 9, 7, 5, 3, 1, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19`
  - target terrain cell footprint: 40x20 pixels.
- Added `tools/render_m_cel_map.py`, which parses the counted `kingdom.cel` blocks and renders `.m` records using actual CEL pixels:
  - `field0` draws acwx base terrain diamonds.
  - `field1` draws acwy overlay/transition diamonds with zero as transparent.
  - `field2` draws acwz objects using the exe anchor rule `dest_x = screen_x - header0`, `dest_y = screen_y - header1`; current placement is first-pass and still needs z-order/footprint refinement.
- `iso` layout is the valid current direction. The simple `rect` layout was generated only for comparison and has visible diamond gaps.
- Generated real CEL map previews under `derived/cel_maps/`:
  - `stage20_iso_xy.png` / `stage20_iso_xy_thumb.png`
  - `stage20_iso_xyz.png` / `stage20_iso_xyz_thumb.png`
  - `stage01_iso_xyz_crop120000.png` / `stage01_iso_xyz_crop120000_thumb.png`
- `derived/m_layers/` remains useful as editable raw index/flag extraction, but it is not the final visual map reconstruction.
- Remaining renderer work: confirm exact viewport/world coordinate transform from the exe, improve acwz z-order and footprint handling, and add tile/object picking metadata for editor use.

## Update 2026-06-23 Stage11 Screenshot Calibration
- Initialized a local git repository and committed the current code/docs as `bc1021b` before making renderer changes.
- Compared the user-provided `derived/stage11.png` with renderer outputs.
- Recovered the viewport/world-to-screen transform from `Emperor.exe` around VA `0x419dc0`:
  - visible row screen y uses `row_offset * 10 + 10`
  - visible columns use x step `0x28` = 40 pixels
  - odd/even visible rows shift x by 20 pixels
  - the viewport clips against `0x230` = 560 pixels in the DirectDraw path
- Added `stagger` layout to `tools/render_m_cel_map.py`:
  - `screen_x = col * 40 + (20 if row is odd else 0)`
  - `screen_y = row * 10`
  - this is now the renderer default because it matches the actual game screenshot far better than the full diamond `iso` layout.
- Added `--flip-x`, `--crop X Y W H`, and `--scale N` options for viewport/camera comparison.
- Fixed acwx base tile compositing: inside the exe diamond scanline mask, acwx pixels are copied opaquely; acwy/acwz remain zero-color transparent overlays.
- Generated close stage11 comparison outputs:
  - `derived/cel_maps/stage11_stagger_xyz_scale2.png`
  - `derived/cel_maps/stage11_stagger_xyz_viewport93_57_1642_1684_scale2.png` (3284x3368, matching the screenshot dimensions)
- Remaining differences vs `stage11.png`: UI and soldiers are not part of `.m`/`kingdom.cel` terrain rendering; they must come from UI resources and `.spr`/unit systems. Some acwz z-order/footprint details still need refinement, but the terrain/world transform is now aligned.

## Update 2026-06-23 Palette Calibration
- Checked all BMP palettes and `Emperor.exe` resources/import strings after the user noticed rivers were not blue.
- `Emperor.exe` has no embedded bitmap resource palette; palette-related imports are GDI/DirectDraw system palette functions, and the executable references external BMP files.
- The current map CEL pixels use water-related indices `11/12/13`; `stage.bmp` maps those indices to bright green, while `BIGMAP01.bmp`/`mainmenu.bmp` map them to blue and match `derived/stage11.png`.
- Changed script defaults to `BIGMAP01.bmp` for map/resource preview generation. `stage.bmp` is still available via `--palette stage.bmp` for comparison.

## Update 2026-06-23 Editor Data Model
- The first editor bundle uses `.m` records as the authoritative editable table and preserves all 12 decoded fields per cell: `acwx`, `acwy`, `acwz`, `word06`, `byte08..byte12`, `final_palette`, `byte14`, `byte15`.
- The editor prototype writes JSON patch data rather than modifying original `.m` files. This keeps the round-trip path reversible while field semantics are still being decoded.
- Runtime palette selection now defaults to `tools/palette.py::SAN_RGB_PALETTE`, with BMP palette names remaining available for comparison.
