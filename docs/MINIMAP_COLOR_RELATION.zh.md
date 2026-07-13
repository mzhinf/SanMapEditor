# minimap_color 与 xyz 关系分析

## 样本与方法

本报告于 2026-07-13 对游戏目录内 33 个 `stage*.m` 进行全量统计，共分析 1,222,256 个 Cell、140 种 `minimap_color`。字段严格按 `m.ksy` 读取：`acwx/acwy/acwz` 位于 Cell 的 `+0x00/+0x02/+0x04`，`minimap_color` 位于 `+0x0D`。

对每一种输入组合建立 `color -> 次数` 计数，并以众数作为预测值。除样本内拟合外，另做按关卡留一验证：每次完全排除一个关卡，用其余 32 个关卡训练，再预测被排除关卡。

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

`xyz` 的唯一键中有 95.479% 只观察到一种颜色，但这些多数是低频组合。按 Cell 数量计算，只有 26.765% 的记录处于完全确定的 `xyz` 组合中；大量高频地形组合对应多个颜色。

典型冲突是 `(acwx=2254, acwy=-1, acwz=-1)`：共 9,840 个 Cell，其中颜色 243 有 8,683 个，但还出现 244、246、245、190 等颜色。因此不存在无损的纯 `xyz -> minimap_color` 确定函数。

## 跨关卡验证

预测器采用以下回退顺序：

1. 完整 `(acwx, acwy, acwz)` 众数。
2. `(acwx, acwy)` 众数。
3. `acwx` 众数。
4. 全局颜色众数。

按关卡留一验证结果：

- 总记录数：1,222,256。
- 其他关卡存在完全相同 `xyz` 的覆盖率：88.195%。
- 最终预测准确率：83.471%。

该准确率足以生成编辑建议或新 Cell 的初始候选颜色，但约每六个 Cell 就可能有一个错误，不能在导出时静默覆盖原始 `minimap_color`。

## 可复用函数

实现位于 `src/san_tools/analysis/analyze_minimap_color_relation.py`：

```python
from san_tools.analysis.analyze_minimap_color_relation import (
    MinimapColorPredictor,
    build_minimap_color_function,
    iter_m_color_rows,
)

rows = list(iter_m_color_rows(stage_path))
predict_color = build_minimap_color_function(rows)
color = predict_color(acwx, acwy, acwz)

predictor = MinimapColorPredictor(rows)
detail = predictor.predict_detail(acwx, acwy, acwz)
print(detail.color, detail.confidence, detail.support, detail.level)
```

命令行重新生成全量 JSON 报告：

```powershell
python -m san_tools.analysis.analyze_minimap_color_relation . --out derived/minimap_color_relation/report.json
```

## 管理结论

1. `minimap_color` 继续作为 `.m` 的独立可编辑字段保存和导出。
2. `xyz` 预测只能用于“建议颜色”“新建内容初始值”或人工确认后的批量填充。
3. 自动应用时应展示 `confidence/support/level`；低置信度或仅命中全局回退时不得直接写入。
4. 若要进一步提高准确率，需要研究 Cell 坐标、邻域地形和数据标记字段，而不是假定颜色只由当前 Cell 的 xyz 决定。
