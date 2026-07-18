# 文档索引与维护表

更新日期：2026-07-18

本文档是项目文档的统一目录，说明每份文档负责什么、当前状态以及何时需要更新。可复用的临时脚本和短期任务记录放在已忽略的 `.planning/`；完成阶段的关键结论与验证结果归档到项目历史。

## 建议阅读顺序

1. 编辑人员首次使用发布包：`docs/EDITOR_USER_GUIDE.zh.md`；开发者首次使用：`README.md`、`data/README.zh.md`。
2. 参与开发：`AGENTS.md`、`CONTRIBUTING.zh.md`、本文档。
3. 执行脚本：命令执行参考。
4. 修改编辑器：编辑器设计、数据管理、字段转换。
5. 修改二进制格式：KSY 文件、格式笔记、字段转换。
6. 发布前：无资源打包链路、已知问题、GitHub Release 清单、版权说明和实施验收基线。

## 技术文档

| 文档 | 主要内容 | 状态 | 需要更新的情况 |
| --- | --- | --- | --- |
| `docs/DOCUMENT_INDEX.zh.md` | 全部文档的职责、状态和维护入口 | 持续维护 | 新增、删除、合并或改名任何文档时 |
| `docs/COMMAND_REFERENCE.zh.md` | 统一命令入口、全部命令参数、示例、产物与风险 | 当前有效 | 注册命令、参数、默认路径或输出行为变化时 |
| `docs/EDITOR_USER_GUIDE.zh.md` | 随发布 ZIP 交付给编辑人员的启动、布局、逐步操作、快捷键、导出和排错指南 | 当前有效 | 用户界面、操作方式、快捷键或导出流程变化时 |
| `docs/EDITOR_PACKAGING_CHAIN.zh.md` | 无资源 Windows 构建、五文件产物、用户运行时临时 Bundle、审计和发布门禁 | 当前有效 | 构建入口、运行时依赖、白名单、会话或发布目录变化时 |
| `docs/EDITOR_CONTENT_PACK.zh.md` | 独立内容包格式、生成、审计、启动缓存和组合分发 | 当前有效 | 内容 Schema、缓存、审计或组合方式变化时 |
| `docs/EDITOR_RESOURCE_FREE_RELEASE_PLAN.zh.md` | 无资源发布的目标、架构、改动清单、测试、验收标准和最终实施状态 | 已实施验收基线 | 无资源发布边界、运行时导入架构或验收状态变化时 |
| `docs/EDITOR_UI_V2_DESIGN.zh.md` | 编辑器布局、工作流、管理界面和运行时架构 | 当前有效 | UI 结构、主要工作流或功能边界变化时 |
| `docs/EDITOR_DATA_MANAGEMENT.zh.md` | 输入源、临时会话、用户导出边界，以及字段关系与跨文件同步规则 | 当前有效 | CRUD、会话、Patch 或导入导出行为变化时 |
| `docs/EDITOR_FIELD_CONVERSION.zh.md` | `.m/.dor/.stg/stage.ini/History.txt` 字段级转换与写回 | 当前有效 | 字段偏移、类型、转换或写回规则变化时 |
| `docs/FORMAT_NOTES.zh.md` | 二进制文件结构、证据级别、已确认结论与未解问题 | 当前有效 | KSY、样本统计或格式结论变化时 |
| `docs/MINIMAP_COLOR_RELATION.zh.md` | `minimap_color` 与 xyz 的统计关系和预测边界 | 研究结论 | 样本集、算法或自动填色策略变化时 |
| `docs/KNOWN_ISSUES.zh.md` | 暂时搁置的问题、风险和验证边界 | 持续维护 | 问题出现、状态变化或解决时 |
| `docs/GITHUB_RELEASE_CHECKLIST.zh.md` | GitHub 推送、五文件发布审计、运行时验收和人工法律门禁 | 发布前有效 | GitHub 上传、许可证、资源审计或发布方式变化时 |
| `docs/PROJECT_HISTORY.zh.md` | 关键技术和产品里程碑摘要 | 只追加重要节点 | 完成会影响项目方向或能力边界的阶段时 |

## 项目入口与治理文档

| 文档 | 主要内容 | 状态 | 需要更新的情况 |
| --- | --- | --- | --- |
| `README.md` | 项目简介、当前能力、安装、数据准备、启动和测试 | 持续维护 | 用户可见能力、命令或目录变化时 |
| `data/README.zh.md` | 本地游戏数据清单、目录结构和环境变量 | 持续维护 | 必需资源或路径规则变化时 |
| `AGENTS.md` | 仓库内自动化开发和文档维护约束 | 规范 | 项目协作规则变化时 |
| `CONTRIBUTING.zh.md` | 开发环境、贡献要求和提交前验证 | 规范 | 开发流程、测试或贡献方式变化时 |
| `CHANGELOG.md` | 面向版本和用户的功能变更摘要 | 持续维护 | 产生用户可见行为变化时 |
| `CODE_OF_CONDUCT.zh.md` | 社区参与和讨论行为准则 | 规范 | 社区治理方式变化时 |
| `SECURITY.md` | 安全问题报告和二进制输出风险 | 规范 | 安全支持范围或报告渠道变化时 |
| `NOTICE.zh.md` | 与原游戏权利方的关系、无资源发布包、用户临时会话和调色板边界 | 规范 | 素材分发、临时会话或权利边界变化时 |
| `LICENSE` | 源码与文档许可条款 | 法律文件 | 只能由版权所有者确认后修改 |

## GitHub 配套文件

| 文件 | 主要内容 |
| --- | --- |
| `.github/workflows/ci.yml` | Python 3.11、3.12、3.13 自动测试 |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | 错误报告模板和敏感数据提醒 |
| `.github/pull_request_template.md` | PR 修改说明与验证清单 |
| `.github/dependabot.yml` | Python 和 GitHub Actions 依赖更新 |

## 事实来源优先级

当文档之间出现冲突时，按以下顺序处理：

1. `.m/.dor/.stg` 的字段、类型和解析顺序以 `src/san_tools/ksy/` 为最高规范。
2. 可执行行为以当前源码和通过的自动化测试为准。
3. 字段转换与关联管理分别以 `EDITOR_FIELD_CONVERSION.zh.md`、`EDITOR_DATA_MANAGEMENT.zh.md` 为准。
4. 研究推断必须在 `FORMAT_NOTES.zh.md` 标明证据级别，不得覆盖已确认的 KSY 事实。
5. 历史文档只记录当时完成的里程碑，不作为当前实现规范。

## 维护流程

1. 修改前确定唯一负责该信息的文档，避免在多处复制相同段落。
2. 格式事实变化时，先更新 KSY 和测试，再同步字段转换与格式笔记。
3. 用户可见行为变化时，同步更新 README、数据管理和 CHANGELOG。
4. 新增或删除文档时，必须同步更新本文档。
5. 提交前检查命令、相对链接、路径、章节顺序、乱码和失效状态。

## 已合并或移除的文档

| 原文件 | 处理方式 | 信息去向 |
| --- | --- | --- |
| `docs/DOC_WORKFLOW.zh.md` | 合并后删除 | 维护规则并入本文档 |
| `docs/EDITOR_CURRENT_GOAL.zh.md` | 合并后删除 | 命令语义进入数据管理，完成状态进入项目历史 |
| 根目录 `task_plan.md`、`findings.md`、`progress.md` | 整理后删除 | 关键结论、实现阶段和验证结果并入 `docs/PROJECT_HISTORY.zh.md` |
