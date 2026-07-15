# 三国霸业地图编辑器 2.0

本项目用于研究《三国霸业》地图与剧本文件，并提供可视化地图编辑、信息管理和二进制回写能力。当前正式数据模型严格对应 `src/san_tools/ksy/` 中的 `.m/.dor/.stg` 描述。

项目创建者：mzhinf

## 当前能力

- 导入 `stageXX.m`，只从同一目录加载同名 `.dor/.stg/.s/.x`、`stage.ini`、`History.txt`、`kingdom.cel`、`heads.dat` 与可选的 `kingdom.atr`。
- 编辑底层、叠加、物件与数据标记，支持图层显示、撤销、重做、区域复制、剪切和合成对象。
- 管理势力、城池、军寨、山寨、城门、武将与士兵关联。
- 使用 `SAN_RGB_PALETTE` 渲染地图、小地图与武将头像；小地图颜色随 xyz 自动派生，并允许 Raw 手工修正。
- 导出 `.m/.dor/.stg/.ini/.s/.x` 及 ZIP 数据包。
- 对未确认的二进制字段采用原始字节保留和局部覆写策略。

编辑器已经可用于 `stage01` 样本，但二进制写回仍应在游戏副本中验证。发布包使用方法见 [编辑器使用指南](docs/EDITOR_USER_GUIDE.zh.md)，发布维护者参阅 [Windows 打包链路](docs/EDITOR_PACKAGING_CHAIN.zh.md)，已知限制见 [已知问题](docs/KNOWN_ISSUES.zh.md)。

## 环境要求

- Windows 10/11
- Python 3.11 或更高版本
- Node.js 仅用于少量浏览器脚本集成测试
- 构建 EXE 时需要 PyInstaller

推荐使用 uv：

```powershell
git clone <仓库地址>
cd san
uv sync --extra dev
uv run python -m san_tools list
```

也可使用普通虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m san_tools list
```

## 准备运行时数据

正式发布 ZIP 不包含任何游戏地图、头像、文本、调色板文件或派生图片。最终用户应从自己合法取得的游戏副本中选择资源，不需要把文件复制到仓库目录。

单个关卡的完整导入清单如下；除 `kingdom.atr` 外均为必需文件，且应位于同一目录：

| 文件 | 用途 |
| --- | --- |
| `stageXX.m` | 地图尺寸与 Cell 数据；可直接在启动器中选择。 |
| `stageXX.dor`、`stageXX.stg` | 城门、势力、据点、武将和士兵。 |
| `stageXX.s`、`stageXX.x` | 小地图有效区与必须保留的用户原始尾区。 |
| `stage.ini`、`History.txt` | 城池、武将母表和历史记录。 |
| `kingdom.cel`、`heads.dat` | 地图资源和头像；图集只在系统临时会话中生成。 |
| `kingdom.atr` | 可选的资源属性研究数据。 |

`stageXX` 必须使用相同场景编号。目录中有多个 `.m` 时应直接选择目标 `.m`，启动器不会静默选取。
选择单个 `.m` 时只匹配上表文件，不会加载同目录中的其他关卡，不会遍历子目录，也不会回退读取仓库或环境变量中的默认游戏目录。

源码开发和格式研究仍可使用忽略目录 `data/game`、`data/text` 或 `SAN_GAME_DATA_DIR`、`SAN_GAME_TEXT_DIR`；这些开发路径不是正式发布程序的运行时回退。

## 启动编辑器

使用正式发布包：

1. 完整解压 ZIP，保持 `SanMapEditor.exe` 与 `editor-data` 同级。
2. 双击 EXE。浏览器先显示“尚未导入地图项目”，桌面启动器显示资源选择按钮。
3. 选择 `stageXX.m`，或选择只含一个 `stageXX.m` 的完整资源目录。
4. 启动器校验全部同组文件，在 `%TEMP%/SanMapEditor` 生成当前会话并打开编辑页。
5. 重新选择资源会要求确认；新导入失败时旧会话保持可用。
6. 关闭启动器会停止本机 HTTP 服务并删除当前临时会话。编辑结果必须先导出。

发布程序只监听 `127.0.0.1` 的随机端口，不会把编辑器暴露到局域网。

源码开发时仍可显式生成样本 Bundle：

```powershell
python -m san_tools run export-editor-bundle . --stage stage01 --out derived/editor
```

构建无资源 Windows 发布包：

```powershell
python -m pip install -e ".[release]"
python -m san_tools run build-editor-release .
```

构建不读取 `data/game` 或 `data/text`。`dist/` 中生成 ZIP、外部 SHA-256 清单和构建结果 JSON；ZIP 只允许 EXE、空入口、发布元数据、短说明和完整使用指南五个文件。公开发布前仍需完成资源审计、合法游戏副本人工兼容性验证，并对源码内 `SAN_RGB_PALETTE` 的发布边界作法律确认。

## 命令入口

旧 `tools/` 转发目录已移除，所有正式命令通过统一入口执行：

```powershell
python -m san_tools list
python -m san_tools run analyze-dor data/game/stage01.dor --out derived/dor
python -m san_tools run analyze-stage-site-links . --stage stage01
python -m san_tools run export-stage-ini-workbook .
python -m san_tools run export-stg-workbook . --stage stage01
```

命令后的参数原样传给对应模块；如参数与统一入口冲突，可在命令名后加 `--`。全部命令、参数、产物和风险说明见 [命令执行参考](docs/COMMAND_REFERENCE.zh.md)。

## 测试

```powershell
python -m unittest discover -s tests -v
```

单元测试不依赖游戏素材。需要真实样本的集成测试会通过统一数据路径查找文件，在干净克隆或 CI 中缺少素材时明确跳过。

## 项目结构

```text
src/san_tools/
├── analysis/     # 格式统计与关系分析
├── cli/          # 统一命令注册表
├── codecs/       # 二进制编解码与 roundtrip
├── ksy/          # .m/.dor/.stg 规范描述
├── map/          # 编辑器、地图渲染与回写
├── pipelines/    # JSON、工作簿和二进制转换管线
└── text/         # 游戏文本编码转换
```

文档职责与阅读顺序见 [文档索引](docs/DOCUMENT_INDEX.zh.md)。格式结论见 [二进制格式笔记](docs/FORMAT_NOTES.zh.md)，字段间转换见 [编辑器字段转换](docs/EDITOR_FIELD_CONVERSION.zh.md)，关联维护规则见 [编辑器数据管理](docs/EDITOR_DATA_MANAGEMENT.zh.md)，重要演进记录见 [项目历史](docs/PROJECT_HISTORY.zh.md)。

## 贡献与许可

贡献前请阅读 [贡献指南](CONTRIBUTING.zh.md) 和 [项目维护约定](AGENTS.md)。当前源码采用保留所有权利的许可；如需改为开源许可证，应由版权所有者单独确认并替换 [LICENSE](LICENSE)。

本项目与原游戏权利方无关联，不提供任何游戏素材。完整说明见 [版权与项目关系说明](NOTICE.zh.md)。
