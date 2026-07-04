# 进度日志

## 2026-06-23 至 2026-07-02 阶段总结

- 完成 `.m` 主记录、资源渲染、地图浏览与基础编辑闭环。
- 完成 `stage.ini`、`.stg`、`.dor`、`.s/.x` 的多轮逆向与写回能力补齐。
- 统一 `.dor` 分析入口，清理旧的猜测型脚本。
- 为编辑器接入据点与城门归属联动，支持地图高亮与 bundle 导出 `siteLinks`。

## 2026-07-03

- 阅读新版编辑器示意图与 `deep-research-report.md`，确认重构方向应从“底层字段分栏”转向“任务导向布局”。
- 盘点现有前端与导出数据，确认 `stage.json` / `resources.json` 已具备支撑 UI 2.0 的数据基础。
- 启动 UI 2.0 工作，拆分为两个提交：
  1. 设计文档、计划同步与结论落盘
  2. `editor_app.html` 的全新布局与交互重构
- 完成 `docs/EDITOR_UI_V2_DESIGN.zh.md`、`task_plan.md`、`findings.md`、`progress.md` 的 UTF-8 中文同步。

## 2026-07-04

- 根据新增要求，补齐新版编辑器的数据架构定义，把设计重点从“任务导向布局”进一步推进到“剧本 / 资源双主线领域模型”。
- 更新 `docs/EDITOR_UI_V2_DESIGN.zh.md`，明确剧本树、资源树、运行时领域层、视图派生层与预留扩展位。
- 同步更新 `task_plan.md` 与 `findings.md`，确保计划、结论、实现目标使用同一套中文术语。
- 已将领域模型摘要映射到新 UI 左侧总览与右侧 Inspector，使页面能直接反映数据骨架而不是只展示布局。
- 完成 `editor_app.js` 运行时领域模型接线，并通过 `node --check` 与 `export_editor_bundle.py --stage stage11` 冒烟验证。

## 2026-07-05

- 盘点 `src/san_tools/` 下的正式入口，确认编辑器主 bundle、`.stg` 工作簿、`.dor` 归属表、`.s/.x` sidecar、`stage.ini` 文本映射都已有稳定脚本链路。
- 在 `docs/EDITOR_UI_V2_DESIGN.zh.md` 新增“数据结构与游戏文件一一对应表”与“仓库级转换脚本总表”，把数据结构、游戏文件、转换脚本、回写脚本放进同一套表格。
- 同步更新 `task_plan.md` 与 `findings.md`，把这次补齐的映射关系纳入长期维护基线，后续新增结构时可直接按表扩展。
