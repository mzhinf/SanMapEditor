# GitHub 上传前整理清单

审计日期：2026-07-13

审计分支：`master`

审计基准：`56a5a22`

## 1. 当前结论

当前仓库**不适合直接推送到 GitHub**。源码检出树本身较小，但 Git 历史、工作区状态、测试独立性、打包配置和版权边界仍有阻断项。

发布前至少必须完成：

- [ ] 清理或重建包含大文件的 Git 历史。
- [ ] 处理全部未提交和未跟踪文件，使工作区干净。
- [ ] 排除原始游戏文件、派生图集和本地发布包。
- [ ] 修复 5 个完整测试错误。
- [ ] 移除源码和测试中的本机绝对路径。
- [ ] 补齐 Python 包中的 HTML 与 KSY 数据文件。
- [ ] 选择并添加开源许可证，明确游戏资产版权边界。

## 2. P0：上传阻断项

### 2.1 Git 历史体积

当前检出树只跟踪 133 个文件，最大跟踪文件约 0.229 MiB；但 `.git` 中 pack 总计约 5.61 GiB。

历史中存在：

- 31 个超过 100 MiB 的 blob。
- 37 个超过 50 MiB 的 blob。
- 最大 blob 约 979.58 MiB。
- 大对象主要来自 `derived-old/`，另有 `dist/`、`.tmp/`、`outputs/` 和 `sgby-output/` 历史产物。

GitHub 普通 Git 推送会拒绝超过 100 MiB 的单文件。修改 `.gitignore` 只能阻止未来误提交，不能清理历史。

处理方案二选一：

1. **推荐：重写现有历史**。先创建完整备份，再使用 `git filter-repo` 从全部提交中移除 `derived-old/`、`derived/`、`dist/`、`.tmp/`、`outputs/`、`sgby-output/`、`other/` 和 `三国霸业/`。
2. **最稳妥：建立干净的新历史**。在新仓库或 orphan 分支中只提交审核后的源码、测试和文档。旧仓库保留为本地研究档案。

当前没有 remote 和 tag，适合在首次公开上传前完成此操作。历史清理属于不可逆操作，必须先备份，不能直接在唯一副本上执行。

### 2.2 工作区不干净

当前已跟踪未提交内容：

- `.gitignore`：新增 `other/` 合理，但新增 `/tools/` 会屏蔽正式兼容入口下的新脚本，应移除。
- `derived/dor_relationship/stage01/*.json`：3 个已跟踪分析产物处于删除状态；若确认不再维护，应提交删除并从历史清理。
- `docs/FORMAT_NOTES.zh.md`、`findings.md`、`progress.md`：STG 深度修订内容尚未提交。
- `tests/test_minimap_sidecar_builder.py`：新增了硬编码本机路径且没有断言的测试，当前会报错，不能原样提交。

当前需要人工决定的未跟踪源码：

- `src/san_tools/analysis/analyze_stg.py`：仍描述旧固定记录布局，与当前 `stg.ksy` 对象流模型冲突，应重写或移除。
- `src/san_tools/codecs/stg_codec_direct.py`：独立 STG 解析实现，需证明与 KSY 字段和顺序一致后再整合。
- `src/san_tools/codecs/stg_stream_codec_refactored.py`：独立 STG 流解析实现，尚未纳入正式入口，部分注释和文档字符串为英文。
- `tests/test_assets.py`：依赖本机绝对路径，以打印代替断言，应改成手工研究脚本或有效集成测试。
- `uv.lock`：若项目采用 uv，应提交；否则应明确忽略，不要长期悬空。

明确不应提交：

- `.planning/`
- `.tmp/`
- `dist/`
- `outputs/`
- `sgby-output/`
- `src/san_map_tools.egg-info/`
- `src/san_tools/map/_editor_app_check.js`
- `.idea/`、`.uv-cache/`、`.venv/`

### 2.3 原始游戏与版权资产

源码仓库不得包含：

- `三国霸业/` 原始游戏目录。
- `Emperor.exe`、`heads.dat`、`stage.ini`、关卡 `.m/.dor/.stg/.s/.x`。
- 由 `kingdom.cel/.atr` 或头像文件生成的大图、图集和预览图。
- 包含上述内容的 ZIP、工作簿或检查数据。

当前 Windows 发布包包含 `heads.dat`、`stage.ini`、`stage01.dor`、`stage01.stg` 以及由游戏资源生成的图集。它不应进入源码提交；是否上传到 GitHub Release，必须先确认拥有分发这些资产的权利。

README 应增加免责声明：项目与原游戏权利方无关联；仓库不提供游戏资产；用户必须自行准备合法游戏副本。

