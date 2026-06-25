# Progress Log

## 2026-06-23

- 盘点游戏目录，确认 `stageNN.*`、`kingdom.cel/.atr`、DAT 容器与 `Emperor.exe` 为核心对象。
- 确认 `.m` 文件头为 `width + height + Hello1.0`，cell 记录固定 16 字节。
- 完成 `kingdom.cel/.atr` 的第一轮图层拆解。
- 恢复基于 `acwx/acwy/acwz` 的真实地图渲染。
- 从 `Emperor.exe` 收口 `stage11` 所需的 world-to-screen 变换。
- 建立浏览器地图编辑器原型，支持 Inspect / Paint / 本地 `.m` 加载 / Undo / Reset / patch 导出。

## 2026-06-24

- 补齐编辑器资源面板、即时重绘、右键拖动地图、方向键移动选中格。
- 完成安全 patch -> `.m` 复制写回脚本。
- 建立 `.stg/.evt/.spr/.dor/.s/.x` 的第一轮 sidecar 分析脚本与工作簿导出。
- 修复 `docs/FORMAT_NOTES.zh.md` 中的中文编码污染一次，但后续又发现其余文档仍有残留污染。
- 确认 `stage.ini` 可导出 JSON / Excel，并可从 JSON 回写字节级一致文件。

## 2026-06-25

- 重做 `uft8-game-txt` 与 `stage.ini` 的关联方式，改为基于原始 dword 流，而不是先信任 family_guess。
- 确认当前稳定映射：
  - `general.txt`：步长 `57 dwords`
  - `castle.txt`：步长 `25 dwords`
  - `magic.txt`：步长 `19 dwords`
  - `soldier.txt`：步长 `20 dwords`
- 区分分析版工作簿与纯转换版工作簿。
- 新增纯 Python 的 Excel 导出、导入、回写链路：
  - `tools/export_stage_ini_txt_workbook.py`
  - `tools/import_stage_ini_txt_workbook.py`
  - `tools/build_stage_ini_from_txt_workbook.py`
- 修复 Python 导出 `xlsx` 时的非法 XML 控制字符问题。
- 验证结果：
  - `stage_ini_linked_tables.xlsx` 可由 Python 正常导出
  - `stage_ini_conversion_tables.xlsx` 可由 Python 正常导出
  - 未修改的 `stage_ini_conversion_tables.xlsx` 可回写为与原始 `stage.ini` 完全一致的新文件
  - `sha256 = 29584de26770323a09849d180331d936e9c112f55936d76b08f4f6f6a63663b8`

## 本次文档收口（已完成）

- `README.md` 已重写为干净 UTF-8 中文版本。
- `docs/FORMAT_NOTES.zh.md` 已重写，并单列 `stage.ini` 二进制构成。
- 新增 `docs/DOC_WORKFLOW.zh.md`，把文档更新责任和提交前检查表写死。
- `task_plan.md`、`findings.md`、`progress.md` 已同步为新的有效基线。
- 验证：Python 按 UTF-8 读取上述文档成功，确认乱码来自控制台代码页而非文件内容。

## 验证记录

| 项目 | 结果 |
| --- | --- |
| `stage.ini` JSON -> binary 回写 | 字节级一致 |
| `stage_ini_conversion_tables.xlsx -> stage.ini` 回写 | 字节级一致 |
| 编辑器本地 `.m` 加载 | 通过 |
| 编辑器 patch 写回复制件 | 通过 |
| 核心文档 UTF-8 读取 | 通过 |

## 当前风险

1. `.stg` / `.evt` 仍未完成字段命名，暂时不能做完整语义编辑器。
2. `.s/.x` 的写回流程尚未确认，不应贸然生成覆盖。
3. `acwz` 的完整 footprint / z-order 仍有尾差。