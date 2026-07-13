# GitHub 上传前整理清单

审计日期：2026-07-13

审计分支：`master`

## 当前结论

仓库源码已经完成公开上传前的主要整理。游戏素材与生成物继续保留在本地忽略目录；首次推送前仍需配置 GitHub 远端，并由维护者确认仓库可见性和许可证策略。

## Git 历史复核

对 `master` 的 103 个提交逐个执行树对象扫描后确认：

- 大于 100 MiB 的唯一 blob：0 个。
- 大于 1 MiB 的唯一 blob：0 个。
- 不需要重建 Git 仓库，也不需要重写 `master` 历史。

本地 `.git` 约 5.61 GiB，主要来自 Codex 内部 `refs/codex/turn-diffs/*` 快照、reflog 和不可达对象。它们不属于 `master`，普通 `git push origin master` 不会上传这些对象。不要为了减小本地目录而删除 Codex 引用；如以后确需清理，应先备份并单独评估本地任务恢复影响。

## 已完成项

- [x] 复核 `master` 历史，不存在 GitHub 100 MiB 单文件阻断。
- [x] 删除未被应用引用的 `_editor_app_check.js`。
- [x] 确认旧 `tools` 目录仅剩 Python 转发层，命令已迁移到 `python -m san_tools`。
- [ ] 删除 38 个已跟踪的旧 `tools` 转发文件；安全审查要求维护者再次明确批准。
- [x] 统一本地资源入口为 `data/game`、`data/text` 和两个环境变量。
- [x] 移除源码、测试中的本机盘符路径与个人缓存路径。
- [x] 删除只有打印输出且依赖绝对路径的 `tests/test_assets.py`。
- [x] 在无游戏素材时跳过集成测试，保留 CI 可复现性。
- [x] 声明 `editor_app.html` 与 `ksy/*.ksy` 为 Python package data。
- [x] 增加 README、贡献指南、安全策略、变更记录、维护约定、CI 和模板。
- [x] 增加游戏素材免责声明和保守许可证。

## 问题说明

### wheel 中缺少 HTML 与 KSY 的原因

源码开发和 editable install 会直接从 `src/` 读取 `editor_app.html`，因此本机运行正常；但 setuptools 默认只收集 Python 模块，不会自动把 HTML 和 KSY 放入 wheel/sdist。安装正式构建包后，`Path(__file__).with_name("editor_app.html")` 会找不到模板，KSY 规范文件也不会随包分发。

现已在 `pyproject.toml` 中增加 package data，并通过构建产物内容测试验证。

### 并行 STG 实现为什么有风险

仓库同时存在 KSY 字段模型、块流 roundtrip 编解码器和早期固定记录分析视图。它们形成于不同研究阶段，如果都被视为正式规范，新增字段或写回逻辑可能出现对象边界、保留字段和记录顺序冲突。

当前处理是明确职责：编辑器正式模型只以 KSY 和 `editor_model.py` 为准；其他实现仅保留为研究或兼容工具。全面合并需要重新逐字段、逐样本验证，按要求暂时搁置，详见 [已知问题](KNOWN_ISSUES.zh.md)。

## 已知搁置项

- Windows 发布包可能包含原始游戏素材或派生图集，再分发权尚未核验，暂不上传 Release。
- STG 研究实现的统一命名、抽象合并和历史代码移除暂时搁置。
- `.s/.x` 小地图生成规则仍采用保守兼容方案，需要更多游戏内样本验证。

## 首次推送前操作

- [ ] 设置 Git 用户名和 GitHub 已验证邮箱。
- [ ] 创建 GitHub 仓库并添加 `origin`。
- [ ] 决定是否把默认分支从 `master` 改为 `main`。
- [ ] 确认当前“保留所有权利”许可符合发布目的；开源时替换为明确的开源许可证。
- [ ] 执行完整测试和 wheel 内容验证。
- [ ] 检查 `git status --short`，确保仅包含预期源码与文档。
- [ ] 扫描令牌、私钥、本机路径和误提交的大文件。
- [ ] 推送后确认 GitHub Actions 在 Python 3.11、3.12、3.13 上通过。

## 不得提交的内容

- `data/game/*`、`data/text/*` 中的实际素材。
- 原始游戏目录、EXE、地图、头像、文本和派生图集。
- `derived/`、`dist/`、`outputs/`、`.tmp/`、`.planning/`。
- 工作簿、ZIP、发布 EXE、缓存和 IDE 状态。
