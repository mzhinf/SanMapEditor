from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

STAGE_FORMAT = "san-editor-stage-v1"
PATCH_FORMAT = "san-editor-patch-v1"
M_MAGIC = b"Hello1.0"
M_HEADER_SIZE = 16
M_CELL_SIZE = 16

KSY_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "ksy" / "m.ksy"


@dataclass(frozen=True)
class MapFieldSpec:
    """描述 `.m` 单个 cell 字段在 KSY 与编辑器 JSON 之间的映射。"""

    name: str
    ksy_id: str
    offset: int
    fmt: str
    min_value: int
    max_value: int
    alias: str
    label: str
    editable: bool
    reserved: bool
    sidecar_source: bool = False
    legacy_names: tuple[str, ...] = ()

    @property
    def struct_format(self) -> str:
        """返回用于 `struct` 读写的 little-endian 格式。"""

        return f"<{self.fmt}"

    def read_from(self, record: bytes | bytearray) -> int:
        """从 16 字节 cell 记录中读取当前字段。"""

        if self.fmt == "B":
            return int(record[self.offset])
        return int(struct.unpack_from(self.struct_format, record, self.offset)[0])

    def validate_value(self, value: int) -> None:
        """校验字段值是否落在二进制格式允许范围内。"""

        if not isinstance(value, int):
            raise TypeError(f"{self.name} 必须是整数。")
        if not (self.min_value <= value <= self.max_value):
            raise ValueError(f"{self.name}={value} 超出范围 {self.min_value}..{self.max_value}。")


FIELD_SPECS: tuple[MapFieldSpec, ...] = (
    MapFieldSpec("acwx", "acwx", 0x00, "h", -32768, 32767, "terrain_base", "底层地表", True, False),
    MapFieldSpec("acwy", "acwy", 0x02, "h", -32768, 32767, "terrain_overlay", "叠加地表", True, False),
    MapFieldSpec("acwz", "acwz", 0x04, "h", -32768, 32767, "object_overlay", "物件层", True, False),
    MapFieldSpec("word06", "reserved0", 0x06, "h", -32768, 32767, "", "保留字段", False, True, legacy_names=("flags",)),
    MapFieldSpec("byte08", "terrain_tag", 0x08, "B", 0, 255, "land_water_hint", "水陆切换提示", True, False),
    MapFieldSpec("byte09", "blocked", 0x09, "B", 0, 255, "blocked", "阻挡标记", True, False),
    MapFieldSpec("byte10", "site_trigger", 0x0A, "B", 0, 255, "site_trigger", "据点触发", True, False),
    MapFieldSpec("byte11", "site_area", 0x0B, "B", 0, 255, "site_area", "据点区域", True, False),
    MapFieldSpec("byte12", "reserved1", 0x0C, "B", 0, 255, "reserved1", "保留字段 1", False, True),
    MapFieldSpec("byte13", "minimap_color", 0x0D, "B", 0, 255, "minimap_color", "小地图颜色", True, False, True, ("final_palette",)),
    MapFieldSpec("byte14", "reserved2", 0x0E, "B", 0, 255, "reserved2", "保留字段 2", False, True),
    MapFieldSpec("byte15", "reserved2", 0x0F, "B", 0, 255, "reserved3", "保留字段 3", False, True),
)

FIELD_NAMES: tuple[str, ...] = tuple(spec.name for spec in FIELD_SPECS)
EDITABLE_LAYERS: tuple[str, ...] = ("acwx", "acwy", "acwz")
POINT_LAYER_FIELDS: tuple[str, ...] = ("byte08", "byte09", "byte10", "byte11")
EDITABLE_RECORD_FIELDS: tuple[str, ...] = tuple(spec.name for spec in FIELD_SPECS if spec.editable)
FIELD_BY_NAME: dict[str, MapFieldSpec] = {spec.name: spec for spec in FIELD_SPECS}
for _spec in FIELD_SPECS:
    for _legacy_name in _spec.legacy_names:
        FIELD_BY_NAME[_legacy_name] = _spec


