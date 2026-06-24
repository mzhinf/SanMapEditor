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

## Update 2026-06-23 Editor Resource Palettes And Minimap

The editable visual map is built from `stageNN.m` records plus `kingdom.cel` pixels:

- `record + 0x00 int16 acwx`: base terrain diamond. This is the ground layer and should generally be present for every map cell.
- `record + 0x02 int16 acwy`: transparent overlay/transition diamond. This carries shorelines, road/edge/transition details, and is `-1` when absent.
- `record + 0x04 int16 acwz`: object/building strip or footprint reference. It is rendered with the CEL anchor rule and may be `-1`; some non-negative values are occupancy/footprint cells.

Editor implications:

- Replacement cannot be numeric-only; the editor must expose resource palettes for `acwx`, `acwy`, and `acwz` so the user sees the actual drawable graphic before painting.
- `tools/export_editor_bundle.py` now exports `resources.json` and atlas PNGs for all drawable entries in those three layers. Current-stage used resources are sorted first and include a `used` count.
- The minimap should be treated as a derived view, not an unrelated bitmap. A terrain/object edit marks the affected cells as minimap-dirty; later write-back should regenerate the minimap/cache representation from the same `.m` record table, and only then update `.s/.x` if those files are confirmed as game minimap/cache outputs.


## Editor Notes 2026-06-24

`stage11.m` is not all `-1` on the overlay/object layers. The current export contains:

- `acwy`: 1702 non-empty cells, 391 distinct non-empty ids.
- `acwz`: 744 non-empty cells, 133 distinct non-empty ids.

These layers are sparse by design. `acwx` is the base terrain and is present on every cell; `acwy` is an optional transparent overlay/transition layer; `acwz` is an optional object/building/footprint reference. A tall `acwz` sprite can cover neighboring cells, so clicking a visible building pixel may inspect a neighboring ground cell whose own `acwz` value is still `-1`. The editor now shows nearby non-empty `acwy/acwz` anchors in the Cell panel to make this clearer.

Resource list behavior:

- The generated resource catalog is sorted by numeric index by default.
- The editor can switch between numeric order and current-stage usage order.
- A label like `123 x7` means resource index `123` appears 7 times in the current `.m` file.

Tool modes:

- Inspect: select a cell and show its decoded `.m` record without changing data.
- Paint: write the current resource index into the active layer for the selected cell.
- Pan: drag the map view.

Next implementation plan for lower-priority items:

1. Live redraw edits: export draw-ready CEL tile/object atlases, add an overlay canvas, and repaint dirty cells immediately using the same stagger transform as `render_m_cel_map.py`. `acwx` redraw replaces the base diamond, `acwy` draws transparent overlay pixels, and `acwz` uses the recovered anchor rule plus local z-order refresh.
2. Select/load `.m` files: add an editor index page for exported stages first, then add a browser File API path that parses `Hello1.0` `.m` files locally and pairs them with the already exported `kingdom.cel` resource catalog.
3. Minimap/cache write-back: treat minimap as derived from edited `.m` records first. Continue `Emperor.exe` xref research before writing `.s/.x`; current evidence says they are minimap/cache-like, but the exact write-back mapping is not confirmed yet.


## Live Redraw Update 2026-06-24

The editor now exports draw-ready CEL atlases in addition to thumbnail resource sheets:

- `draw_acwx.png`: original 40x20 base terrain diamonds.
- `draw_acwy.png`: original 40x20 transparent overlay diamonds, with palette index 0 transparent.
- `draw_acwz.png`: packed original object/building sprites, preserving `xAnchor/yAnchor` metadata.

`resources.json` is now `san-editor-resources-v2`. Each resource entry keeps the thumbnail `atlas` rectangle for the resource browser and a `draw` rectangle for live map rendering.

The browser editor now rebuilds an offscreen editable map image from the current `.m` records whenever Paint changes a cell. It draws the three layers in the same order as the renderer: all `acwx`, then all `acwy`, then all `acwz`; `acwz` uses `screen_x + 20 - xAnchor` and `screen_y + 20 - yAnchor`. Patch and selection markers are now outlines only, so they do not hide the edited tile pixels.

Verification: regenerated `derived/editor/stage11`, loaded `http://127.0.0.1:8787/stage11/editor.html`, performed a real Paint action through the browser UI, and confirmed the clicked region screenshot changed (`byteDiff=901`) while the patch list changed to one dirty edit.

Known limitation: the first live-redraw version rebuilds the whole stage image after each Paint. This is simple and correct for the current `stage11` bundle, but a later pass should redraw only a dirty neighborhood and improve `acwz` footprint/z-order refresh for larger maps.


