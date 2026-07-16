# 本地数据目录

本目录用于存放用户自行从合法游戏副本中提取的运行与测试数据。游戏素材不属于本项目源码，实际文件不会提交到 Git。

## 目录结构

```text
data/
├── game/              # 原始二进制与 Big5 文本
│   ├── stage.ini
│   ├── stage01.m
│   ├── stage01.dor
│   ├── stage01.stg
│   ├── stage01.s
│   ├── stage01.x
│   ├── heads.dat
│   ├── History.txt
│   ├── general.txt
│   ├── kingdom.atr
│   └── kingdom.cel
└── text/              # 转换为 UTF-8 的文本表
    ├── castle.txt
    ├── general.txt
    ├── History.txt
    ├── soldier.txt
    └── 其他文本表
```

`stage01.*` 是当前编辑器集成测试的标准样本。其他 `stageNN.*` 可按研究需要自行补充。

## 正式发布程序边界

`data/game`、`data/text` 和下述环境变量只服务源码开发、格式分析与条件集成测试。正式 `SanMapEditor.exe` 不搜索这些目录，也不把它们作为回退。

最终用户应在启动器中显式选择 `stageNN.m` 或只含一个目标地图的目录。运行时同目录必须包含：

- `stageNN.m/.dor/.stg/.s/.x`
- `stage.ini`、`History.txt`
- `kingdom.cel`、`heads.dat`

`kingdom.atr` 可选。缺少其他任一文件、场景编号错配或重复文件时，启动器会拒绝创建临时会话。

## 自定义位置

无需复制文件时，可通过环境变量指定现有目录：

- `SAN_GAME_DATA_DIR`：原始游戏数据目录。
- `SAN_GAME_TEXT_DIR`：UTF-8 文本表目录。

路径优先级为环境变量、`data/` 标准目录、历史兼容目录。代码中不得再写入本机绝对路径。