def canonical_field_name(name: str) -> str:
    """把旧字段名转换为当前编辑器字段名。"""

    try:
        return FIELD_BY_NAME[name].name
    except KeyError as exc:
        raise ValueError(f"不支持的地图字段：{name!r}") from exc


def field_meta() -> list[dict[str, object]]:
    """生成编辑器 stage JSON 使用的字段元数据。"""

    rows: list[dict[str, object]] = []
    for spec in FIELD_SPECS:
        row: dict[str, object] = {
            "name": spec.name,
            "alias": spec.alias,
            "label": spec.label,
            "editable": spec.editable,
            "reserved": spec.reserved,
            "ksyId": spec.ksy_id,
            "offset": spec.offset,
        }
        if spec.sidecar_source:
            row["sidecarSource"] = True
        if spec.legacy_names:
            row["legacyNames"] = list(spec.legacy_names)
        rows.append(row)
    return rows


@dataclass(frozen=True)
class MapCell:
    """保存 `.m` 文件中一个地图 cell 的全部 16 字节可解释字段。"""

    acwx: int
    acwy: int
    acwz: int
    word06: int
    byte08: int
    byte09: int
    byte10: int
    byte11: int
    byte12: int
    byte13: int
    byte14: int
    byte15: int

    @classmethod
    def from_record(cls, record: bytes | bytearray) -> "MapCell":
        """从单条 16 字节 cell 记录构造模型。"""

        if len(record) != M_CELL_SIZE:
            raise ValueError(f"cell 记录长度应为 {M_CELL_SIZE} 字节，实际 {len(record)} 字节。")
        values = {spec.name: spec.read_from(record) for spec in FIELD_SPECS}
        return cls(**values)

    @classmethod
    def from_editor_record(cls, values: Iterable[int]) -> "MapCell":
        """从编辑器 JSON 的数组记录构造模型。"""

        row = list(values)
        if len(row) != len(FIELD_SPECS):
            raise ValueError(f"编辑器记录字段数应为 {len(FIELD_SPECS)}，实际 {len(row)}。")
        for spec, value in zip(FIELD_SPECS, row):
            spec.validate_value(value)
        return cls(**dict(zip(FIELD_NAMES, row)))

    def as_editor_record(self) -> list[int]:
        """按编辑器 JSON 字段顺序输出数组记录。"""

        return [int(getattr(self, spec.name)) for spec in FIELD_SPECS]

    def value_of(self, field_name: str) -> int:
        """读取指定字段值，兼容历史字段名。"""

        return int(getattr(self, canonical_field_name(field_name)))