## Undo And Reset Update 2026-06-24

The editor now keeps an immutable copy of the original `.m` records and computes patches against that baseline. This fixes repeated edits to the same cell/layer: the patch `before` value remains the original value, while `after` follows the current edited value.

Edit controls:

- `Ctrl+Z` / `Undo`: undo the most recent edit transaction.
- `Reset cell`: reset the currently selected cell on the currently selected layer (`acwx`, `acwy`, or `acwz`) back to the original `.m` value.
- `Reset all`: reset every current patch back to the original `.m` values.
- Reset operations are also transactions, so `Ctrl+Z` after `Reset all` restores the reset batch.

Verification: in the browser editor, Paint produced one patch, `Ctrl+Z` returned to zero patches, `Reset cell` returned one selected-layer patch to zero, `Reset all` returned two patches to zero, and `Ctrl+Z` after `Reset all` restored those two patches.


## Stage And Local `.m` Loading Update 2026-06-24

The editor now supports two map-loading paths:

- Exported stage picker: each generated `editor.html` reads `../index.json` and shows a Stage dropdown. Selecting another exported stage navigates to that stage's editor bundle.
- Local `.m` loader: `Open .m` reads a user-selected `Hello1.0` `.m` file in the browser, parses its 16-byte records, resets edit history, and rebuilds the map directly from the already loaded CEL draw atlases.

The local `.m` path does not require a pre-rendered `map.png`; canvas dimensions are derived from the `.m` header using the recovered stagger layout: `width * 40 + 20 + 128` by `height * 10 + 20 + 128`. The minimap falls back to the live rendered map when no generated `minimap.png` exists.

`tools/export_editor_bundle.py` also has a new `--all` option:

```powershell
& $py tools/export_editor_bundle.py . --all
```

This exports every `stage*.m` bundle and writes `derived/editor/index.html` plus `derived/editor/index.json`. Be aware that current bundles still include resource atlases per stage, so exporting all stages is useful but disk-heavy until resource atlases are moved to a shared directory.

Verification: regenerated `stage11` and `stage20`, loaded `stage11/editor.html`, confirmed the Stage dropdown showed both exported stages, and confirmed `derived/editor/index.html` lists exported stage editors.


## Patch-To-`.m` Copy Writing 2026-06-24

`tools/apply_editor_patch.py` applies an exported `san-editor-patch-v1` JSON patch to a copied `.m` file. It never overwrites the original game directory by default.

Typical use:

```powershell
& $py tools/apply_editor_patch.py derived/editor/stage11_patch.json . --out derived/edited
```

Useful options:

- `--dry-run`: validate the patch and source `.m` without writing.
- `--source path/to/stageNN.m`: use an explicit source `.m`, useful for patches exported from a locally opened `.m` file.
- `--out derived/edited`: write `derived/edited/<stage>.m`; if `--out` ends with `.m`, it is treated as the exact output path.
- `--force`: apply even when a patch `before` value does not match the source `.m`; normally this mismatch is refused.

Safety behavior:

- The source `.m` must be a `Hello1.0` map file.
- Every change cell must be within the source map bounds.
- Every `before` value is checked against the source file before writing.
- Supported fields match the editor record schema: `acwx/acwy/acwz/word06/byte08..byte15/final_palette`.

Verification: a synthetic `stage11` patch changed cell `0,1 acwx` from `36` to `37` in `derived/edited_test/stage11.m`; a mismatched patch was rejected with a JSON error and no output write.

## Update 2026-06-24 Sidecar Semantic Strings
- Using the upgraded `tools/analyze_stage_sidecars.py`, `.stg` now clearly exposes more than a scenario title. Sampled string previews include city names (`平原`, `荊州`, `襄陽`, `南郡`), general names (`劉備`, `關羽`, `諸葛亮`), troop labels (`步兵`, `弓箭兵`), and faction text (`中立國家`).
- The 76-byte `.stg` record preview suggests a mixed entity table rather than one uniform record kind: early records look like scenario/faction metadata, later records surface city names, then general names, then troop names.
- `.evt` string previews surfaced explicit objective/prompt/dialogue phrases such as `勝利`, `失敗`, `佔領四郡`, `敵兵全死`, `黃忠加入提示`, `劉備出現`, and `到達涿縣`. Together with `talk` / `VIEW`, this strongly supports a script-command layer with embedded or referenced text parameters.
- `.spr` is optional by stage: `stage01.spr` contains only the `Soldier Data` magic plus the stable `180/36` meta dwords and then zeroes. `.dor` is also optional by stage: `stage11.dor` is only 28 bytes and has an all-zero body after the header.
