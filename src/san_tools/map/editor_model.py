from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

KSY_ROOT = Path(__file__).resolve().parents[1] / "ksy"
M_KSY_PATH = KSY_ROOT / "m.ksy"
DOR_KSY_PATH = KSY_ROOT / "dor.ksy"
STG_KSY_PATH = KSY_ROOT / "stg.ksy"

M_MAGIC = b"Hello1.0"
DOR_MAGIC = b"Door    Data"
BIG5_ENCODING = "big5"


def _ensure_range(blob: bytes, offset: int, size: int, label: str) -> None:
    """检查读取区间是否落在二进制范围内。"""

    if offset < 0 or size < 0 or offset + size > len(blob):
        raise ValueError(f"{label} 越界：offset={offset:#x} size={size} total={len(blob)}")


def _read_exact(blob: bytes, offset: int, size: int, label: str) -> bytes:
    """读取固定长度字节片段。"""

    _ensure_range(blob, offset, size, label)
    return blob[offset : offset + size]


def _read_u4(blob: bytes, offset: int, label: str) -> int:
    """读取 little-endian u4。"""

    return int(struct.unpack("<I", _read_exact(blob, offset, 4, label))[0])


def _read_s4(blob: bytes, offset: int, label: str) -> int:
    """读取 little-endian s4。"""

    return int(struct.unpack("<i", _read_exact(blob, offset, 4, label))[0])


def _read_s2(blob: bytes, offset: int, label: str) -> int:
    """读取 little-endian s2。"""

    return int(struct.unpack("<h", _read_exact(blob, offset, 2, label))[0])


def _read_u1(blob: bytes, offset: int, label: str) -> int:
    """读取 u1。"""

    return int(_read_exact(blob, offset, 1, label)[0])


def _decode_big5(raw: bytes) -> str:
    """按 KSY 的 Big5 定长字符串规则解码。"""

    return raw.split(b"\x00", 1)[0].decode(BIG5_ENCODING, errors="replace")


def _expect_bytes(blob: bytes, offset: int, expected: bytes, label: str) -> bytes:
    """读取并校验 contents 固定字节。"""

    raw = _read_exact(blob, offset, len(expected), label)
    if raw != expected:
        raise ValueError(f"{label} 不匹配：expected={expected!r} actual={raw!r}")
    return raw


@dataclass(frozen=True)
class U4Words:
    """对应 u4_words，用于保存未命名但按 4 字节对齐的原始字数组。"""

    words: tuple[int, ...]

    @classmethod
    def from_bytes(cls, blob: bytes, label: str) -> "U4Words":
        """把整段字节按 u4 数组解析。"""

        if len(blob) % 4 != 0:
            raise ValueError(f"{label} 长度必须是 4 的倍数，实际为 {len(blob)}")
        return cls(words=tuple(struct.unpack(f"<{len(blob) // 4}I", blob)) if blob else ())


class _SeqReader:
    """顺序读取器，用于把 KSY 中的 seq 按声明顺序稳定映射到模型字段。"""

    def __init__(self, blob: bytes, label: str) -> None:
        self._blob = blob
        self._label = label
        self._offset = 0

    def remaining(self) -> int:
        """返回剩余未消费字节数。"""

        return len(self._blob) - self._offset

    def u4(self, field_name: str) -> int:
        """顺序读取一个 u4 字段。"""

        value = _read_u4(self._blob, self._offset, f"{self._label}.{field_name}")
        self._offset += 4
        return value

    def s4(self, field_name: str) -> int:
        """顺序读取一个 s4 字段。"""

        value = _read_s4(self._blob, self._offset, f"{self._label}.{field_name}")
        self._offset += 4
        return value

    def s2(self, field_name: str) -> int:
        """顺序读取一个 s2 字段。"""

        value = _read_s2(self._blob, self._offset, f"{self._label}.{field_name}")
        self._offset += 2
        return value

    def u1(self, field_name: str) -> int:
        """顺序读取一个 u1 字段。"""

        value = _read_u1(self._blob, self._offset, f"{self._label}.{field_name}")
        self._offset += 1
        return value

    def exact(self, size: int, expected: bytes, field_name: str) -> bytes:
        """顺序读取一个 contents 固定字节字段。"""

        raw = _expect_bytes(self._blob, self._offset, expected, f"{self._label}.{field_name}")
        self._offset += size
        return raw

    def big5(self, size: int, field_name: str) -> str:
        """顺序读取一个 Big5 定长字符串字段。"""

        raw = _read_exact(self._blob, self._offset, size, f"{self._label}.{field_name}")
        self._offset += size
        return _decode_big5(raw)

    def u4_tuple(self, count: int, field_name: str) -> tuple[int, ...]:
        """顺序读取定长 u4 数组。"""

        size = count * 4
        raw = _read_exact(self._blob, self._offset, size, f"{self._label}.{field_name}")
        self._offset += size
        return tuple(struct.unpack(f"<{count}I", raw))

    def u4_words_to_end(self, field_name: str) -> U4Words:
        """把剩余字节全部按 u4_words 解析。"""

        raw = self._blob[self._offset :]
        self._offset = len(self._blob)
        return U4Words.from_bytes(raw, f"{self._label}.{field_name}")

    def finish(self) -> None:
        """确保当前结构没有剩余未消费字节。"""

        if self._offset != len(self._blob):
            raise ValueError(
                f"{self._label} 仍有未解析数据：parsed={self._offset} total={len(self._blob)}"
            )


