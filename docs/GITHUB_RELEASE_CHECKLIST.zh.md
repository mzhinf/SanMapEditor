# GitHub 上传与 Release 发布清单

更新日期：2026-07-16

## 当前结论

源码仓库可继续公开推送；Windows 构建已改为五文件无资源包，并有目录、ZIP、PyInstaller TOC 扫描和 SHA-256 清单。公开上传 Release 前仍需完成合法游戏副本人工兼容性验证、`SAN_RGB_PALETTE` 发布边界确认和许可证决策。

## Git 历史与工作区

- [ ] 目标分支历史不存在 GitHub 100 MiB 单文件阻断。
- [ ] `git status --short` 只含预期源码和文档。
- [ ] `data/game*`、`data/text*`、`derived/`、`dist/`、`outputs/`、ZIP、EXE 和工作簿未暂存。
- [ ] 已扫描令牌、私钥、本机路径、缓存和误提交二进制。

## 无资源发布构建

- [ ] 使用干净工作目录执行 `python -m san_tools run build-editor-release .`，不得带 `--stage`。
- [ ] 构建未读取 `data/game`、`data/text` 或游戏安装目录。
- [ ] ZIP 精确包含：

```text
SanMapEditor.exe
editor-data/index.html
editor-data/release-info.json
使用说明.txt
编辑器使用指南.md
```

- [ ] ZIP 不含 `stageNN/`、`index.json`、游戏扩展名、`map.png`、`minimap.png`、`heads.png` 或图集。
- [ ] 目录与 ZIP 的路径、字节数、SHA-256 一致。
- [ ] Analysis、EXE、PKG、PYZ TOC 通过禁用资源扫描。
- [ ] 外部 Manifest 记录 ZIP 大小、SHA-256 和 TOC。
- [ ] 正式 EXE `--check` 返回 0。

## 运行时验收

- [ ] 空项目、导入中、失败、已加载四态正确。
- [ ] 完整 `stageNN` 输入可在系统临时目录生成地图、资源、小地图和头像。
- [ ] 缺失、重复、编号错配或损坏文件显示明确错误。
- [ ] 重新选择要求确认；失败保留旧会话。
- [ ] 关闭清理当前会话，过期带标记会话可回收。
- [ ] 禁用仓库游戏和文本定位器后真实样本仍可生成。
- [ ] `.s/.x` 尾区来自用户输入，缺失或异常时导出阻断。

## 人工与法律门禁

- [ ] 在合法游戏副本验证 `.m/.dor/.stg/stage.ini/.s/.x/History.txt`。
- [ ] 检查地图、资源、小地图、头像、势力、据点、城门、武将和士兵。
- [ ] 确认 `SAN_RGB_PALETTE` 随 EXE 发布的权利边界。
- [ ] 确认许可证、仓库可见性、Release 文案、校验和与安全提醒。

任一资源审计、游戏兼容性或法律门禁未完成时，不上传正式 Release 附件。
