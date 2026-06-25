# Task Plan: 三国霸业地图编辑器逆向

## 目标

解析《三国霸业》的地图与关卡数据格式，完成：

1. 地图真实渲染
2. 地图编辑器原型
3. `stage.ini` 与 Excel 的可回写链路
4. 继续补齐 `.stg/.evt/.s/.x` 的语义与写回能力

## 当前阶段

Phase 7：sidecar 深化逆向与小地图写回准备

## 阶段状态

### Phase 1：资源盘点与地图主表识别
- [x] 识别 `stageNN.*`、`kingdom.cel/.atr`、DAT 容器、`Emperor.exe`
- [x] 确认 `.m` 为固定 16 字节 cell 记录表
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
- [x] 方向键移动选中 cell
- [x] `Ctrl+Z`、`Reset cell`、`Reset all`
- [x] 导出 JSON patch
- [x] 安全写回复制后的 `.m`

### Phase 4：`stage.ini` 结构化导出与回写
- [x] 导出 `stage.ini` JSON
- [x] 回写字节级一致的 `stage.ini`
- [x] 导出分析版 Excel
- [x] 导出纯转换版 Excel
- [x] 从纯转换版 Excel 回写字节级一致的 `stage.ini`

### Phase 5：`uft8-game-txt` 与 `stage.ini` 映射
- [x] 建立 `general/castle/magic/soldier/history` 链接关系
- [x] 确认 `general/castle/magic/soldier` 的稳定 dword 步长
- [x] 区分分析版与转换版工作簿
- [x] 补上 trailer row 分类

### Phase 6：文档收口与流程固化
- [x] 重写 `README.md`，移除乱码与失效说明
- [x] 重写 `docs/FORMAT_NOTES.zh.md`，保留有效结论并单列 `stage.ini`
- [x] 建立明确的文档维护约定
- [x] 同步更新 `task_plan.md` / `findings.md` / `progress.md`

### Phase 7：下一步逆向重点
- [x] 确认 `stage01.stg city_92_family.n12 -> city_id`，并可通过 `castle.txt / stage.ini` 反查坐标
- [x] 确认 `stage01.stg city_92_family.n16 -> city_size`
- [x] 导出 `.stg` 原始记录链，确认不能跳过无文本记录
- [x] 按顺序恢复 `stage01.stg` 的势力/城池/武将/士兵层级
- [x] 导出 `.stg` 城池状态与士兵记录候选表
- [x] 确认城池块内人口、金、粮、开发、商业、治安、上限、坐标、太守候选字段
- [x] 确认 `.stg` 字节级回写规则，并完成 Excel round-trip 脚本
- [ ] 命名士兵记录中的数量、等级、兵种 id 字段
- [ ] 确认 `.evt` 的对象/坐标/目标引用方式
- [ ] 继续从 `Emperor.exe` 确认 `.s/.x` 的真实生成与读取路径

## 最高优先级问题

1. `.stg` 城池状态字段能否安全写回，以及是否需要同步其他续记录
2. 士兵记录中的数量、等级、兵种 id 字段如何命名
3. `.evt` 怎样引用地图对象与全局 id
4. `.s/.x` 是否必须与 `.m` 联动回写
5. `.m.byte08/09/10/11` 的最终语义
6. `acwz` 的完整 footprint / z-order

## 当前决策

| 决策 | 原因 |
| --- | --- |
| 地图编辑仍以 `.m` 16 字节完整记录为主 | 未解字段不能丢，否则无法安全回写 |
| `stage.ini` 通过 `raw_hex` 保底回写 | 可最大限度保留未知字节 |
| Phase 7 以 `.stg` 原始顺序层级作为 owner 主线 | `stage01` 已验证势力/城池/武将/士兵块结构，旧 `slot` 线索已降级 |
| 文档必须与代码同轮更新 | 当前项目已经证明，不写文档会快速积累错误与乱码 |

## 最近完成的里程碑

- `.stg` 已支持 Excel 字节级互转：`stage01.stg -> stage01_stg.xlsx -> stage01.stg` 在未修改时 sha256 完全一致，且 `city_state` 字段烟测可产生有限字节变化。

- 地图渲染已与 `stage11.png` 基本对齐
- 编辑器已支持本地 `.m` 编辑与 patch 写回复制件
- `stage.ini` 已支持 Python 版 Excel 导出、导入与字节级回写
- 文档体系已统一清理为 UTF-8 中文基线，并新增强制维护约定
- `stage01.stg` 已导出原始记录链与层级表，确认可恢复势力/城池/武将/士兵结构

## 下一步建议执行顺序

1. 先继续拆 `troop_candidates.csv` 中的士兵数量、等级、兵种 id 字段
2. 基于 `.stg` Excel 互转继续命名士兵数量、等级、兵种 id 字段
3. 然后做 `.evt` 的坐标/对象引用定位
4. 最后补 `.s/.x` 的缓存/小地图写回链路