def _read_sized_block(blob: bytes, offset: int, label: str) -> tuple[int, bytes, int]:
    """读取 KSY 中反复出现的 u32 size + payload 块。"""

    size = _read_u4(blob, offset, f"{label}.size")
    payload_offset = offset + 4
    payload = _read_exact(blob, payload_offset, size, f"{label}.body")
    return size, payload, payload_offset + size


@dataclass(frozen=True)
class MMapCell:
    """对应 m.ksy.types.map_cell。"""

    acwx: int
    acwy: int
    acwz: int
    reserved0: bytes
    terrain_tag: int
    blocked: int
    site_trigger: int
    site_area: int
    reserved1: bytes
    minimap_color: int
    reserved2: bytes

    @classmethod
    def from_bytes(cls, blob: bytes) -> "MMapCell":
        """按 map_cell.seq 顺序解析单个地图单元。"""

        if len(blob) != 16:
            raise ValueError(f"map_cell 长度必须为 16，实际为 {len(blob)}")
        reader = _SeqReader(blob, "map_cell")
        model = cls(
            acwx=reader.s2("acwx"),
            acwy=reader.s2("acwy"),
            acwz=reader.s2("acwz"),
            reserved0=reader.exact(2, b"\x00\x00", "reserved0"),
            terrain_tag=reader.u1("terrain_tag"),
            blocked=reader.u1("blocked"),
            site_trigger=reader.u1("site_trigger"),
            site_area=reader.u1("site_area"),
            reserved1=reader.exact(1, b"\x00", "reserved1"),
            minimap_color=reader.u1("minimap_color"),
            reserved2=reader.exact(2, b"\x00\x00", "reserved2"),
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class MFile:
    """对应 m.ksy 顶层结构。"""

    width: int
    height: int
    magic_bytes: bytes
    cells: tuple[MMapCell, ...]

    @property
    def cell_size(self) -> int:
        """对应 instances.cell_size。"""

        return self.width * self.height

    @classmethod
    def from_bytes(cls, blob: bytes) -> "MFile":
        """按 m.ksy 解析整个 .m 文件。"""

        reader = _SeqReader(blob, "m")
        width = reader.u4("width")
        height = reader.u4("height")
        magic_bytes = reader.exact(8, M_MAGIC, "magic_bytes")
        cells = tuple(
            MMapCell.from_bytes(_read_exact(blob, 16 + index * 16, 16, f"cells[{index}]"))
            for index in range(width * height)
        )
        if len(blob) != 16 + len(cells) * 16:
            raise ValueError(".m 文件长度与 width * height * 16 + header 不一致")
        return cls(width=width, height=height, magic_bytes=magic_bytes, cells=cells)

    @classmethod
    def from_file(cls, path: Path) -> "MFile":
        """从文件系统读取 .m 文件。"""

        return cls.from_bytes(path.read_bytes())


@dataclass(frozen=True)
class DorRecord:
    """对应 dor.ksy.types.dor_record。"""

    door_x: int
    door_y: int
    door_ori: int
    reserved0: tuple[int, ...]
    site_x: int
    site_y: int
    reserved1: int

    @classmethod
    def from_bytes(cls, blob: bytes) -> "DorRecord":
        """按单条 15 个 u4 记录解析城门记录。"""

        if len(blob) != 60:
            raise ValueError(f"dor_record 长度必须为 60，实际为 {len(blob)}")
        reader = _SeqReader(blob, "dor_record")
        model = cls(
            door_x=reader.u4("door_x"),
            door_y=reader.u4("door_y"),
            door_ori=reader.u4("door_ori"),
            reserved0=reader.u4_tuple(9, "reserved0"),
            site_x=reader.u4("site_x"),
            site_y=reader.u4("site_y"),
            reserved1=reader.u4("reserved1"),
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class DorGroup:
    """对应 dor.ksy.types.dor_group。"""

    record_count: int
    records: tuple[DorRecord, ...]


@dataclass(frozen=True)
class DorFile:
    """对应 dor.ksy 顶层结构。"""

    magic_bytes: bytes
    record_size: int
    dor_groups: tuple[DorGroup, ...]

    @property
    def record_size_bytes(self) -> int:
        """对应 instances.record_size_bytes。"""

        return self.record_size * 4

    @classmethod
    def from_bytes(cls, blob: bytes) -> "DorFile":
        """按 dor.ksy 解析整个 .dor 文件。"""

        reader = _SeqReader(blob, "dor")
        magic_bytes = reader.exact(12, DOR_MAGIC, "magic_bytes")
        record_size = reader.u4("record_size")
        offset = 16
        groups: list[DorGroup] = []
        group_index = 0
        while offset < len(blob):
            record_count = _read_u4(blob, offset, f"dor_groups[{group_index}].record_count")
            offset += 4
            records: list[DorRecord] = []
            for record_index in range(record_count):
                record_blob = _read_exact(
                    blob,
                    offset,
                    60,
                    f"dor_groups[{group_index}].records[{record_index}]",
                )
                records.append(DorRecord.from_bytes(record_blob))
                offset += 60
            groups.append(DorGroup(record_count=record_count, records=tuple(records)))
            group_index += 1
        return cls(magic_bytes=magic_bytes, record_size=record_size, dor_groups=tuple(groups))

    @classmethod
    def from_file(cls, path: Path) -> "DorFile":
        """从文件系统读取 .dor 文件。"""

        return cls.from_bytes(path.read_bytes())


@dataclass(frozen=True)
class RootPart1Payload:
    """对应 stg.ksy.types.root_part1_payload。"""

    scenario_title: str
    root1_special_mode_or_title_tail_10: int
    reserved_zero_14: int
    reserved_zero_18: int
    scenario_year_start: int
    scenario_year_end: int
    scenario_mode_flag_a: int
    reserved_zero_28: int
    scenario_mode_flag_b: int
    scenario_id: int
    scenario_id_or_duplicate: int
    root1_variant_38: int
    root1_variant_3c: int
    reserved_zero_40: int
    root1_scenario_type_44: int
    reserved_zero_48: int | None

    @classmethod
    def from_bytes(cls, blob: bytes) -> "RootPart1Payload":
        """按 root_part1_payload.seq 解析。"""

        reader = _SeqReader(blob, "root_part1_payload")
        model = cls(
            scenario_title=reader.big5(16, "scenario_title"),
            root1_special_mode_or_title_tail_10=reader.u4("root1_special_mode_or_title_tail_10"),
            reserved_zero_14=reader.u4("reserved_zero_14"),
            reserved_zero_18=reader.u4("reserved_zero_18"),
            scenario_year_start=reader.u4("scenario_year_start"),
            scenario_year_end=reader.u4("scenario_year_end"),
            scenario_mode_flag_a=reader.u4("scenario_mode_flag_a"),
            reserved_zero_28=reader.u4("reserved_zero_28"),
            scenario_mode_flag_b=reader.u4("scenario_mode_flag_b"),
            scenario_id=reader.u4("scenario_id"),
            scenario_id_or_duplicate=reader.u4("scenario_id_or_duplicate"),
            root1_variant_38=reader.u4("root1_variant_38"),
            root1_variant_3c=reader.u4("root1_variant_3c"),
            reserved_zero_40=reader.u4("reserved_zero_40"),
            root1_scenario_type_44=reader.u4("root1_scenario_type_44"),
            reserved_zero_48=reader.u4("reserved_zero_48") if reader.remaining() >= 4 else None,
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class RootPart2Payload:
    """对应 stg.ksy.types.root_part2_payload。"""

    root2_mode_00: int
    root2_mode_04: int
    root2_value_08: int
    root2_value_0c: int
    root2_pointer_or_mode_10: int
    force_count_mirror_candidate: int
    reserved_zero_18: int
    root2_mode_1c: int
    reserved_zero_20: int
    root2_pointer_or_mode_24: int
    root2_mode_28: int
    reserved_zero_2c: int
    root2_mode_30: int

    @classmethod
    def from_bytes(cls, blob: bytes) -> "RootPart2Payload":
        """按 root_part2_payload.seq 解析。"""

        reader = _SeqReader(blob, "root_part2_payload")
        model = cls(
            root2_mode_00=reader.u4("root2_mode_00"),
            root2_mode_04=reader.u4("root2_mode_04"),
            root2_value_08=reader.u4("root2_value_08"),
            root2_value_0c=reader.u4("root2_value_0c"),
            root2_pointer_or_mode_10=reader.u4("root2_pointer_or_mode_10"),
            force_count_mirror_candidate=reader.u4("force_count_mirror_candidate"),
            reserved_zero_18=reader.u4("reserved_zero_18"),
            root2_mode_1c=reader.u4("root2_mode_1c"),
            reserved_zero_20=reader.u4("reserved_zero_20"),
            root2_pointer_or_mode_24=reader.u4("root2_pointer_or_mode_24"),
            root2_mode_28=reader.u4("root2_mode_28"),
            reserved_zero_2c=reader.u4("reserved_zero_2c"),
            root2_mode_30=reader.u4("root2_mode_30"),
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class ForcePart1Payload:
    """对应 stg.ksy.types.force_part1_payload。"""

    force_name: str
    force_slot_or_index_14: int
    force_lord_person_id: int
    force_ai_or_diplomacy_mode_1c: int
    force_flag_20: int
    force_level_or_group_24: int
    force_policy_28: int
    force_policy_2c: int
    reserved_zero_30: int
    reserved_zero_34: int
    force_timer_or_score_38: int
    force_timer_or_score_3c: int
    force_flag_40: int
    reserved_zero_44: int
    force_rare_flag_48: int
    force_ai_mode_4c: int
    force_rare_flag_50: int
    force_rare_value_54: int
    force_budget_or_delay_58: int
    force_ai_mode_5c: int

    @classmethod
    def from_bytes(cls, blob: bytes) -> "ForcePart1Payload":
        """按 force_part1_payload.seq 解析。"""

        reader = _SeqReader(blob, "force_part1_payload")
        model = cls(
            force_name=reader.big5(20, "force_name"),
            force_slot_or_index_14=reader.u4("force_slot_or_index_14"),
            force_lord_person_id=reader.u4("force_lord_person_id"),
            force_ai_or_diplomacy_mode_1c=reader.u4("force_ai_or_diplomacy_mode_1c"),
            force_flag_20=reader.u4("force_flag_20"),
            force_level_or_group_24=reader.u4("force_level_or_group_24"),
            force_policy_28=reader.u4("force_policy_28"),
            force_policy_2c=reader.u4("force_policy_2c"),
            reserved_zero_30=reader.u4("reserved_zero_30"),
            reserved_zero_34=reader.u4("reserved_zero_34"),
            force_timer_or_score_38=reader.u4("force_timer_or_score_38"),
            force_timer_or_score_3c=reader.u4("force_timer_or_score_3c"),
            force_flag_40=reader.u4("force_flag_40"),
            reserved_zero_44=reader.u4("reserved_zero_44"),
            force_rare_flag_48=reader.u4("force_rare_flag_48"),
            force_ai_mode_4c=reader.u4("force_ai_mode_4c"),
            force_rare_flag_50=reader.u4("force_rare_flag_50"),
            force_rare_value_54=reader.u4("force_rare_value_54"),
            force_budget_or_delay_58=reader.u4("force_budget_or_delay_58"),
            force_ai_mode_5c=reader.u4("force_ai_mode_5c"),
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class ForcePart2Payload:
    """对应 stg.ksy.types.force_part2_payload。"""

    site_count: int
    force_index_1based: int
    force_lord_person_id_or_ref: int
    reserved_zero_0c: int
    force_runtime_ref_10: int
    force_runtime_ref_14: int
    reserved_zero_18: int
    reserved_zero_1c: int
    reserved_zero_20: int
    resource_slots_24_48: tuple[int, ...]
    ai_relation_flags_4c_74: tuple[int, ...]
    force_strategy_budget_78: int
    reserved_zero_7c: int | None
    reserved_zero_80: int | None

    @classmethod
    def from_bytes(cls, blob: bytes) -> "ForcePart2Payload":
        """按 force_part2_payload.seq 解析。"""

        reader = _SeqReader(blob, "force_part2_payload")
        model = cls(
            site_count=reader.u4("site_count"),
            force_index_1based=reader.u4("force_index_1based"),
            force_lord_person_id_or_ref=reader.u4("force_lord_person_id_or_ref"),
            reserved_zero_0c=reader.u4("reserved_zero_0c"),
            force_runtime_ref_10=reader.u4("force_runtime_ref_10"),
            force_runtime_ref_14=reader.u4("force_runtime_ref_14"),
            reserved_zero_18=reader.u4("reserved_zero_18"),
            reserved_zero_1c=reader.u4("reserved_zero_1c"),
            reserved_zero_20=reader.u4("reserved_zero_20"),
            resource_slots_24_48=reader.u4_tuple(10, "resource_slots_24_48"),
            ai_relation_flags_4c_74=reader.u4_tuple(11, "ai_relation_flags_4c_74"),
            force_strategy_budget_78=reader.u4("force_strategy_budget_78"),
            reserved_zero_7c=reader.u4("reserved_zero_7c") if reader.remaining() >= 4 else None,
            reserved_zero_80=reader.u4("reserved_zero_80") if reader.remaining() >= 4 else None,
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class SitePart1Payload:
    """对应 stg.ksy.types.site_part1_payload。"""

    site_name: str
    city_index: int
    house_attr: int
    castle_scale: int
    population: int
    gold: int
    food: int
    standby_soldier: int
    develop: int
    commerce: int
    security: int
    develop_limit: int
    commerce_limit: int
    security_limit: int
    coord_x: int
    coord_y: int
    governor: int
    general_count_or_slot: int
    site_part1_extra_words: U4Words

    @classmethod
    def from_bytes(cls, blob: bytes) -> "SitePart1Payload":
        """按 site_part1_payload.seq 解析。"""

        reader = _SeqReader(blob, "site_part1_payload")
        model = cls(
            site_name=reader.big5(20, "site_name"),
            city_index=reader.s4("city_index"),
            house_attr=reader.s4("house_attr"),
            castle_scale=reader.s4("castle_scale"),
            population=reader.s4("population"),
            gold=reader.s4("gold"),
            food=reader.s4("food"),
            standby_soldier=reader.s4("standby_soldier"),
            develop=reader.s4("develop"),
            commerce=reader.s4("commerce"),
            security=reader.s4("security"),
            develop_limit=reader.s4("develop_limit"),
            commerce_limit=reader.s4("commerce_limit"),
            security_limit=reader.s4("security_limit"),
            coord_x=reader.s4("coord_x"),
            coord_y=reader.s4("coord_y"),
            governor=reader.s4("governor"),
            general_count_or_slot=reader.s4("general_count_or_slot"),
            site_part1_extra_words=reader.u4_words_to_end("site_part1_extra_words"),
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class SitePart2Payload:
    """对应 stg.ksy.types.site_part2_payload。"""

    reserved_zero_000: int
    runtime_coord_or_spawn_x_004: int
    runtime_coord_or_spawn_y_008: int
    site_kind_or_force_group_00c: int
    site_serial_010: int
    site_flag_014: int
    reserved_zero_018: int
    site_small_counter_01c: int
    reserved_zero_020: int
    sentinel_minus_one_024: int
    reserved_zero_028: int
    reserved_zero_02c: int
    site_flag_030: int
    reserved_zero_034: int
    reserved_zero_038: int
    site_flag_03c: int
    reserved_zero_040_054: tuple[int, ...]
    ai_template_params_058_130: tuple[int, ...]
    reserved_zero_134_20c: tuple[int, ...]
    runtime_tail_words_210_278: tuple[int, ...]
    optional_entity_flag_27c: int
    optional_entity_flag_280: int
    optional_entity_flag_284: int
    optional_entity_flag_288: int
    optional_entity_flag_28c: int
    reserved_zero_290: int
    runtime_rare_flag_294: int
    runtime_budget_298: int
    runtime_bitfield_29c: int
    runtime_mode_2a0: int
    reserved_zero_2a4: int
    reserved_zero_2a8: int
    reserved_zero_2ac: int

    @classmethod
    def from_bytes(cls, blob: bytes) -> "SitePart2Payload":
        """按 site_part2_payload.seq 解析。"""

        reader = _SeqReader(blob, "site_part2_payload")
        model = cls(
            reserved_zero_000=reader.u4("reserved_zero_000"),
            runtime_coord_or_spawn_x_004=reader.s4("runtime_coord_or_spawn_x_004"),
            runtime_coord_or_spawn_y_008=reader.s4("runtime_coord_or_spawn_y_008"),
            site_kind_or_force_group_00c=reader.u4("site_kind_or_force_group_00c"),
            site_serial_010=reader.u4("site_serial_010"),
            site_flag_014=reader.u4("site_flag_014"),
            reserved_zero_018=reader.u4("reserved_zero_018"),
            site_small_counter_01c=reader.u4("site_small_counter_01c"),
            reserved_zero_020=reader.u4("reserved_zero_020"),
            sentinel_minus_one_024=reader.u4("sentinel_minus_one_024"),
            reserved_zero_028=reader.u4("reserved_zero_028"),
            reserved_zero_02c=reader.u4("reserved_zero_02c"),
            site_flag_030=reader.u4("site_flag_030"),
            reserved_zero_034=reader.u4("reserved_zero_034"),
            reserved_zero_038=reader.u4("reserved_zero_038"),
            site_flag_03c=reader.u4("site_flag_03c"),
            reserved_zero_040_054=reader.u4_tuple(6, "reserved_zero_040_054"),
            ai_template_params_058_130=reader.u4_tuple(55, "ai_template_params_058_130"),
            reserved_zero_134_20c=reader.u4_tuple(55, "reserved_zero_134_20c"),
            runtime_tail_words_210_278=reader.u4_tuple(27, "runtime_tail_words_210_278"),
            optional_entity_flag_27c=reader.u4("optional_entity_flag_27c"),
            optional_entity_flag_280=reader.u4("optional_entity_flag_280"),
            optional_entity_flag_284=reader.u4("optional_entity_flag_284"),
            optional_entity_flag_288=reader.u4("optional_entity_flag_288"),
            optional_entity_flag_28c=reader.u4("optional_entity_flag_28c"),
            reserved_zero_290=reader.u4("reserved_zero_290"),
            runtime_rare_flag_294=reader.u4("runtime_rare_flag_294"),
            runtime_budget_298=reader.u4("runtime_budget_298"),
            runtime_bitfield_29c=reader.u4("runtime_bitfield_29c"),
            runtime_mode_2a0=reader.u4("runtime_mode_2a0"),
            reserved_zero_2a4=reader.u4("reserved_zero_2a4"),
            reserved_zero_2a8=reader.u4("reserved_zero_2a8"),
            reserved_zero_2ac=reader.u4("reserved_zero_2ac"),
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class EntityPart1Payload:
    """对应 stg.ksy.types.entity_part1_payload。"""

    reserved_zero_00_20: tuple[int, ...]
    runtime_value_24: int
    runtime_ref_28: int
    runtime_float_or_state_2c: int
    runtime_force_or_ai_side_30: int | None

    @classmethod
    def from_bytes(cls, blob: bytes) -> "EntityPart1Payload":
        """按 entity_part1_payload.seq 解析。"""

        reader = _SeqReader(blob, "entity_part1_payload")
        model = cls(
            reserved_zero_00_20=reader.u4_tuple(9, "reserved_zero_00_20"),
            runtime_value_24=reader.u4("runtime_value_24"),
            runtime_ref_28=reader.u4("runtime_ref_28"),
            runtime_float_or_state_2c=reader.u4("runtime_float_or_state_2c"),
            runtime_force_or_ai_side_30=reader.u4("runtime_force_or_ai_side_30")
            if reader.remaining() >= 4
            else None,
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class EntityPart2Payload:
    """对应 stg.ksy.types.entity_part2_payload。"""

    entity_name: str
    person_id: int
    portrait_id: int
    static_owner_id: int
    static_location_id: int
    command: int
    soldier_type_id: int
    level: int
    troop_count: int
    martial_force: int
    intellect: int
    loyalty: int
    experience: int
    skill_fire_1: int
    skill_fire_2: int
    skill_fire_3: int
    skill_stone_1: int
    skill_stone_2: int
    skill_stone_3: int
    skill_thunder_1: int
    skill_thunder_2: int
    skill_thunder_3: int
    skill_slash_1: int
    skill_slash_2: int
    skill_slash_3: int
    skill_spear_1: int
    skill_spear_2: int
    skill_spear_3: int
    skill_arrow_1: int
    skill_arrow_2: int
    skill_arrow_3: int
    skill_persuade: int
    skill_inspire: int
    skill_shout: int
    skill_confuse: int
    special_skill: int
    action_state: int
    imprisoned_flag: int
    loaded_flag: int
    attribute: int
    self_ref: int
    alert_ai: int
    chase_ai: int
    retreat_ai: int
    action_policy: int
    ambush_field: int
    betrayal_force_id: int
    max_troop_count: int
    max_martial_force: int
    max_intellect: int
    reserved_d8: int
    reserved_dc: int

    @classmethod
    def from_bytes(cls, blob: bytes) -> "EntityPart2Payload":
        """按 entity_part2_payload.seq 解析。"""

        reader = _SeqReader(blob, "entity_part2_payload")
        model = cls(
            entity_name=reader.big5(20, "entity_name"),
            person_id=reader.s4("person_id"),
            portrait_id=reader.s4("portrait_id"),
            static_owner_id=reader.s4("static_owner_id"),
            static_location_id=reader.s4("static_location_id"),
            command=reader.s4("command"),
            soldier_type_id=reader.s4("soldier_type_id"),
            level=reader.s4("level"),
            troop_count=reader.s4("troop_count"),
            martial_force=reader.s4("martial_force"),
            intellect=reader.s4("intellect"),
            loyalty=reader.s4("loyalty"),
            experience=reader.s4("experience"),
            skill_fire_1=reader.s4("skill_fire_1"),
            skill_fire_2=reader.s4("skill_fire_2"),
            skill_fire_3=reader.s4("skill_fire_3"),
            skill_stone_1=reader.s4("skill_stone_1"),
            skill_stone_2=reader.s4("skill_stone_2"),
            skill_stone_3=reader.s4("skill_stone_3"),
            skill_thunder_1=reader.s4("skill_thunder_1"),
            skill_thunder_2=reader.s4("skill_thunder_2"),
            skill_thunder_3=reader.s4("skill_thunder_3"),
            skill_slash_1=reader.s4("skill_slash_1"),
            skill_slash_2=reader.s4("skill_slash_2"),
            skill_slash_3=reader.s4("skill_slash_3"),
            skill_spear_1=reader.s4("skill_spear_1"),
            skill_spear_2=reader.s4("skill_spear_2"),
            skill_spear_3=reader.s4("skill_spear_3"),
            skill_arrow_1=reader.s4("skill_arrow_1"),
            skill_arrow_2=reader.s4("skill_arrow_2"),
            skill_arrow_3=reader.s4("skill_arrow_3"),
            skill_persuade=reader.s4("skill_persuade"),
            skill_inspire=reader.s4("skill_inspire"),
            skill_shout=reader.s4("skill_shout"),
            skill_confuse=reader.s4("skill_confuse"),
            special_skill=reader.s4("special_skill"),
            action_state=reader.s4("action_state"),
            imprisoned_flag=reader.s4("imprisoned_flag"),
            loaded_flag=reader.s4("loaded_flag"),
            attribute=reader.s4("attribute"),
            self_ref=reader.s4("self_ref"),
            alert_ai=reader.s4("alert_ai"),
            chase_ai=reader.s4("chase_ai"),
            retreat_ai=reader.s4("retreat_ai"),
            action_policy=reader.s4("action_policy"),
            ambush_field=reader.s4("ambush_field"),
            betrayal_force_id=reader.s4("betrayal_force_id"),
            max_troop_count=reader.s4("max_troop_count"),
            max_martial_force=reader.s4("max_martial_force"),
            max_intellect=reader.s4("max_intellect"),
            reserved_d8=reader.s4("reserved_d8"),
            reserved_dc=reader.s4("reserved_dc"),
        )
        reader.finish()
        return model


@dataclass(frozen=True)
class RootPart1Block:
    """对应 stg.ksy.types.root_part1_block。"""

    size: int
    body: RootPart1Payload

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["RootPart1Block", int]:
        """读取 root_part1_block。"""

        size, payload, end_offset = _read_sized_block(blob, offset, "root_part1")
        return cls(size=size, body=RootPart1Payload.from_bytes(payload)), end_offset


@dataclass(frozen=True)
class RootPart2Block:
    """对应 stg.ksy.types.root_part2_block。"""

    size: int
    body: RootPart2Payload

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["RootPart2Block", int]:
        """读取 root_part2_block。"""

        size, payload, end_offset = _read_sized_block(blob, offset, "root_part2")
        return cls(size=size, body=RootPart2Payload.from_bytes(payload)), end_offset


@dataclass(frozen=True)
class ForcePart1Block:
    """对应 stg.ksy.types.force_part1_block。"""

    size: int
    body: ForcePart1Payload

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["ForcePart1Block", int]:
        """读取 force_part1_block。"""

        size, payload, end_offset = _read_sized_block(blob, offset, "force_part1")
        return cls(size=size, body=ForcePart1Payload.from_bytes(payload)), end_offset


@dataclass(frozen=True)
class ForcePart2Block:
    """对应 stg.ksy.types.force_part2_block。"""

    size: int
    body: ForcePart2Payload

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["ForcePart2Block", int]:
        """读取 force_part2_block。"""

        size, payload, end_offset = _read_sized_block(blob, offset, "force_part2")
        return cls(size=size, body=ForcePart2Payload.from_bytes(payload)), end_offset


@dataclass(frozen=True)
class SitePart1Block:
    """对应 stg.ksy.types.site_part1_block。"""

    size: int
    body: SitePart1Payload

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["SitePart1Block", int]:
        """读取 site_part1_block。"""

        size, payload, end_offset = _read_sized_block(blob, offset, "site_part1")
        return cls(size=size, body=SitePart1Payload.from_bytes(payload)), end_offset


@dataclass(frozen=True)
class SitePart2Block:
    """对应 stg.ksy.types.site_part2_block。"""

    size: int
    body: SitePart2Payload

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["SitePart2Block", int]:
        """读取 site_part2_block。"""

        size, payload, end_offset = _read_sized_block(blob, offset, "site_part2")
        return cls(size=size, body=SitePart2Payload.from_bytes(payload)), end_offset


@dataclass(frozen=True)
class EntityPart1Block:
    """对应 stg.ksy.types.entity_part1_block。"""

    size: int
    body: EntityPart1Payload

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["EntityPart1Block", int]:
        """读取 entity_part1_block。"""

        size, payload, end_offset = _read_sized_block(blob, offset, "entity_part1")
        return cls(size=size, body=EntityPart1Payload.from_bytes(payload)), end_offset


@dataclass(frozen=True)
class EntityPart2Block:
    """对应 stg.ksy.types.entity_part2_block。"""

    size: int
    body: EntityPart2Payload

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["EntityPart2Block", int]:
        """读取 entity_part2_block。"""

        size, payload, end_offset = _read_sized_block(blob, offset, "entity_part2")
        return cls(size=size, body=EntityPart2Payload.from_bytes(payload)), end_offset


@dataclass(frozen=True)
class Entity:
    """对应 stg.ksy.types.entity。"""

    part1: EntityPart1Block
    part2: EntityPart2Block

    @property
    def entity_name(self) -> str:
        """对应 instances.entity_name。"""

        return self.part2.body.entity_name

    @property
    def person_id(self) -> int:
        """对应 instances.person_id。"""

        return self.part2.body.person_id

    @property
    def troop_count(self) -> int:
        """对应 instances.troop_count。"""

        return self.part2.body.troop_count

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["Entity", int]:
        """读取 entity 对象。"""

        part1, next_offset = EntityPart1Block.read_from(blob, offset)
        part2, next_offset = EntityPart2Block.read_from(blob, next_offset)
        return cls(part1=part1, part2=part2), next_offset


@dataclass(frozen=True)
class Site:
    """对应 stg.ksy.types.site。"""

    part1: SitePart1Block
    part2: SitePart2Block
    primary_entity_count: int
    entities: tuple[Entity, ...]
    optional_entity_27c: Entity | None
    optional_entity_280: Entity | None
    optional_entity_284: Entity | None
    optional_entity_288: Entity | None
    optional_entity_28c: Entity | None

    @property
    def site_name(self) -> str:
        """对应 instances.site_name。"""

        return self.part1.body.site_name

    @property
    def city_index(self) -> int:
        """对应 instances.city_index。"""

        return self.part1.body.city_index

    @property
    def map_x(self) -> int:
        """对应 instances.map_x。"""

        return self.part1.body.coord_x

    @property
    def map_y(self) -> int:
        """对应 instances.map_y。"""

        return self.part1.body.coord_y

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["Site", int]:
        """读取 site 对象及其主实体、可选实体。"""

        part1, next_offset = SitePart1Block.read_from(blob, offset)
        part2, next_offset = SitePart2Block.read_from(blob, next_offset)
        primary_entity_count = _read_u4(blob, next_offset, "site.primary_entity_count")
        next_offset += 4
        entities: list[Entity] = []
        for _ in range(primary_entity_count):
            entity, next_offset = Entity.read_from(blob, next_offset)
            entities.append(entity)

        optional_entities: dict[str, Entity | None] = {
            "27c": None,
            "280": None,
            "284": None,
            "288": None,
            "28c": None,
        }
        for suffix, flag in (
            ("27c", part2.body.optional_entity_flag_27c),
            ("280", part2.body.optional_entity_flag_280),
            ("284", part2.body.optional_entity_flag_284),
            ("288", part2.body.optional_entity_flag_288),
            ("28c", part2.body.optional_entity_flag_28c),
        ):
            if flag != 0:
                optional_entity, next_offset = Entity.read_from(blob, next_offset)
                optional_entities[suffix] = optional_entity

        return (
            cls(
                part1=part1,
                part2=part2,
                primary_entity_count=primary_entity_count,
                entities=tuple(entities),
                optional_entity_27c=optional_entities["27c"],
                optional_entity_280=optional_entities["280"],
                optional_entity_284=optional_entities["284"],
                optional_entity_288=optional_entities["288"],
                optional_entity_28c=optional_entities["28c"],
            ),
            next_offset,
        )


@dataclass(frozen=True)
class Force:
    """对应 stg.ksy.types.force。"""

    part1: ForcePart1Block
    part2: ForcePart2Block
    site_list_pre_count_or_flag: int
    sites: tuple[Site, ...]

    @property
    def force_name(self) -> str:
        """对应 instances.force_name。"""

        return self.part1.body.force_name

    @property
    def site_count(self) -> int:
        """对应 instances.site_count。"""

        return self.part2.body.site_count

    @classmethod
    def read_from(cls, blob: bytes, offset: int) -> tuple["Force", int]:
        """读取 force 对象及其据点列表。"""

        part1, next_offset = ForcePart1Block.read_from(blob, offset)
        part2, next_offset = ForcePart2Block.read_from(blob, next_offset)
        site_list_pre_count_or_flag = _read_u4(
            blob,
            next_offset,
            "force.site_list_pre_count_or_flag",
        )
        next_offset += 4
        sites: list[Site] = []
        for _ in range(part2.body.site_count):
            site, next_offset = Site.read_from(blob, next_offset)
            sites.append(site)
        return (
            cls(
                part1=part1,
                part2=part2,
                site_list_pre_count_or_flag=site_list_pre_count_or_flag,
                sites=tuple(sites),
            ),
            next_offset,
        )


@dataclass(frozen=True)
class AfterForcesTail:
    """对应 stg.ksy.types.after_forces_tail。"""

    middle_tail_words: U4Words | None
    trailer_or_small_tail_words: U4Words

    @property
    def middle_tail_size(self) -> int:
        """对应 instances.middle_tail_size。"""

        return 0 if self.middle_tail_words is None else len(self.middle_tail_words.words) * 4

    @property
    def trailer_or_small_tail_size(self) -> int:
        """对应 instances.trailer_or_small_tail_size。"""

        return len(self.trailer_or_small_tail_words.words) * 4

    @classmethod
    def from_bytes(cls, blob: bytes) -> "AfterForcesTail":
        """按 after_forces_tail.seq 解析尾区。"""

        if len(blob) > 0xA0:
            middle = U4Words.from_bytes(blob[:-0xA0], "after_forces_tail.middle_tail_words")
            trailer = U4Words.from_bytes(blob[-0xA0:], "after_forces_tail.trailer_or_small_tail_words")
            return cls(middle_tail_words=middle, trailer_or_small_tail_words=trailer)
        return cls(
            middle_tail_words=None,
            trailer_or_small_tail_words=U4Words.from_bytes(
                blob,
                "after_forces_tail.trailer_or_small_tail_words",
            ),
        )


@dataclass(frozen=True)
class StgFile:
    """对应 stg.ksy 顶层结构。"""

    present_or_version: int
    root_part1: RootPart1Block
    root_part2: RootPart2Block
    force_count: int
    forces: tuple[Force, ...]
    after_forces_tail: AfterForcesTail

    @classmethod
    def from_bytes(cls, blob: bytes) -> "StgFile":
        """按 stg.ksy 解析整个 .stg 文件。"""

        present_or_version = _read_u4(blob, 0, "stg.present_or_version")
        root_part1, next_offset = RootPart1Block.read_from(blob, 4)
        root_part2, next_offset = RootPart2Block.read_from(blob, next_offset)
        force_count = _read_u4(blob, next_offset, "stg.force_count")
        next_offset += 4
        forces: list[Force] = []
        for _ in range(force_count):
            force, next_offset = Force.read_from(blob, next_offset)
            forces.append(force)
        after_forces_tail = AfterForcesTail.from_bytes(blob[next_offset:])
        return cls(
            present_or_version=present_or_version,
            root_part1=root_part1,
            root_part2=root_part2,
            force_count=force_count,
            forces=tuple(forces),
            after_forces_tail=after_forces_tail,
        )

    @classmethod
    def from_file(cls, path: Path) -> "StgFile":
        """从文件系统读取 .stg 文件。"""

        return cls.from_bytes(path.read_bytes())


__all__ = [
    "BIG5_ENCODING",
    "DOR_KSY_PATH",
    "DOR_MAGIC",
    "M_KSY_PATH",
    "M_MAGIC",
    "STG_KSY_PATH",
    "AfterForcesTail",
    "DorFile",
    "DorGroup",
    "DorRecord",
    "Entity",
    "EntityPart1Block",
    "EntityPart1Payload",
    "EntityPart2Block",
    "EntityPart2Payload",
    "Force",
    "ForcePart1Block",
    "ForcePart1Payload",
    "ForcePart2Block",
    "ForcePart2Payload",
    "MFile",
    "MMapCell",
    "RootPart1Block",
    "RootPart1Payload",
    "RootPart2Block",
    "RootPart2Payload",
    "Site",
    "SitePart1Block",
    "SitePart1Payload",
    "SitePart2Block",
    "SitePart2Payload",
    "StgFile",
    "U4Words",
]
