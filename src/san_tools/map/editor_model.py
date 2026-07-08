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

DOR_MAGIC = b"Door    Data"
STG_ENCODING = "big5"

KSY_ROOT = Path(__file__).resolve().parents[1] / "ksy"
M_KSY_SCHEMA_PATH = KSY_ROOT / "m.ksy"
DOR_KSY_SCHEMA_PATH = KSY_ROOT / "dor.ksy"
STG_KSY_SCHEMA_PATH = KSY_ROOT / "stg.ksy"


def read_u32(blob: bytes | bytearray, offset: int) -> int:
    """读取 little-endian u32。"""

    return int(struct.unpack_from("<I", blob, offset)[0])


def read_s32(blob: bytes | bytearray, offset: int) -> int:
    """读取 little-endian s32。"""

    return int(struct.unpack_from("<i", blob, offset)[0])


def decode_big5(raw: bytes) -> str:
    """按 Big5 定长字符串规则解码，遇到 0 截断。"""

    return raw.split(b"\x00", 1)[0].decode(STG_ENCODING, errors="replace")


def ensure_range(offset: int, size: int, total: int, label: str) -> None:
    """检查即将读取的字节区间是否越界。"""

    if offset < 0 or size < 0 or offset + size > total:
        raise ValueError(f"{label} 越界：offset={offset:#x}, size={size}, total={total}")


@dataclass(frozen=True)
class DorRecordModel:
    """保存 `.dor` 中一条城门记录。"""

    group_index: int
    record_index: int
    door_x: int
    door_y: int
    door_ori: int
    reserved0: tuple[int, ...]
    site_x: int
    site_y: int
    reserved1: int
    raw_words: tuple[int, ...]

    @classmethod
    def from_words(cls, group_index: int, record_index: int, words: tuple[int, ...]) -> "DorRecordModel":
        """从 15 个 u32 字段构造城门记录。"""

        if len(words) != 15:
            raise ValueError(f".dor 记录应包含 15 个 u32，实际 {len(words)}。")
        return cls(
            group_index=group_index,
            record_index=record_index,
            door_x=words[0],
            door_y=words[1],
            door_ori=words[2],
            reserved0=tuple(words[3:12]),
            site_x=words[12],
            site_y=words[13],
            reserved1=words[14],
            raw_words=words,
        )

    @property
    def site_key(self) -> str:
        """返回可与 `.stg` 据点坐标关联的键。"""

        return f"{self.site_x},{self.site_y}"

    def to_dict(self) -> dict[str, object]:
        """输出编辑器可直接消费的城门记录。"""

        return {
            "groupIndex": self.group_index,
            "recordIndex": self.record_index,
            "doorX": self.door_x,
            "doorY": self.door_y,
            "doorOri": self.door_ori,
            "siteX": self.site_x,
            "siteY": self.site_y,
            "siteKey": self.site_key,
            "reserved0": list(self.reserved0),
            "reserved1": self.reserved1,
            "rawWords": list(self.raw_words),
        }


