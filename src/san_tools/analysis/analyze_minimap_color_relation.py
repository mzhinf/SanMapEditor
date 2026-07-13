"""统计 `.m` 资源索引与 `minimap_color` 的关系，并提供近似预测器。"""

from __future__ import annotations

import argparse
import json
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

from san_tools.map.extract_kingdom import find_game_dir


CellColorRow = tuple[int, int, int, int]
KEY_LEVELS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("xyz", (0, 1, 2)),
    ("xy", (0, 1)),
    ("x", (0,)),
)
ANALYSIS_LEVELS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("x", (0,)),
    ("y", (1,)),
    ("z", (2,)),
    ("xy", (0, 1)),
    ("xz", (0, 2)),
    ("yz", (1, 2)),
    ("xyz", (0, 1, 2)),
)


@dataclass(frozen=True)
class ColorPrediction:
    """一次颜色预测及其统计依据。"""

    color: int
    confidence: float
    support: int
    level: str


def iter_m_color_rows(path: Path) -> Iterator[CellColorRow]:
    """严格按 `m.ksy` 的 16 字节 Cell 顺序读取 xyz 与颜色。"""

    blob = path.read_bytes()
    if len(blob) < 16 or blob[8:16] != b"Hello1.0":
        raise ValueError(f"不是合法的 .m 文件：{path}")
    width, height = struct.unpack_from("<II", blob, 0)
    expected_size = 16 + width * height * 16
    if len(blob) != expected_size:
        raise ValueError(f".m 长度错误：expected={expected_size} actual={len(blob)} path={path}")
    for index in range(width * height):
        offset = 16 + index * 16
        acwx, acwy, acwz = struct.unpack_from("<hhh", blob, offset)
        yield acwx, acwy, acwz, blob[offset + 13]


def _key(row: Sequence[int], indexes: Sequence[int]) -> tuple[int, ...]:
    return tuple(row[index] for index in indexes)


def _build_table(rows: Iterable[CellColorRow], indexes: Sequence[int]) -> dict[tuple[int, ...], Counter[int]]:
    table: dict[tuple[int, ...], Counter[int]] = defaultdict(Counter)
    for row in rows:
        table[_key(row, indexes)][row[3]] += 1
    return dict(table)


def _majority(counts: Counter[int]) -> tuple[int, int]:
    """返回稳定众数；频次相同时选择较小的颜色索引。"""

    color, frequency = max(counts.items(), key=lambda item: (item[1], -item[0]))
    return color, frequency


class MinimapColorPredictor:
    """使用 xyz 众数和分级回退预测小地图颜色。"""

    def __init__(self, rows: Iterable[CellColorRow]) -> None:
        materialized = tuple(rows)
        if not materialized:
            raise ValueError("至少需要一个 Cell 才能构建颜色预测器")
        self._tables = {
            name: _build_table(materialized, indexes)
            for name, indexes in KEY_LEVELS
        }
        self._global = Counter(row[3] for row in materialized)

    def predict_detail(self, acwx: int, acwy: int, acwz: int) -> ColorPrediction:
        """返回颜色、置信度、支持数及实际命中的回退层级。"""

        values = (acwx, acwy, acwz)
        for name, indexes in KEY_LEVELS:
            counts = self._tables[name].get(_key(values, indexes))
            if counts:
                color, frequency = _majority(counts)
                support = sum(counts.values())
                return ColorPrediction(color, frequency / support, support, name)
        color, frequency = _majority(self._global)
        support = sum(self._global.values())
        return ColorPrediction(color, frequency / support, support, "global")

    def predict_color(self, acwx: int, acwy: int, acwz: int) -> int:
        """输入 xyz 并只返回 0..255 的 `minimap_color`。"""

        return self.predict_detail(acwx, acwy, acwz).color


def build_minimap_color_function(rows: Iterable[CellColorRow]) -> Callable[[int, int, int], int]:
    """构建一个签名为 `(acwx, acwy, acwz) -> color` 的函数。"""

    predictor = MinimapColorPredictor(rows)
    return predictor.predict_color