### 2.4 完整测试失败

审计命令：

```powershell
python -m unittest discover -s tests -v
```

结果：运行 70 项，5 项报错。

- `test_build_new_x_s`：硬编码的 `H:/Workstation/san/三国霸业/SGBY_MAP/new-stage01.m` 不存在。
- `test_stage01_site_links_cover_all_doors`：缺少未入库的 `uft8-game-txt/castle.txt`。
- `test_stage01_block_view_is_more_stable_than_single_record_view`：同上。
- `test_stage01_troop_rows_export_named_soldier_id_cluster`：同上。
- `StgWorkbookRoundTripTest.setUpClass`：同上。

建议把测试拆成：

- `unit`：完全使用仓库内小型人工夹具，任何机器和 CI 都必须通过。
- `integration`：需要用户自备游戏素材，通过环境变量指定目录；素材缺失时明确跳过。
- `manual/research`：仅输出分析结果的脚本，不放在自动化测试目录。

### 2.5 本机绝对路径

已跟踪文件至少包含以下不可移植路径：

- `src/san_tools/analysis/analyze_stg_field_values.py`
- `tests/test_minimap_sidecar_builder.py`
- `tests/test_stg_field_values.py`
- `tests/test_stg_json_roundtrip.py`
- `tools/export_stage_ini_workbook.mjs`
- `tools/export_stage_sidecar_workbook.mjs`

两个 `.mjs` 文件还硬编码 `C:/Users/mzhinf/.cache/codex-runtimes/...`，其他机器无法运行。

统一改造原则：

- 命令输入使用参数或环境变量，例如 `SAN_GAME_DIR`。
- 测试使用 `tempfile` 和仓库内夹具。
- Node 依赖写入 `package.json`，通过标准包解析加载，不引用个人缓存目录。

### 2.6 Python 包缺少数据文件

`pyproject.toml` 当前只配置 Python 包发现，没有声明 package data。现有 `SOURCES.txt` 不包含：

- `src/san_tools/map/editor_app.html`
- `src/san_tools/ksy/m.ksy`
- `src/san_tools/ksy/dor.ksy`
- `src/san_tools/ksy/stg.ksy`

从 wheel 或 sdist 安装后，编辑器模板和格式定义可能缺失。应增加：

```toml
[tool.setuptools.package-data]
san_tools = ["map/editor_app.html", "ksy/*.ksy"]
```

随后构建 wheel，并检查压缩包内确实包含这些文件。

## 3. P1：仓库规范化

### 3.1 `.gitignore`

建议至少覆盖：

```gitignore
# 原始游戏和本地研究素材
三国霸业/
other/

# 生成物与发布物
derived/
dist/
outputs/
sgby-output/
build/
*.egg-info/

# 临时文件与工具状态
.tmp/
.planning/
.uv-cache/
.idea/
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
```

不要忽略 `/tools/`，因为其中有 40 个已跟踪兼容入口。若采用 uv，也不要忽略 `uv.lock`。

### 3.2 行尾与编辑器配置

当前 Git 全局配置为 `core.autocrlf=true`，已有 LF/CRLF 转换警告。建议增加：

- `.gitattributes`：统一文本行尾，显式标记二进制扩展名。
- `.editorconfig`：UTF-8、末尾换行、Python 4 空格、Markdown 行尾策略。

### 3.3 项目元数据

`pyproject.toml` 建议补充：

- `authors`
- `license`
- `keywords`
- `classifiers`
- `[project.urls]` 中的主页、源码、问题追踪地址
- 测试和集成测试 marker
- package data

当前版本为 `0.1.0`，首次公开发布前应确认版本号与发布说明一致。

### 3.4 Git 身份与默认分支

当前 103 个提交的作者均为 `Codex <codex@local>`。公开前需要决定：

- 保留现状；或
- 使用 `.mailmap` 映射展示身份；或
- 在历史重写时统一作者信息。

上传前设置真实的 Git 用户名和 GitHub 已验证邮箱。默认分支可从 `master` 改为 `main`，并在 GitHub 开启分支保护。

## 4. P1：README 与文档

### 4.1 README 必须补齐

- [ ] 项目状态和稳定性声明。
- [ ] 支持的平台与 Python 版本。
- [ ] 从克隆、创建虚拟环境、安装到运行的快速开始。
- [ ] 定义命令示例中的 `$py`，或直接改用 `python`。
- [ ] 用户自备游戏素材的目录模板，不链接到不会提交的 `三国霸业/`。
- [ ] 编辑器启动命令和 Windows 发布包构建命令。
- [ ] 一条可复现的完整单元测试命令。
- [ ] unit 与 integration 测试的区别。
- [ ] 许可证、免责声明和贡献入口。

