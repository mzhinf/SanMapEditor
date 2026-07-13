# 命令执行参考

更新日期：2026-07-14

本文档覆盖 `src/san_tools/cli/command_registry.py` 中全部公开命令。命令名称、模块和摘要以注册表为准，参数以各命令实时 `--help` 为准；两者变化时必须同步更新本文档。

## 1. 基本用法

在仓库根目录安装开发依赖：

```powershell
python -m pip install -e ".[dev]"
```

列出公开命令：

```powershell
python -m san_tools list
```

执行命令：

```powershell
python -m san_tools run <命令名> [参数]
```

查看某个命令的实时参数：

```powershell
python -m san_tools run export-editor-bundle -- --help
```

命令名后的参数会原样传给目标模块。`--` 通常可以省略；当参数可能被统一入口解释时保留它。

安装项目后也可以把 `python -m san_tools` 换成 `san-tools`：

```powershell
san-tools list
san-tools run render-map . --stage stage01
```

## 2. 数据目录与输出规则

命令默认从以下位置查找用户自备数据：

| 数据 | 默认目录 | 环境变量 |
| --- | --- | --- |
| 游戏二进制与资源 | `data/game` | `SAN_GAME_DATA_DIR` |
| UTF-8 文本表 | `data/text` | `SAN_GAME_TEXT_DIR` |

命令中的可选 `root` 通常表示项目根目录，默认是当前目录 `.`。研究结果默认写入 `derived/`，工作簿默认写入 `outputs/`，发布包默认写入 `dist/`；这些目录均不应提交到 Git。

除非明确指定输出文件覆盖原文件，命令默认生成新文件。涉及二进制回写时仍应先复制原文件，并优先使用 `--dry-run` 或 `--compare-with` 验证。

## 3. 地图、编辑器与资源命令

| 命令 | 最小示例 | 主要参数与默认产物 | 类型 |
| --- | --- | --- | --- |
| `render-map` | `python -m san_tools run render-map . --stage stage01` | `--layout`、`--layers`、`--crop X Y W H`、`--scale`；输出到 `derived/cel_maps` | 只读导出 |
| `export-editor-bundle` | `python -m san_tools run export-editor-bundle . --stage stage01` | `--all` 可导出全部关卡；输出到 `derived/editor` | 只读导出 |
| `apply-editor-patch` | `python -m san_tools run apply-editor-patch path/to/stage01_patch.json . --dry-run` | `--source` 指定源 `.m`，`--out` 默认 `derived/edited`，默认同步 `.s/.x` | 二进制写回 |
| `build-minimap-sidecars` | `python -m san_tools run build-minimap-sidecars . --stage stage01` | `--stage` 可重复，`--all` 批量处理，输出到 `derived/minimap_sidecars` | 二进制生成 |
| `export-map-previews` | `python -m san_tools run export-map-previews . --stage stage01` | `--stage` 可重复；输出到 `derived` | 只读导出 |
| `extract-kingdom` | `python -m san_tools run extract-kingdom .` | `--palette`、`--sheet-limit`；输出到 `derived/kingdom` | 只读导出 |
| `stitch-kingdom` | `python -m san_tools run stitch-kingdom .` | `--acwz-align center|bottom|top`；输出到 `derived/kingdom` | 只读导出 |
| `export-m-layers` | `python -m san_tools run export-m-layers .` | `--palette`；输出到 `derived/m_layers` | 只读导出 |
| `build-editor-release` | `python -m san_tools run build-editor-release . --stage stage01` | 工作目录 `derived/editor-release`，发布目录 `dist` | 发布构建 |
| `launch-editor` | `python -m san_tools run launch-editor --data-dir derived/editor --stage stage01` | `--no-browser` 禁止自动打开浏览器，`--check` 只检查数据 | 本地启动 |

### Patch 写回建议

先检查 Patch 与源地图是否匹配：

```powershell
python -m san_tools run apply-editor-patch path/to/stage01_patch.json . --dry-run
```

确认后写入单独目录，并生成小地图预览：

```powershell
python -m san_tools run apply-editor-patch path/to/stage01_patch.json . `
  --out derived/edited/stage01.m `
  --sidecar-preview
```

`--force` 会跳过 Patch 的旧值冲突检查，只应在人工核对差异后使用。`--no-minimap-sidecars` 会只写 `.m`，不会同步生成 `.s/.x`。

### Windows 发布包

