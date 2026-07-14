# minimap_color 与 xyz 自动派生

## 目标与边界

地图编辑器把 `minimap_color` 作为 `.m` 的存储字段保留，但编辑人员不再直接维护它。仅当某个 Cell 的 `acwx/acwy/acwz` 最终值真实变化时，编辑器自动计算颜色，并把颜色修改与 xyz 修改放进同一个撤销/重做事务。导入时不会重算全图；“恢复当前 Cell”和“恢复全部”会精确恢复原始颜色。

`minimap_color` 不是 xyz 的无损确定函数。本报告于 2026-07-14 对 `data/game` 内 33 个 `stage*.m` 进行全量统计，共分析 1,222,256 个 Cell、140 种颜色。字段严格按 `m.ksy` 读取：`acwx/acwy/acwz` 位于 Cell 的 `+0x00/+0x02/+0x04`，`minimap_color` 位于 `+0x0D`。

## 统计结果

| 输入字段 | 唯一键数 | 冲突键数 | 确定键占比 | 确定记录占比 | 样本内众数命中率 |
|---|---:|---:|---:|---:|---:|
| `acwx` | 1,003 | 907 | 9.571% | 0.068% | 66.714% |
| `acwy` | 1,968 | 1,354 | 31.199% | 1.179% | 35.055% |
| `acwz` | 597 | 220 | 63.149% | 1.163% | 17.761% |
| `acwx+acwy` | 105,687 | 10,165 | 90.382% | 18.306% | 89.309% |
| `acwx+acwz` | 28,497 | 2,318 | 91.866% | 5.056% | 72.680% |
| `acwy+acwz` | 10,163 | 1,332 | 86.894% | 4.977% | 41.147% |
| `acwx+acwy+acwz` | 138,589 | 6,265 | 95.479% | 26.765% | 95.091% |

典型冲突是 `(acwx=2254, acwy=-1, acwz=-1)`：9,840 个 Cell 中颜色 243 有 8,683 个，但还存在 244、246、245、190 等颜色。因此函数必须明确采用统计规则，不能声称能还原游戏原始颜色。

## 派生函数

编辑器加载 `.m` 后，以该地图的原始 Cell 构建计数表。函数签名为：

```text
derive_minimap_color(acwx, acwy, acwz) -> 0..255
```

按以下顺序查找颜色计数并取众数：

1. 完整 `(acwx, acwy, acwz)`。
2. `(acwx, acwy)`。
3. `(acwx, acwz)`。
4. `acwx`。
5. 当前地图全局颜色。

同频时固定选择较小的颜色索引，使函数结果稳定可复现。`xy` 先于 `xz`，因为全量样本中的众数拟合率分别为 89.309% 和 72.680%。模型同时保留 `level/confidence/support`，便于诊断，但普通编辑流程只消费最终颜色。

按关卡留一验证会完全排除目标关卡并使用其余 32 个关卡训练。加入 `xz` 回退后的结果是：完全相同 xyz 覆盖率 88.195%，最终准确率 83.618%。编辑器使用当前地图训练，常见资源组合通常能命中完整 xyz；新组合则按上述层级回退。

## 编辑规则

1. `minimap_color` 不进入 Raw 可编辑字段、数据层色板或复制快照。
2. 笔刷、Raw xyz 修改、区域粘贴和剪切先合并同一 Cell 的 xyz，随后只对最终值预测一次。
3. 旧 Patch 或快照中的显式 `minimap_color` 修改会被忽略，避免旧颜色覆盖派生结果。
4. 自动颜色与 xyz 一起撤销和重做；小地图在颜色变化后立即重建。
5. 全量恢复和单 Cell 恢复使用导入时原始值，不经过统计函数，保证恢复结果逐字段一致。

## 可复用实现

Python 分析函数位于 `src/san_tools/analysis/analyze_minimap_color_relation.py`：

```python
from san_tools.analysis.analyze_minimap_color_relation import (
    MinimapColorPredictor,
    build_minimap_color_function,
    iter_m_color_rows,
)

rows = list(iter_m_color_rows(stage_path))
predict_color = build_minimap_color_function(rows)
color = predict_color(acwx, acwy, acwz)

detail = MinimapColorPredictor(rows).predict_detail(acwx, acwy, acwz)
print(detail.color, detail.confidence, detail.support, detail.level)
```

重新生成全量报告：

```powershell
python -m san_tools run analyze-minimap-color-relation .
```
