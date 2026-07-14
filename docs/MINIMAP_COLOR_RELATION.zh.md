# minimap_color 自动派生与手工修正

## 目标与边界

地图编辑器默认根据 `acwx/acwy/acwz` 自动维护 `minimap_color`，使普通地图编辑不必同步考虑颜色。由于 xyz 与颜色不是无损一一映射，`minimap_color` 同时保留在 Raw 字段中，允许编辑人员输入 `0..255` 的调色板索引进行最终修正。

本报告于 2026-07-14 对 `data/game` 内 33 个 `stage*.m` 进行全量统计，共分析 1,222,256 个 Cell、140 种颜色。字段严格按 `m.ksy` 读取：`acwx/acwy/acwz` 位于 Cell 的 `+0x00/+0x02/+0x04`，`minimap_color` 位于 `+0x0D`。

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

典型冲突是 `(acwx=2254, acwy=-1, acwz=-1)`：9,840 个 Cell 中颜色 243 有 8,683 个，但还存在 244、246、245、190 等颜色。自动函数是统计预测，不应阻止人工修正。

## 派生函数

编辑器加载 `.m` 后，以该地图的原始 Cell 构建计数表。函数签名为：

```text
derive_minimap_color(acwx, acwy, acwz) -> 0..255
```

字段优先级为 `acwz > acwy > acwx`。全部非空字段组合按该优先级的二进制降序排列，依次查找颜色计数并取众数：

1. `xyz`：`(acwx, acwy, acwz)`。
2. `yz`：`(acwy, acwz)`。
3. `xz`：`(acwx, acwz)`。
4. `z`：`acwz`。
5. `xy`：`(acwx, acwy)`。
6. `y`：`acwy`。
7. `x`：`acwx`。
8. 当前地图全局颜色。

同频时固定选择较小的颜色索引，使结果稳定可复现。模型保留 `level/confidence/support` 供测试和诊断，普通编辑流程只消费最终颜色。

按关卡留一验证会完全排除目标关卡并使用其余 32 个关卡训练。新顺序的完全相同 xyz 覆盖率为 88.195%，最终准确率为 94.564%；上一版 `xyz→xy→xz→x→全局` 的准确率为 83.618%。

## 编辑规则

1. xyz 真实变化且当前批次没有显式颜色时，自动追加一次颜色修改。
2. 同一 Cell 的一次批量操作同时包含 xyz 与 `minimap_color` 时，显式颜色优先，跳过自动预测。
3. Raw 面板允许直接修改和一键恢复 `minimap_color`；颜色变化后立即重建小地图。
4. 自动值和手工值都进入普通 Patch，并随对应操作撤销、重做和导出。
5. 全复制保存 `minimap_color`，粘贴时保留源 Cell 的手工修正；非底层复制继续排除颜色。
6. 剪切不把颜色直接清零，而是根据剪切后的最终 xyz 自动派生。
7. 导入不会重算全图；恢复当前 Cell 和恢复全部使用导入时原始颜色。

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