发布构建需要额外安装依赖：

```powershell
python -m pip install -e ".[release]"
python -m san_tools run build-editor-release . --stage stage01
```

构建命令会重建指定工作目录，因此 `--work-dir` 必须位于项目目录内；发布目录默认是 `dist/`。

## 4. 格式与关联分析命令

| 命令 | 最小示例 | 主要参数与默认产物 | 状态 |
| --- | --- | --- | --- |
| `analyze-assets` | `python -m san_tools run analyze-assets data/game` | `--strings-limit` 控制 EXE 字符串输出数量；结果写到终端 | 研究工具 |
| `analyze-sidecars` | `python -m san_tools run analyze-sidecars . --stage stage01` | `--stage` 可重复；JSON 写到终端 | 研究工具 |
| `analyze-stg-family-alignment` | `python -m san_tools run analyze-stg-family-alignment .` | 输出 `derived/sidecar_analysis/stg_family_alignment.json` | 旧记录视图 |
| `analyze-evt-resources` | `python -m san_tools run analyze-evt-resources . --stage stage17` | 输出 `derived/sidecar_analysis/evt_resource_linkage.json` | 研究工具 |
| `analyze-dor` | `python -m san_tools run analyze-dor data/game/stage01.dor` | `--out` 指定 JSON 输出目录 | 已确认结构 |
| `analyze-stage-site-links` | `python -m san_tools run analyze-stage-site-links . --stage stage01` | 输出 `derived/dor_analysis/site_links` | 关联分析 |
| `analyze-stg-field-values` | `python -m san_tools run analyze-stg-field-values data/game/stage01.stg` | `--strict-parse` 遇到错误立即退出；输出到 `derived/stg_field_statistics` | KSY 字段统计 |
| `analyze-m-byte-fields` | `python -m san_tools run analyze-m-byte-fields . --stage stage01` | 分析原始 `+0x08..+0x0F`；输出到 `derived/m_byte_fields` | 原始偏移研究 |
| `analyze-minimap-sidecars` | `python -m san_tools run analyze-minimap-sidecars . --stage stage01` | 输出 `derived/sidecar_analysis/minimap_sidecar_analysis.json` | 研究工具 |
| `analyze-minimap-color-relation` | `python -m san_tools run analyze-minimap-color-relation .` | 输出 `derived/minimap_color_relation/report.json` | 统计模型 |
| `export-sidecar-tables` | `python -m san_tools run export-sidecar-tables . --stage stage01` | 输出 `derived/sidecar_analysis/stage_sidecar_tables.json` | 旧记录视图 |

`analyze-stg-family-alignment` 与 `export-sidecar-tables` 基于早期固定记录分析视图，只用于研究和兼容，不是 `.stg` 正式字段规范。正式字段、类型和顺序以 `src/san_tools/ksy/stg.ksy` 为准。

## 5. stage.ini 与文本母表命令

| 命令 | 最小示例 | 默认产物 | 类型 |
| --- | --- | --- | --- |
| `export-stage-ini-json` | `python -m san_tools run export-stage-ini-json .` | `derived/stage_ini_analysis/stage_ini_tables.json` | 只读导出 |
| `export-stage-ini-txt-tables` | `python -m san_tools run export-stage-ini-txt-tables .` | `derived/stage_ini_txt_analysis/stage_ini_txt_links.json` | 只读导出 |
| `build-stage-ini` | `python -m san_tools run build-stage-ini derived/stage_ini_analysis/stage_ini_tables.json` | `derived/stage_ini_analysis/stage.ini` | 二进制写回 |
| `export-stage-ini-workbook` | `python -m san_tools run export-stage-ini-workbook .` | `outputs/stage_ini_txt_analysis/*.xlsx` | 工作簿导出 |
| `import-stage-ini-workbook` | `python -m san_tools run import-stage-ini-workbook --input outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx` | `derived/stage_ini_txt_analysis/stage_ini_txt_workbook_import.json` | 工作簿导入 |
| `build-stage-ini-from-workbook` | `python -m san_tools run build-stage-ini-from-workbook outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx .` | `derived/stage_ini_txt_analysis/stage_ini_from_workbook.ini` | 二进制写回 |

验证未修改 JSON 能否逐字节重建：

```powershell
python -m san_tools run export-stage-ini-json .
python -m san_tools run build-stage-ini `
  derived/stage_ini_analysis/stage_ini_tables.json `
  --compare-with data/game/stage.ini
```