### 4.2 失效或冲突文档

- `task_plan.md` 仍把 UI 2.0 编码标为未完成，与当前编辑器状态不一致，应更新或归档。
- `README.md` 的“下一步建议”仍以早期逆向阶段为主，应按当前完成度重写。
- `docs/FORMAT_NOTES.md` 是较旧英文文档，不符合项目“非代码统一中文”的规则；应合并有效内容到中文文档后移除。
- `docs/FORMAT_NOTES.zh.md` 的 `5.6` 小节位于第 8 章之后，章节顺序需要整理。
- 根目录 `findings.md`、`progress.md`、`task_plan.md` 可移动到 `docs/development/`，避免项目入口过于杂乱；移动后同步修正维护文档。
- `uft8-game-txt` 是历史拼写，若公开 API 尚未固定，可评估统一为 `utf8-game-txt`。

## 5. P2：GitHub 配套文件

在 P0 问题解决后补充：

- [ ] `LICENSE`
- [ ] `CONTRIBUTING.zh.md`
- [ ] `SECURITY.md`
- [ ] `CODE_OF_CONDUCT.zh.md`，若接受外部贡献
- [ ] `CHANGELOG.md`
- [ ] `AGENTS.md`，记录中文文档、脚本注释和提交要求
- [ ] `.github/workflows/ci.yml`
- [ ] Issue 模板和 Pull Request 模板
- [ ] Dependabot 或等价依赖更新配置

CI 建议先覆盖 Python 3.11、3.12 和 3.13。Python 3.14 可在依赖稳定后加入，不应只在开发者本机版本上验证。

## 6. 推荐整理后的目录

```text
.
├─ .github/
│  ├─ workflows/
│  └─ ISSUE_TEMPLATE/
├─ docs/
│  ├─ development/
│  └─ *.zh.md
├─ src/san_tools/
│  ├─ analysis/
│  ├─ cli/
│  ├─ codecs/
│  ├─ ksy/
│  ├─ map/
│  ├─ pipelines/
│  └─ text/
├─ tests/
│  ├─ fixtures/
│  ├─ integration/
│  └─ unit/
├─ tools/
├─ .editorconfig
├─ .gitattributes
├─ .gitignore
├─ AGENTS.md
├─ CHANGELOG.md
├─ CONTRIBUTING.zh.md
├─ LICENSE
├─ pyproject.toml
├─ README.md
└─ uv.lock
```

原始游戏、分析结果、输出文件和发布包均留在本地忽略目录，不出现在源码树中。

## 7. 推荐提交顺序

1. **STG 研究收口**：决定 3 个未跟踪 STG 模块的去留，修正或移除 `test_assets.py`，提交对应中文文档。
2. **测试可移植化**：移除绝对路径，拆分 unit/integration，确保无素材环境下单元测试全绿。
3. **仓库卫生**：修正 `.gitignore`，提交已跟踪生成物删除，添加行尾和编辑器配置。
4. **Python 打包**：补齐 package data 和项目元数据，验证 wheel/sdist。
5. **公开文档**：重写 README，整理旧文档，添加许可证、免责声明和贡献指南。
6. **CI**：添加 GitHub Actions，并确保干净克隆可通过。
7. **历史清理**：备份后重写历史或建立干净新历史，再次扫描大对象。
8. **首次推送**：创建 GitHub 仓库、添加 remote、推送默认分支，最后配置分支保护和 Release。

每个步骤单独提交，避免把功能变更、生成物清理和历史操作混在一个提交里。

## 8. 上传前最终验收

- [ ] `git status --short` 无输出。
- [ ] 当前 Git 历史不存在超过 100 MiB 的 blob，仓库总体积合理。
- [ ] `git ls-files` 不包含原始游戏文件、生成图、工作簿、ZIP、EXE 或本地缓存。
- [ ] 全仓库不包含 `H:/Workstation`、`C:/Users` 等本机路径。
- [ ] 常见 token、私钥和密码模式扫描无结果。
- [ ] 干净克隆后可按 README 完成安装。
- [ ] wheel/sdist 包含 `editor_app.html` 与全部 KSY 文件。
- [ ] unit 测试全部通过；integration 测试在无素材时明确跳过。
- [ ] README 中的命令、路径和链接全部有效。
- [ ] 已添加许可证与游戏资产免责声明。
- [ ] Windows 发布包未进入源码提交。
- [ ] GitHub Actions 首次运行成功。

只有以上项目全部满足后，仓库才达到适合公开上传的状态。