@dataclass(frozen=True)
class DorGroupModel:
    """保存 `.dor` 中一组城门记录。"""

    group_index: int
    records: tuple[DorRecordModel, ...]

    def to_dict(self) -> dict[str, object]:
        """输出城门分组 JSON。"""

        return {
            "groupIndex": self.group_index,
            "recordCount": len(self.records),
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True)
class DorModel:
    """保存一个 `.dor` 城门文件的数据模型。"""

    stage: str
    record_size_words: int
    groups: tuple[DorGroupModel, ...]
    source: str | None = None
    has_zero_count_terminator: bool = False

    @classmethod
    def from_dor_bytes(cls, blob: bytes, stage: str = "", source: str | None = None) -> "DorModel":
        """从 `.dor` 原始字节构造城门模型。"""

        if len(blob) < 16:
            raise ValueError("数据过小，不是合法的 .dor 文件。")
        if blob[:12] != DOR_MAGIC:
            raise ValueError("不是 Door    Data 城门文件。")
        record_size_words = read_u32(blob, 0x0C)
        if record_size_words != 15:
            raise ValueError(f"当前仅支持 15 u32 的 .dor 记录，实际 record_size={record_size_words}。")
        offset = 0x10
        groups: list[DorGroupModel] = []
        has_zero_count_terminator = False
        group_index = 0
        while offset < len(blob):
            ensure_range(offset, 4, len(blob), ".dor group count")
            record_count = read_u32(blob, offset)
            offset += 4
            if record_count == 0 and offset == len(blob):
                has_zero_count_terminator = True
                break
            records: list[DorRecordModel] = []
            for record_index in range(record_count):
                record_size_bytes = record_size_words * 4
                ensure_range(offset, record_size_bytes, len(blob), ".dor record")
                words = struct.unpack_from("<15I", blob, offset)
                records.append(DorRecordModel.from_words(group_index, record_index, tuple(int(word) for word in words)))
                offset += record_size_bytes
            groups.append(DorGroupModel(group_index, tuple(records)))
            group_index += 1
        return cls(stage=stage, record_size_words=record_size_words, groups=tuple(groups), source=source, has_zero_count_terminator=has_zero_count_terminator)

    @classmethod
    def from_dor_file(cls, path: Path, stage: str | None = None) -> "DorModel":
        """读取 `.dor` 文件并构造城门模型。"""

        return cls.from_dor_bytes(path.read_bytes(), stage=stage or path.stem, source=str(path))

    @property
    def records(self) -> tuple[DorRecordModel, ...]:
        """展开所有城门记录。"""

        return tuple(record for group in self.groups for record in group.records)

    def to_dict(self) -> dict[str, object]:
        """输出 `.dor` 模型 JSON。"""

        payload: dict[str, object] = {
            "format": "san-editor-dor-v1",
            "stage": self.stage,
            "ksy": str(DOR_KSY_SCHEMA_PATH),
            "recordSizeWords": self.record_size_words,
            "groupCount": len(self.groups),
            "recordCount": len(self.records),
            "hasZeroCountTerminator": self.has_zero_count_terminator,
            "groups": [group.to_dict() for group in self.groups],
        }
        if self.source:
            payload["source"] = self.source
        return payload


@dataclass(frozen=True)
class StgBlockModel:
    """保存 `.stg` 中一个 `u32 size + payload` 块。"""

    name: str
    offset: int
    size: int
    payload: bytes

    @classmethod
    def read_from(cls, blob: bytes, offset: int, name: str) -> "StgBlockModel":
        """读取一个 STG 块，并保留原始 payload。"""

        ensure_range(offset, 4, len(blob), f"{name}.size")
        size = read_u32(blob, offset)
        payload_offset = offset + 4
        ensure_range(payload_offset, size, len(blob), name)
        return cls(name=name, offset=offset, size=size, payload=blob[payload_offset : payload_offset + size])

    @property
    def end_offset(self) -> int:
        """返回块结束偏移。"""

        return self.offset + 4 + self.size

    def u32(self, offset: int, default: int = 0) -> int:
        """读取 payload 内的 u32，越界时返回默认值。"""

        if offset + 4 > len(self.payload):
            return default
        return read_u32(self.payload, offset)

    def s32(self, offset: int, default: int = 0) -> int:
        """读取 payload 内的 s32，越界时返回默认值。"""

        if offset + 4 > len(self.payload):
            return default
        return read_s32(self.payload, offset)

    def text(self, offset: int, size: int) -> str:
        """读取 payload 内的 Big5 文本。"""

        if offset >= len(self.payload):
            return ""
        return decode_big5(self.payload[offset : min(len(self.payload), offset + size)])

    def to_dict(self) -> dict[str, object]:
        """输出块的可持久化表示。"""

        return {
            "name": self.name,
            "offset": self.offset,
            "offsetHex": f"0x{self.offset:X}",
            "size": self.size,
            "payloadHex": self.payload.hex(),
        }