工作簿闭环：

```powershell
python -m san_tools run export-stage-ini-workbook .
python -m san_tools run import-stage-ini-workbook `
  --input outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx
python -m san_tools run build-stage-ini-from-workbook `
  outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx . `
  --compare-with data/game/stage.ini
```

`History.txt` 只用于补充武将资料，不自动写入 `stage.ini`。工作簿只回写已确认映射的数值字段，未识别字节应保持原值。

## 6. STG 命令

| 命令 | 最小示例 | 默认产物 | 状态 |
| --- | --- | --- | --- |
| `export-stg-raw-chain` | `python -m san_tools run export-stg-raw-chain . --stage stage01` | `derived/sidecar_analysis/raw_chain` | 76 字节兼容视图 |
| `export-stg-hierarchy` | `python -m san_tools run export-stg-hierarchy . --stage stage01` | `derived/sidecar_analysis/hierarchy` | 层级分析 |
| `export-stg-city-troop` | `python -m san_tools run export-stg-city-troop . --stage stage01` | `derived/sidecar_analysis/city_troop` | 候选字段分析 |
| `export-stg-workbook` | `python -m san_tools run export-stg-workbook . --stage stage01` | `outputs/stg_workbooks/stage01_stg.xlsx` | 76 字节兼容视图 |
| `roundtrip-stg-json` | `python -m san_tools run roundtrip-stg-json data/game/stage01.stg` | `derived/stg_json_roundtrip` | 当前块流模型 |
| `import-stg-workbook` | `python -m san_tools run import-stg-workbook outputs/stg_workbooks/stage01_stg.xlsx .` | `derived/sidecar_analysis/stg_workbooks/stage_from_workbook.stg` | 76 字节兼容写回 |
| `export-stg-phase7` | `python -m san_tools run export-stg-phase7 . --stage stage01` | `derived/sidecar_analysis/phase7/stage01` | 历史研究视图 |

当前推荐使用 `roundtrip-stg-json` 验证 KSY 块流模型：

```powershell
python -m san_tools run roundtrip-stg-json data/game/stage01.stg `
  --json-out derived/stg_json_roundtrip/stage01.json `
  --stg-out derived/stg_json_roundtrip/stage01.stg
```

重要参数：

- `--include-words`：在 JSON 中附带 block 的 `u32/i32` 视图。
- `--no-strict`：关闭严格结构校验，只用于研究异常样本。
- `--strip-reserved-fields`：只从 JSON 表示中移除保留字段，不应被理解为清空原始字节。
- `--zero-reserved-zero-fields`：把明确标为固定零的字段写成零，会改变输出二进制，使用前必须保留原文件。
- `--no-recompute-counts`：关闭势力、据点和实体计数重算，通常不应在结构变更后使用。
- `--no-patch-fields`：不把 JSON 字段修改覆写回 `raw_hex`。

`export-stg-raw-chain`、`export-stg-workbook`、`import-stg-workbook` 和 `export-stg-phase7` 是历史兼容链路。它们不替代 KSY 字段级模型，也不应用于新增对象流结构。

## 7. 文本编码命令

| 命令 | 最小示例 | 说明 |
| --- | --- | --- |
| `convert-game-texts` | `python -m san_tools run convert-game-texts -- --out data/text` | 自动查找 `data/game`，批量生成 UTF-8 文本表 |
| `encode-convert` | `python -m san_tools run encode-convert input output big5_to_utf8` | 对任意目录执行 `big5_to_utf8` 或 `utf8_to_big5` |

指定非标准游戏目录：

```powershell
python -m san_tools run convert-game-texts `
  --game-dir path/to/game `
  --out data/text
```

`encode-convert` 是通用目录转换器，会递归写入目标目录。反向转换时应使用新的输出目录，避免把 UTF-8 参考表与 Big5 游戏文件混在一起。

## 8. 命令维护要求

1. 新增具有 `main()` 和 `argparse` 的公开模块时，必须加入统一注册表和本文档。
2. 删除或改名命令时，必须同步修改 README、本文档、CHANGELOG 和相关测试。
3. 每个注册命令必须通过 `tests/test_command_registry.py` 的 `--help` 可用性检查。
4. 命令默认路径变化时，必须同步修改本文档中的默认产物。
5. 研究命令必须标明“当前模型”“兼容视图”或“历史研究视图”，不能与 KSY 正式规范混用。