def predictor_statistics(rows: Sequence[CellColorRow], indexes: Sequence[int]) -> dict[str, int | float]:
    """统计一个字段组合的确定性与样本内众数命中率。"""

    table = _build_table(rows, indexes)
    deterministic = [counts for counts in table.values() if len(counts) == 1]
    return {
        "keys": len(table),
        "ambiguous_keys": sum(len(counts) > 1 for counts in table.values()),
        "deterministic_key_rate": len(deterministic) / len(table),
        "deterministic_record_rate": sum(sum(counts.values()) for counts in deterministic) / len(rows),
        "majority_fit_accuracy": sum(max(counts.values()) for counts in table.values()) / len(rows),
    }


def _majority_excluding(global_counts: Counter[int], held_counts: Counter[int]) -> tuple[int, int, int] | None:
    """从全局计数中扣除当前留出关卡，返回众数、频次和支持数。"""

    remaining = [(count - held_counts[color], color) for color, count in global_counts.items()]
    positive = [(count, color) for count, color in remaining if count > 0]
    if not positive:
        return None
    frequency, color = max(positive, key=lambda item: (item[0], -item[1]))
    return color, frequency, sum(count for count, _ in positive)


def leave_one_stage_out(stage_rows: dict[str, Sequence[CellColorRow]]) -> dict[str, float | int]:
    """按关卡留一验证 xyz→xy→x→全局众数预测器。"""

    all_rows = tuple(row for rows in stage_rows.values() for row in rows)
    global_tables = {name: _build_table(all_rows, indexes) for name, indexes in KEY_LEVELS}
    global_colors = Counter(row[3] for row in all_rows)
    correct = exact_hits = total = 0
    for held_rows in stage_rows.values():
        held_tables = {name: _build_table(held_rows, indexes) for name, indexes in KEY_LEVELS}
        held_colors = Counter(row[3] for row in held_rows)
        cache: dict[tuple[str, tuple[int, ...]], int | None] = {}
        global_fallback = _majority_excluding(global_colors, held_colors)
        if global_fallback is None:
            raise ValueError("留一验证至少需要两个关卡")
        for row in held_rows:
            predicted: int | None = None
            for level_index, (name, indexes) in enumerate(KEY_LEVELS):
                value_key = _key(row, indexes)
                cache_key = name, value_key
                if cache_key not in cache:
                    result = _majority_excluding(
                        global_tables[name].get(value_key, Counter()),
                        held_tables[name].get(value_key, Counter()),
                    )
                    cache[cache_key] = result[0] if result else None
                predicted = cache[cache_key]
                if predicted is not None:
                    if level_index == 0:
                        exact_hits += 1
                    break
            if predicted is None:
                predicted = global_fallback[0]
            correct += int(predicted == row[3])
            total += 1
    return {
        "records": total,
        "accuracy": correct / total,
        "exact_xyz_coverage": exact_hits / total,
    }


def analyze_stage_files(paths: Sequence[Path]) -> dict[str, object]:
    """分析多个关卡并生成可序列化报告。"""

    stage_rows = {path.stem: tuple(iter_m_color_rows(path)) for path in paths}
    if not stage_rows:
        raise ValueError("没有可分析的 stage*.m")
    all_rows = tuple(row for rows in stage_rows.values() for row in rows)
    stats = {
        name: predictor_statistics(all_rows, indexes)
        for name, indexes in ANALYSIS_LEVELS
    }
    xyz_table = _build_table(all_rows, (0, 1, 2))
    conflicts = [
        {
            "xyz": list(value_key),
            "records": sum(counts.values()),
            "colors": [[color, count] for color, count in counts.most_common(5)],
        }
        for value_key, counts in xyz_table.items()
        if len(counts) > 1
    ]
    conflicts.sort(key=lambda item: int(item["records"]), reverse=True)
    return {
        "stages": len(stage_rows),
        "records": len(all_rows),
        "colors": len({row[3] for row in all_rows}),
        "predictors": stats,
        "leave_one_stage_out": leave_one_stage_out(stage_rows),
        "top_xyz_conflicts": conflicts[:20],
        "conclusion": "xyz 不是 minimap_color 的确定函数；众数模型只能作为建议值，不能替代原字段。",
    }


def main() -> int:
    """命令行导出全关卡关系报告。"""

    parser = argparse.ArgumentParser(description="分析 minimap_color 与 acwx/acwy/acwz 的统计关系")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--out", default=Path("derived/minimap_color_relation/report.json"), type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    game_dir = find_game_dir(root)
    report = analyze_stage_files(sorted(game_dir.glob("stage*.m")))
    out_path = args.out if args.out.is_absolute() else root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out_path), **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