@dataclass(frozen=True)
class StgEntityModel:
    """保存 `.stg` 中一个实体对象。"""

    index: int
    part1: StgBlockModel
    part2: StgBlockModel
    optional_slot: str | None = None

    @classmethod
    def read_from(cls, blob: bytes, offset: int, index: int, optional_slot: str | None = None) -> tuple["StgEntityModel", int]:
        """从对象流读取实体对象。"""

        part1 = StgBlockModel.read_from(blob, offset, "entity_part1")
        part2 = StgBlockModel.read_from(blob, part1.end_offset, "entity_part2")
        return cls(index=index, part1=part1, part2=part2, optional_slot=optional_slot), part2.end_offset

    @property
    def name(self) -> str:
        """实体名称。"""

        return self.part2.text(0x00, 20)

    @property
    def person_id(self) -> int:
        """人物编号候选。"""

        return self.part2.s32(0x14)

    @property
    def troop_count(self) -> int:
        """带兵数候选。"""

        return self.part2.s32(0x30)

    def to_summary_dict(self) -> dict[str, object]:
        """输出实体摘要。"""

        return {
            "index": self.index,
            "name": self.name,
            "personId": self.person_id,
            "troopCount": self.troop_count,
            "optionalSlot": self.optional_slot,
            "part1": self.part1.to_dict(),
            "part2": self.part2.to_dict(),
        }


@dataclass(frozen=True)
class StgSiteModel:
    """保存 `.stg` 中一个据点对象。"""

    index: int
    part1: StgBlockModel
    part2: StgBlockModel
    primary_entity_count: int
    entities: tuple[StgEntityModel, ...]
    optional_entities: tuple[StgEntityModel, ...]

    @classmethod
    def read_from(cls, blob: bytes, offset: int, index: int) -> tuple["StgSiteModel", int]:
        """从对象流读取据点对象及其实体列表。"""

        part1 = StgBlockModel.read_from(blob, offset, "site_part1")
        part2 = StgBlockModel.read_from(blob, part1.end_offset, "site_part2")
        ensure_range(part2.end_offset, 4, len(blob), "primary_entity_count")
        primary_entity_count = read_u32(blob, part2.end_offset)
        cursor = part2.end_offset + 4
        entities: list[StgEntityModel] = []
        for entity_index in range(primary_entity_count):
            entity, cursor = StgEntityModel.read_from(blob, cursor, entity_index)
            entities.append(entity)

        optional_entities: list[StgEntityModel] = []
        for flag_offset in (0x27C, 0x280, 0x284, 0x288, 0x28C):
            if part2.u32(flag_offset) == 0:
                continue
            optional_slot = f"0x{flag_offset:X}"
            entity, cursor = StgEntityModel.read_from(blob, cursor, len(optional_entities), optional_slot)
            optional_entities.append(entity)

        return cls(index=index, part1=part1, part2=part2, primary_entity_count=primary_entity_count, entities=tuple(entities), optional_entities=tuple(optional_entities)), cursor

    @property
    def name(self) -> str:
        """据点名称。"""

        return self.part1.text(0x00, 20)

    @property
    def city_index(self) -> int:
        """castle.txt 都市索引候选。"""

        return self.part1.s32(0x14)

    @property
    def map_x(self) -> int:
        """据点地图 X 坐标。"""

        return self.part1.s32(0x48)

    @property
    def map_y(self) -> int:
        """据点地图 Y 坐标。"""

        return self.part1.s32(0x4C)

    @property
    def site_key(self) -> str:
        """返回可与 `.dor` 城门关联的坐标键。"""

        return f"{self.map_x},{self.map_y}"

    @property
    def all_entities(self) -> tuple[StgEntityModel, ...]:
        """返回主实体与可选实体。"""

        return self.entities + self.optional_entities

    def to_summary_dict(self) -> dict[str, object]:
        """输出据点摘要。"""

        return {
            "index": self.index,
            "name": self.name,
            "cityIndex": self.city_index,
            "mapX": self.map_x,
            "mapY": self.map_y,
            "siteKey": self.site_key,
            "primaryEntityCount": self.primary_entity_count,
            "optionalEntityCount": len(self.optional_entities),
            "part1": self.part1.to_dict(),
            "part2": self.part2.to_dict(),
            "entities": [entity.to_summary_dict() for entity in self.entities],
            "optionalEntities": [entity.to_summary_dict() for entity in self.optional_entities],
        }


