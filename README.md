# 三国霸业地图编辑器 2.0

本项目用于研究《三国霸业》地图与剧本文件，并提供可视化地图编辑、信息管理和二进制回写能力。当前正式数据模型严格对应 `src/san_tools/ksy/` 中的 `.m/.dor/.stg` 描述。

项目创建者：mzhinf

## 当前能力

- 导入 `stageXX.m`，自动加载同名 `.dor/.stg/.s/.x`、`stage.ini`、`History.txt` 与 `heads.dat`。
- 编辑底层、叠加、物件与数据标记，支持图层显示、撤销、重做、区域复制、剪切和合成对象。
- 管理势力、城池、军寨、山寨、城门、武将与士兵关联。
- 使用 `SAN_RGB_PALETTE` 渲染地图、小地图与武将头像。
- 导出 `.m/.dor/.stg/.ini/.s/.x` 及 ZIP 数据包。
- 对未确认的二进制字段采用原始字节保留和局部覆写策略。

编辑器已经可用于 `stage01` 样本，但二进制写回仍应在游戏副本中验证。已知限制见 [已知问题](docs/KNOWN_ISSUES.zh.md)。

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

## 准备数据

游戏素材不进入 Git。请从合法游戏副本中把所需文件放入以下目录：

```text
data/
├── game/    # stage.ini、stageXX.*、heads.dat、kingdom.cel/.atr、原始文本
└── text/    # 转换为 UTF-8 的 castle/general/History/soldier 等文本表
```

`stage01` 的最小清单和路径覆盖方法见 [本地数据说明](data/README.zh.md)。也可以设置：

```powershell
$env:SAN_GAME_DATA_DIR = "D:\Games\SGBY"
$env:SAN_GAME_TEXT_DIR = "D:\Games\SGBY\utf8-text"
```

把原始文本转换到标准目录：

```powershell
python -m san_tools run convert-game-texts -- --out data/text
```

## 启动编辑器

先导出 `stage01` 编辑器资源：

```powershell
python -m san_tools run export-editor-bundle . --stage stage01 --out derived/editor
```

随后打开 `derived/editor/index.html`。该目录是生成物，不提交到 Git。

构建 Windows 发布包：

```powershell
python -m pip install -e ".[release]"
python -m san_tools.map.build_editor_release . --stage stage01
```

输出位于 `dist/`。发布包可能含游戏素材，目前仅供本机使用，不应直接上传 GitHub Release。

## 命令入口

旧 `tools/` 转发入口已停止使用，所有正式命令通过统一入口执行：

```powershell
python -m san_tools list
python -m san_tools run analyze-dor data/game/stage01.dor --out derived/dor
python -m san_tools run analyze-stage-site-links . --stage stage01
python -m san_tools run export-stage-ini-workbook .
python -m san_tools run export-stg-workbook . --stage stage01
```

命令后的参数原样传给对应模块；如参数与统一入口冲突，可在命令名后加 `--`。

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

格式结论见 [二进制格式笔记](docs/FORMAT_NOTES.zh.md)，字段间转换见 [编辑器字段转换](docs/EDITOR_FIELD_CONVERSION.zh.md)，关联维护规则见 [编辑器数据管理](docs/EDITOR_DATA_MANAGEMENT.zh.md)。

## 贡献与许可

贡献前请阅读 [贡献指南](CONTRIBUTING.zh.md) 和 [项目维护约定](AGENTS.md)。当前源码采用保留所有权利的许可；如需改为开源许可证，应由版权所有者单独确认并替换 [LICENSE](LICENSE)。

本项目与原游戏权利方无关联，不提供任何游戏素材。完整说明见 [版权与项目关系说明](NOTICE.zh.md)。
