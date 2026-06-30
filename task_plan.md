# Task Plan: 三国霸业地图编辑器

## 目标

解析《三国霸业》的地图与关卡数据格式，完成：

1. 真实地图渲染
2. 地图编辑器原型
3. `stage.ini` 与 `.stg` 的可回写链路
4. 继续补齐 `.evt/.spr/.dor/.s/.x` 的语义与写回能力

## 当前阶段

Phase 7：sidecar 深化逆向与小地图写回准备

## 已完成

### Phase 1：资源盘点与地图主表识别
- [x] 识别 `stageNN.*`、`kingdom.cel/.atr`、DAT 容器、`Emperor.exe`
- [x] 确认 `.m` 为固定 16 字节 cell 记录
- [x] 建立初版格式笔记

### Phase 2：地图渲染恢复
- [x] 从 `kingdom.cel/.atr` 恢复 `acwx/acwy/acwz`
- [x] 从 `Emperor.exe` 确认 stagger world-to-screen 变换
- [x] 生成与真实游戏画面接近的地图渲染图

### Phase 3：编辑器原型
- [x] 浏览地图
- [x] Inspect / Paint
- [x] 本地 `.m` 加载
- [x] 右键拖动视角
- [x] 方向键移动当前 cell
- [x] `Ctrl+Z`、`Reset cell`、`Reset all`
- [x] 导出 JSON patch
- [x] 安全写回复制后的 `.m`

### Phase 4：`stage.ini` 结构化导出与回写
- [x] 导出 `stage.ini` JSON
- [x] 回写字节级一致的 `stage.ini`
- [x] 建立 `stage.ini` Excel 工作簿导出与回写链路
- [x] 用 `uft8-game-txt/` 对照稳定文本映射

### Phase 5：`.stg` 工作簿与城池状态回写
- [x] 导出 `.stg` 原始记录链与层级表
- [x] 导出 `.stg` Excel 工作簿
- [x] 回写未修改工作簿并保持字节一致
- [x] 回写 `city_state` 中已确认的字段
- [x] 为 `.stg` 工作簿回写建立自动化测试

### Phase 6：文档与工程化收口
- [x] 清理核心文档的编码污染
- [x] 回滚 `b4a9f70` 在文档里提前写死的新增说明
- [x] 为项目增加 `pyproject.toml`
- [x] 将主源码迁入 `src/san_tools/`
- [x] 将自动化测试迁入独立 `tests/` 目录
- [x] 提供 `python -m tools` / `san-tools` 统一入口
- [x] 保留 `tools/*.py` 兼容包装层
- [x] 修复关键 Python 脚本与测试文件中的中文编码问题

## 当前待办

### Phase 7：sidecar 深化逆向
- [ ] 继续逆向 `.evt` 的记录类型、文本参数和坐标引用
- [ ] 继续逆向 `.spr/.dor` 的实体含义
- [ ] 从 `Emperor.exe` 继续确认 `.s/.x` 的真实生成与读取路径
- [ ] 设计 `.m` 修改如何联动 `.s/.x` 小地图缓存
- [ ] 继续拆 `.stg` 士兵块和附属记录中的未命名字段

### Phase 8：编辑器联动增强
- [ ] 让编辑器支持 `.stg` / `.s/.x` 的联动查看与校验
- [ ] 为地图对象层增加更细的可视化检查工具
- [ ] 把当前 patch 工作流整理成更稳定的“加载 - 编辑 - 校验 - 写回”闭环

## 低优先级待办

- [ ] 增加 `Tiled/TMX` 交换格式，作为外部工具互操作层
- [ ] 评估是否需要桌面版编辑器壳，而不是只保留浏览器版本

## 约束

- `.m` 编辑必须保留完整 16 字节 cell 记录。
- `.stg` 写回必须以 `raw_records.raw_hex` 为保底数据源。
- 未确认字段不允许被脚本重算或清零。
- 文档必须与代码同步更新，不能把过期结论继续留在仓库里。