@dataclass(frozen=True)
class StgForceModel:
    """保存 `.stg` 中一个势力对象。"""

    index: int
    part1: StgBlockModel
    part2: StgBlockModel
    site_list_pre_count_or_flag: int
    sites: tuple[StgSiteModel, ...]

    @classmethod
    def read_from(cls, blob: bytes, offset: int, index: int) -> tuple["StgForceModel", int]:
        """从对象流读取势力对象及其据点列表。"""

        part1 = StgBlockModel.read_from(blob, offset, "force_part1")
        part2 = StgBlockModel.read_from(blob, part1.end_offset, "force_part2")
        ensure_range(part2.end_offset, 4, len(blob), "site_list_pre_count_or_flag")
        site_list_pre_count_or_flag = read_u32(blob, part2.end_offset)
        cursor = part2.end_offset + 4
        site_count = part2.u32(0x00)
        sites: list[StgSiteModel] = []
        for site_index in range(site_count):
            site, cursor = StgSiteModel.read_from(blob, cursor, site_index)
            sites.append(site)
        return cls(index=index, part1=part1, part2=part2, site_list_pre_count_or_flag=site_list_pre_count_or_flag, sites=tuple(sites)), cursor

    @property
    def name(self) -> str:
        """势力名称。"""

        return self.part1.text(0x00, 20)

    @property
    def site_count(self) -> int:
        """势力拥有的据点数量。"""

        return self.part2.u32(0x00)

    def to_summary_dict(self) -> dict[str, object]:
        """输出势力摘要。"""

        return {
            "index": self.index,
            "name": self.name,
            "siteCount": self.site_count,
            "siteListPreCountOrFlag": self.site_list_pre_count_or_flag,
            "part1": self.part1.to_dict(),
            "part2": self.part2.to_dict(),
            "sites": [site.to_summary_dict() for site in self.sites],
        }


@dataclass(frozen=True)
class StgModel:
    """保存一个 `.stg` 剧本对象流的数据模型。"""

    stage: str
    present_or_version: int
    root_part1: StgBlockModel
    root_part2: StgBlockModel
    force_count: int
    forces: tuple[StgForceModel, ...]
    after_forces_tail: bytes
    source: str | None = None

    @classmethod
    def from_stg_bytes(cls, blob: bytes, stage: str = "", source: str | None = None) -> "StgModel":
        """从 `.stg` 原始字节构造剧本模型。"""

        ensure_range(0, 4, len(blob), "present_or_version")
        present_or_version = read_u32(blob, 0)
        root_part1 = StgBlockModel.read_from(blob, 4, "root_part1")
        root_part2 = StgBlockModel.read_from(blob, root_part1.end_offset, "root_part2")
        ensure_range(root_part2.end_offset, 4, len(blob), "force_count")
        force_count = read_u32(blob, root_part2.end_offset)
        cursor = root_part2.end_offset + 4
        forces: list[StgForceModel] = []
        for force_index in range(force_count):
            force, cursor = StgForceModel.read_from(blob, cursor, force_index)
            forces.append(force)
        return cls(
            stage=stage,
            present_or_version=present_or_version,
            root_part1=root_part1,
            root_part2=root_part2,
            force_count=force_count,
            forces=tuple(forces),
            after_forces_tail=blob[cursor:],
            source=source,
        )

    @classmethod
    def from_stg_file(cls, path: Path, stage: str | None = None) -> "StgModel":
        """读取 `.stg` 文件并构造剧本模型。"""

        return cls.from_stg_bytes(path.read_bytes(), stage=stage or path.stem, source=str(path))

    @property
    def title(self) -> str:
        """剧本标题。"""

        return self.root_part1.text(0x00, 16)

    @property
    def scenario_year_start(self) -> int:
        """剧本起始年份。"""

        return self.root_part1.u32(0x1C)

    @property
    def scenario_year_end(self) -> int:
        """剧本结束年份。"""

        return self.root_part1.u32(0x20)

    @property
    def scenario_id(self) -> int:
        """剧本 ID。"""

        return self.root_part1.u32(0x34)

    @property
    def sites(self) -> tuple[StgSiteModel, ...]:
        """展开所有据点。"""

        return tuple(site for force in self.forces for site in force.sites)

    @property
    def entities(self) -> tuple[StgEntityModel, ...]:
        """展开所有实体。"""

        return tuple(entity for site in self.sites for entity in site.all_entities)

    def city_lookup_by_site_key(self) -> dict[str, StgSiteModel]:
        """按地图坐标键索引据点。"""

        return {site.site_key: site for site in self.sites}

    def to_summary_dict(self) -> dict[str, object]:
        """输出 `.stg` 模型摘要 JSON。"""

        payload: dict[str, object] = {
            "format": "san-editor-stg-v1",
            "stage": self.stage,
            "ksy": str(STG_KSY_SCHEMA_PATH),
            "presentOrVersion": self.present_or_version,
            "title": self.title,
            "scenarioYearStart": self.scenario_year_start,
            "scenarioYearEnd": self.scenario_year_end,
            "scenarioId": self.scenario_id,
            "forceCount": self.force_count,
            "siteCount": len(self.sites),
            "entityCount": len(self.entities),
            "afterForcesTailBytes": len(self.after_forces_tail),
            "rootPart1": self.root_part1.to_dict(),
            "rootPart2": self.root_part2.to_dict(),
            "forces": [force.to_summary_dict() for force in self.forces],
        }
        if self.source:
            payload["source"] = self.source
        return payload