@dataclass
class StageMapModel:
    """保存一个关卡 `.m` 地图的可编辑模型。"""

    stage: str
    width: int
    height: int
    cells: list[MapCell]
    source: str | None = None

    @classmethod
    def from_m_bytes(cls, blob: bytes, stage: str = "", source: str | None = None) -> "StageMapModel":
        """从 `.m` 原始字节构造地图模型。"""

        if len(blob) < M_HEADER_SIZE:
            raise ValueError("数据过小，不是合法的 .m 文件。")
        width, height = struct.unpack_from("<II", blob, 0)
        if blob[8:16] != M_MAGIC:
            raise ValueError("不是 Hello1.0 地图文件。")
        expected_size = M_HEADER_SIZE + width * height * M_CELL_SIZE
        if len(blob) < expected_size:
            raise ValueError(f".m 数据长度不足，期望至少 {expected_size} 字节，实际 {len(blob)} 字节。")
        cells = [
            MapCell.from_record(blob[M_HEADER_SIZE + index * M_CELL_SIZE : M_HEADER_SIZE + (index + 1) * M_CELL_SIZE])
            for index in range(width * height)
        ]
        return cls(stage=stage, width=width, height=height, cells=cells, source=source)

    @classmethod
    def from_m_file(cls, path: Path, stage: str | None = None) -> "StageMapModel":
        """读取 `.m` 文件并构造地图模型。"""

        return cls.from_m_bytes(path.read_bytes(), stage=stage or path.stem, source=str(path))

    def __post_init__(self) -> None:
        """确保模型尺寸与 cell 数量一致。"""

        if self.width <= 0 or self.height <= 0:
            raise ValueError("地图宽高必须为正数。")
        expected_cells = self.width * self.height
        if len(self.cells) != expected_cells:
            raise ValueError(f"cell 数量应为 {expected_cells}，实际 {len(self.cells)}。")

    def cell_index(self, x: int, y: int) -> int:
        """把二维坐标转换为记录下标。"""

        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError(f"cell 坐标越界：{x},{y}，地图尺寸 {self.width}x{self.height}。")
        return y * self.width + x

    def cell_at(self, x: int, y: int) -> MapCell:
        """读取指定坐标的 cell。"""

        return self.cells[self.cell_index(x, y)]

    def editor_records(self) -> list[list[int]]:
        """输出编辑器 stage JSON 使用的二维记录数组。"""

        return [cell.as_editor_record() for cell in self.cells]

    def minimap_color_bytes(self) -> bytes:
        """返回 `.s/.x` 有效区派生所需的小地图颜色字节。"""

        return bytes(cell.byte13 for cell in self.cells)

    def to_editor_stage_dict(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """输出可持久化的地图编辑器 stage JSON。"""

        payload: dict[str, Any] = {
            "format": STAGE_FORMAT,
            "stage": self.stage,
            "width": self.width,
            "height": self.height,
            "ksy": str(KSY_SCHEMA_PATH),
            "fields": list(FIELD_NAMES),
            "fieldMeta": field_meta(),
            "editableLayers": list(EDITABLE_LAYERS),
            "resourceLayers": list(EDITABLE_LAYERS),
            "pointLayers": list(POINT_LAYER_FIELDS),
            "editableRecordFields": list(EDITABLE_RECORD_FIELDS),
            "records": self.editor_records(),
        }
        if self.source is not None:
            payload["source"] = self.source
        if extra:
            payload.update(extra)
        return payload

    def write_editor_stage_json(self, path: Path, extra: dict[str, Any] | None = None, indent: int | None = None) -> None:
        """把地图编辑模型写成 stage JSON 文件。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_editor_stage_dict(extra), ensure_ascii=False, indent=indent), encoding="utf-8")


@dataclass(frozen=True)
class MapEditChange:
    """保存单个 cell 字段修改。"""

    x: int
    y: int
    field: str
    before: int
    after: int

    def __post_init__(self) -> None:
        """规范化字段名，并校验修改前后的值范围。"""

        spec = FIELD_BY_NAME[canonical_field_name(self.field)]
        spec.validate_value(self.before)
        spec.validate_value(self.after)
        object.__setattr__(self, "field", spec.name)

    def as_json_dict(self) -> dict[str, int | str]:
        """输出编辑器 patch JSON 中的 change 对象。"""

        return {"x": self.x, "y": self.y, "field": self.field, "before": self.before, "after": self.after}


@dataclass
class MapEditPatchModel:
    """保存一次地图编辑操作产生的 patch。"""

    stage: str
    changes: list[MapEditChange] = field(default_factory=list)
    minimap_dirty_cells: list[tuple[int, int]] = field(default_factory=list)
    fields: tuple[str, ...] = FIELD_NAMES

    def to_patch_dict(self) -> dict[str, Any]:
        """输出可由 `apply_editor_patch.py` 消费的 patch JSON。"""

        return {
            "format": PATCH_FORMAT,
            "stage": self.stage,
            "fields": list(self.fields),
            "minimap": {"dirtyCells": [list(cell) for cell in self.minimap_dirty_cells]},
            "changes": [change.as_json_dict() for change in self.changes],
        }

    def write_patch_json(self, path: Path, indent: int = 2) -> None:
        """把 patch 模型写入 JSON 文件。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_patch_dict(), ensure_ascii=False, indent=indent), encoding="utf-8")
