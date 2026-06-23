# Progress Log

## Session: 2026-06-23

### Phase 1: 目录盘点与格式假设
- **Status:** in_progress
- **Started:** 2026-06-23
- Actions taken:
  - 阅读 `planning-with-files` 技能说明。
  - 阅读浏览器控制技能说明，准备后续用于查看/验证地图渲染结果。
  - 盘点 `H:\Workstation\san` 和 `H:\Workstation\san\三国霸业`。
  - 发现大量 `stageNN.*` 关卡文件、`kingdom.cel/.atr`、`Graphics.dat` 等资源候选。
  - 尝试运行 planning session catchup，发现默认 `python` 命令不可用。
- Files created/modified:
  - `task_plan.md` (created)
  - `findings.md` (created)
  - `progress.md` (created)

### Phase 2: 静态分析 Emperor.exe
- **Status:** pending
- Actions taken:
  -
- Files created/modified:
  -

### Phase 3: 解析地图与资源文件
- **Status:** pending
- Actions taken:
  -
- Files created/modified:
  -

### Phase 4: 复原地图渲染
- **Status:** pending
- Actions taken:
  -
- Files created/modified:
  -

### Phase 5: 编辑器基础交付
- **Status:** pending
- Actions taken:
  -
- Files created/modified:
  -

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Directory inventory | `Get-ChildItem 三国霸业` | List candidate assets | Found stage files and resource containers | pass |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-06-23 | `python` command unavailable | 1 | Will locate bundled/runtime Python or use Node/PowerShell. |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 1: inventory and initial format hypotheses. |
| Where am I going? | Static exe analysis, resource parsing, then map rendering. |
| What's the goal? | Recover game map data and render output for a future map editor. |
| What have I learned? | Stage files are explicit candidates; fixed 25600-byte files are likely grids. |
| What have I done? | Read skills, listed files, created planning files. |

---
*Update after completing each phase or encountering errors*

## Update 2026-06-23 Asset Audit
- Located bundled Python through Codex workspace dependencies.
- Created and ran `tools/analyze_assets.py`.
- Confirmed `Emperor.exe` references stage/resource filenames and `.m` files are fixed-record maps.
- Test passed: `tools/analyze_assets.py 三国霸业` produced PE info, strings, file statistics, and fixed-record `.m` evidence.
- Error logged: Bash-style heredoc is invalid in PowerShell; switched to a repeatable Python script.

## Update 2026-06-23 Delivery Verification
- Wrote `docs/FORMAT_NOTES.md` with recovered file structures.
- Wrote `tools/export_map_previews.py` and ran it against the full game directory.
- Exported 33 `.m` map previews, 66 `.s/.x` grid previews, and 4 DAT resource sheets.
- Created `derived/viewer.html` for browsing recovered maps and layers.
- Started local static server on `127.0.0.1:8765` for browser verification because `file://` is blocked by the in-app browser policy.
- Browser verification passed: viewer loads 33 stages; default `stage01.m` reports 336x1072; switching to `stage20.s` reports 480x480 and updates button state.
- Errors encountered and resolved:
  - `view_image` was blocked by the Windows sandbox wrapper; used local runtime image emission for visual checks.
  - Browser blocked `file://`; used localhost server.
  - PowerShell expanded JavaScript template literals in generated HTML; rewrote with a placeholder replacement.

## Update 2026-06-23 Kingdom Tile Work
- Reclassified `.s/.x` as minimap/cache candidates rather than final editable tile maps, matching the user's observation.
- Decoded `kingdom.cel/.atr` structure:
  - ATR has 6-byte `acwx/acwy/acwz` attribute records.
  - CEL has fixed 20x20 `acwx/acwy` chunks and variable-size `acwz` object/building chunks.
- Created `tools/extract_kingdom.py` to export CEL/ATR tables, tile sheets, and `.m` field0 reconstruction maps.
- Generated `derived/kingdom/kingdom_atr_records.tsv`, `kingdom_cel_chunks.tsv`, `cel_acwx_sheet.png`, `cel_acwy_sheet.png`, `cel_acwz_sheet.png`, and `stageNN_field0_attr.png` files.
- Verified visually that `acwx/acwy` are terrain tiles and `acwz` contains isometric building/object slices.
- Verified `.m` record field0 is a primary ATR/tile index: field0 attr rendering preserves map structure and matches final rendered pixels substantially on many stages.

## 2026-06-23 ACWZ Center Alignment Pass
- Generated `derived/kingdom/acwz_align_compare.png` with bottom, center, and header-y alignment columns.
- Confirmed center alignment is visually better for city/object reconstruction.
- Generated `derived/kingdom/acwz_stitched_city_center.png` as the current preferred preview.
- Added `tools/stitch_kingdom_tiles.py` to make acwz center stitching and acwx/acwy 6x6 meta sheets repeatable.
- Updated `docs/FORMAT_NOTES.md` and `findings.md` with the acwz alignment and acwy uncertainty notes.

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