@dataclass(frozen=True)
class StageEditFilesModel:
    """聚合 `.m/.dor/.stg` 的地图编辑上下文。"""

    stage: str
    map_model: StageMapModel | None = None
    dor_model: DorModel | None = None
    stg_model: StgModel | None = None
    sources: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_files(
        cls,
        stage: str,
        m_path: Path | None = None,
        dor_path: Path | None = None,
        stg_path: Path | None = None,
    ) -> "StageEditFilesModel":
        """从可选的 `.m/.dor/.stg` 路径构造聚合模型。"""

        map_model = StageMapModel.from_m_file(m_path, stage) if m_path is not None else None
        dor_model = DorModel.from_dor_file(dor_path, stage) if dor_path is not None else None
        stg_model = StgModel.from_stg_file(stg_path, stage) if stg_path is not None else None
        sources = {
            suffix: str(path)
            for suffix, path in (("m", m_path), ("dor", dor_path), ("stg", stg_path))
            if path is not None
        }
        return cls(stage=stage, map_model=map_model, dor_model=dor_model, stg_model=stg_model, sources=sources)

    def build_site_links(self) -> dict[str, object]:
        """建立 `.dor` 城门与 `.stg` 据点的坐标关联。"""

        if self.dor_model is None or self.stg_model is None:
            return {
                "available": False,
                "reason": "缺少 .dor 或 .stg，无法建立城门与据点关联。",
                "gates": [],
            }
        sites = self.stg_model.city_lookup_by_site_key()
        gates: list[dict[str, object]] = []
        matched = 0
        for record in self.dor_model.records:
            site = sites.get(record.site_key)
            if site is not None:
                matched += 1
            gate = record.to_dict()
            gate["siteName"] = site.name if site is not None else ""
            gate["cityIndex"] = site.city_index if site is not None else None
            gates.append(gate)
        return {
            "available": True,
            "gateCount": len(gates),
            "matchedGateCount": matched,
            "unmatchedGateCount": len(gates) - matched,
            "gates": gates,
        }

    def to_editor_context_dict(self) -> dict[str, object]:
        """输出可保存的多文件地图编辑上下文。"""

        return {
            "format": "san-editor-stage-files-v1",
            "stage": self.stage,
            "ksy": {
                "m": str(M_KSY_SCHEMA_PATH),
                "dor": str(DOR_KSY_SCHEMA_PATH),
                "stg": str(STG_KSY_SCHEMA_PATH),
            },
            "sources": self.sources,
            "map": self.map_model.to_editor_stage_dict() if self.map_model is not None else None,
            "dor": self.dor_model.to_dict() if self.dor_model is not None else None,
            "stg": self.stg_model.to_summary_dict() if self.stg_model is not None else None,
            "siteLinks": self.build_site_links(),
        }

    def write_editor_context_json(self, path: Path, indent: int = 2) -> None:
        """把多文件编辑上下文写入 JSON。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_editor_context_dict(), ensure_ascii=False, indent=indent), encoding="utf-8")
