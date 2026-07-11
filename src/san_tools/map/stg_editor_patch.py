from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

BIG5_ENCODING = "big5"


@dataclass(frozen=True)
class PatchField:
    """描述一个可从编辑器回写到 .stg 的字段位置。"""

    offset: int
    type: str
    size: int | None = None
    encoding: str | None = None

    def to_json(self) -> dict[str, object]:
        """转换成前端可直接使用的 JSON 字段描述。"""

        data: dict[str, object] = {"offset": self.offset, "type": self.type}
        if self.size is not None:
            data["size"] = self.size
        if self.encoding is not None:
            data["encoding"] = self.encoding
        return data


def _read_u4(blob: bytes | bytearray, offset: int, label: str) -> int:
    """读取 little-endian u32，并在越界时给出可定位错误。"""

    if offset < 0 or offset + 4 > len(blob):
        raise ValueError(f"{label} 越界：offset={offset:#x} total={len(blob)}")
    return int(struct.unpack_from("<I", blob, offset)[0])


def _read_sized_payload(blob: bytes | bytearray, offset: int, label: str) -> tuple[int, int, int]:
    """读取 stg.ksy 中常见的 u32 size + payload 块。"""

    size = _read_u4(blob, offset, f"{label}.size")
    payload_offset = offset + 4
    end_offset = payload_offset + size
    if end_offset > len(blob):
        raise ValueError(f"{label}.body 越界：offset={payload_offset:#x} size={size} total={len(blob)}")
    return payload_offset, size, end_offset


def force_patch_fields(force_part1_payload: int) -> dict[str, PatchField]:
    """返回 force_part1_payload 内已确认可回写字段。"""

    return {
        "force_name": PatchField(force_part1_payload + 0x00, "str", 20, BIG5_ENCODING),
        "force_lord_person_id": PatchField(force_part1_payload + 0x18, "u4"),
    }


def site_patch_fields(site_part1_payload: int) -> dict[str, PatchField]:
    """返回 site_part1_payload 内已确认可回写字段。"""

    return {
        "site_name": PatchField(site_part1_payload + 0x00, "str", 20, BIG5_ENCODING),
        "city_index": PatchField(site_part1_payload + 0x14, "s4"),
        "house_attr": PatchField(site_part1_payload + 0x18, "s4"),
        "castle_scale": PatchField(site_part1_payload + 0x1C, "s4"),
        "population": PatchField(site_part1_payload + 0x20, "s4"),
        "gold": PatchField(site_part1_payload + 0x24, "s4"),
        "food": PatchField(site_part1_payload + 0x28, "s4"),
        "standby_soldier": PatchField(site_part1_payload + 0x2C, "s4"),
        "develop": PatchField(site_part1_payload + 0x30, "s4"),
        "commerce": PatchField(site_part1_payload + 0x34, "s4"),
        "security": PatchField(site_part1_payload + 0x38, "s4"),
        "coord_x": PatchField(site_part1_payload + 0x48, "s4"),
        "coord_y": PatchField(site_part1_payload + 0x4C, "s4"),
        "governor": PatchField(site_part1_payload + 0x50, "s4"),
    }


def entity_patch_fields(entity_part2_payload: int) -> dict[str, PatchField]:
    """返回 entity_part2_payload 内已确认可回写字段。"""

    fields = {
        "entity_name": PatchField(entity_part2_payload + 0x00, "str", 20, BIG5_ENCODING),
        "person_id": PatchField(entity_part2_payload + 0x14, "s4"),
        "portrait_id": PatchField(entity_part2_payload + 0x18, "s4"),
        "static_owner_id": PatchField(entity_part2_payload + 0x1C, "s4"),
        "static_location_id": PatchField(entity_part2_payload + 0x20, "s4"),
        "command": PatchField(entity_part2_payload + 0x24, "s4"),
        "soldier_type_id": PatchField(entity_part2_payload + 0x28, "s4"),
        "level": PatchField(entity_part2_payload + 0x2C, "s4"),
        "troop_count": PatchField(entity_part2_payload + 0x30, "s4"),
        "martial_force": PatchField(entity_part2_payload + 0x34, "s4"),
        "intellect": PatchField(entity_part2_payload + 0x38, "s4"),
        "loyalty": PatchField(entity_part2_payload + 0x3C, "s4"),
        "experience": PatchField(entity_part2_payload + 0x40, "s4"),
    }
    skill_names = [
        "skill_fire_1", "skill_fire_2", "skill_fire_3",
        "skill_stone_1", "skill_stone_2", "skill_stone_3",
        "skill_thunder_1", "skill_thunder_2", "skill_thunder_3",
        "skill_slash_1", "skill_slash_2", "skill_slash_3",
        "skill_spear_1", "skill_spear_2", "skill_spear_3",
        "skill_arrow_1", "skill_arrow_2", "skill_arrow_3",
        "skill_persuade", "skill_inspire", "skill_shout", "skill_confuse",
        "special_skill",
    ]
    for index, name in enumerate(skill_names):
        fields[name] = PatchField(entity_part2_payload + 0x44 + index * 4, "s4")
    for index, name in enumerate((
        "action_state", "imprisoned_flag", "loaded_flag", "attribute", "self_ref",
        "alert_ai", "chase_ai", "retreat_ai", "action_policy", "ambush_field",
        "betrayal_force_id", "max_troop_count", "max_martial_force", "max_intellect",
    )):
        fields[name] = PatchField(entity_part2_payload + 0xA0 + index * 4, "s4")
    return fields


def build_stg_patch_index(blob: bytes) -> dict[str, dict[str, dict[str, object]]]:
    """顺序扫描 .stg，生成编辑器对象键到字段偏移的映射。"""

    offset = 4
    _root1_payload, _root1_size, offset = _read_sized_payload(blob, offset, "root_part1")
    _root2_payload, _root2_size, offset = _read_sized_payload(blob, offset, "root_part2")
    force_count = _read_u4(blob, offset, "stg.force_count")
    offset += 4
    index: dict[str, dict[str, dict[str, object]]] = {}

    for force_index in range(force_count):
        force_key = f"force:{force_index}"
        force_part1_payload, _force_part1_size, offset = _read_sized_payload(blob, offset, f"forces[{force_index}].part1")
        index[force_key] = {name: field.to_json() for name, field in force_patch_fields(force_part1_payload).items()}
        force_part2_payload, _force_part2_size, offset = _read_sized_payload(blob, offset, f"forces[{force_index}].part2")
        site_count = _read_u4(blob, force_part2_payload, f"forces[{force_index}].part2.site_count")
        offset += 4
        for site_index in range(site_count):
            site_key = f"{force_key}/site:{site_index}"
            site_part1_payload, _site_part1_size, offset = _read_sized_payload(blob, offset, f"{site_key}.part1")
            index[site_key] = {name: field.to_json() for name, field in site_patch_fields(site_part1_payload).items()}
            site_part2_payload, _site_part2_size, offset = _read_sized_payload(blob, offset, f"{site_key}.part2")
            primary_entity_count = _read_u4(blob, offset, f"{site_key}.primary_entity_count")
            offset += 4
            for entity_index in range(primary_entity_count):
                entity_key, offset = _scan_entity_patch_index(blob, offset, f"{site_key}/entity:{entity_index}", index)
                if not entity_key:
                    raise ValueError(f"无法扫描 {site_key}/entity:{entity_index}")
            for suffix, flag_offset in (
                ("optional_entity_27c", 0x27C),
                ("optional_entity_280", 0x280),
                ("optional_entity_284", 0x284),
                ("optional_entity_288", 0x288),
                ("optional_entity_28c", 0x28C),
            ):
                if _read_u4(blob, site_part2_payload + flag_offset, f"{site_key}.{suffix}_flag") != 0:
                    _entity_key, offset = _scan_entity_patch_index(blob, offset, f"{site_key}/{suffix}", index)
    return index


def _scan_entity_patch_index(
    blob: bytes,
    offset: int,
    entity_key: str,
    index: dict[str, dict[str, dict[str, object]]],
) -> tuple[str, int]:
    """扫描一个 Entity，并记录 entity_part2_payload 可回写字段。"""

    _entity_part1_payload, _entity_part1_size, offset = _read_sized_payload(blob, offset, f"{entity_key}.part1")
    entity_part2_payload, _entity_part2_size, offset = _read_sized_payload(blob, offset, f"{entity_key}.part2")
    index[entity_key] = {name: field.to_json() for name, field in entity_patch_fields(entity_part2_payload).items()}
    return entity_key, offset


def build_stg_layout_index(blob: bytes) -> dict[str, object]:
    """顺序扫描 .stg，记录可重建对象流所需的 span 与 count 偏移。"""

    offset = 4
    _root1_payload, _root1_size, offset = _read_sized_payload(blob, offset, "root_part1")
    root2_payload, _root2_size, offset = _read_sized_payload(blob, offset, "root_part2")
    force_count_offset = offset
    force_count = _read_u4(blob, offset, "stg.force_count")
    offset += 4
    forces_start = offset
    forces: dict[str, dict[str, object]] = {}
    sites: dict[str, dict[str, object]] = {}
    entities: dict[str, dict[str, object]] = {}

    for force_index in range(force_count):
        force_key = f"force:{force_index}"
        force_start = offset
        _force_part1_payload, _force_part1_size, offset = _read_sized_payload(blob, offset, f"{force_key}.part1")
        force_part2_payload, _force_part2_size, offset = _read_sized_payload(blob, offset, f"{force_key}.part2")
        site_count_offset = force_part2_payload
        site_count = _read_u4(blob, site_count_offset, f"{force_key}.site_count")
        site_list_pre_count_offset = offset
        offset += 4
        force_header_end = offset
        site_keys: list[str] = []
        for site_index in range(site_count):
            site_key = f"{force_key}/site:{site_index}"
            site_keys.append(site_key)
            site_start = offset
            site_part1_payload, site_part1_size, offset = _read_sized_payload(blob, offset, f"{site_key}.part1")
            site_part2_payload, _site_part2_size, offset = _read_sized_payload(blob, offset, f"{site_key}.part2")
            primary_entity_count_offset = offset
            primary_entity_count = _read_u4(blob, offset, f"{site_key}.primary_entity_count")
            offset += 4
            site_header_end = offset
            entity_keys: list[str] = []
            for entity_index in range(primary_entity_count):
                entity_key = f"{site_key}/entity:{entity_index}"
                entity_layout, offset = _scan_entity_layout(blob, offset, entity_key, "primary")
                entities[entity_key] = entity_layout
                entity_keys.append(entity_key)
            optional_entity_flag_offsets = {
                "optional_entity_27c": site_part2_payload + 0x27C,
                "optional_entity_280": site_part2_payload + 0x280,
                "optional_entity_284": site_part2_payload + 0x284,
                "optional_entity_288": site_part2_payload + 0x288,
                "optional_entity_28c": site_part2_payload + 0x28C,
            }
            for suffix, flag_offset in optional_entity_flag_offsets.items():
                if _read_u4(blob, flag_offset, f"{site_key}.{suffix}_flag") != 0:
                    entity_key = f"{site_key}/{suffix}"
                    entity_layout, offset = _scan_entity_layout(blob, offset, entity_key, suffix)
                    entities[entity_key] = entity_layout
                    entity_keys.append(entity_key)
            sites[site_key] = {
                "span": [site_start, offset],
                "headerSpan": [site_start, site_header_end],
                "sitePart1PayloadOffset": site_part1_payload,
                "sitePart1PayloadSize": site_part1_size,
                "sitePart2PayloadOffset": site_part2_payload,
                "primaryEntityCountOffset": primary_entity_count_offset,
                "optionalEntityFlagOffsets": optional_entity_flag_offsets,
                "entityKeys": entity_keys,
            }
        forces[force_key] = {
            "span": [force_start, offset],
            "headerSpan": [force_start, force_header_end],
            "siteCountOffset": site_count_offset,
            "siteListPreCountOffset": site_list_pre_count_offset,
            "siteKeys": site_keys,
        }
    return {
        "layout": {
            "prefixSpan": [0, forces_start],
            "tailSpan": [offset, len(blob)],
            "forceCountOffset": force_count_offset,
            "root2ForceCountOffset": root2_payload + 0x14,
        },
        "forces": forces,
        "sites": sites,
        "entities": entities,
    }


def _scan_entity_layout(blob: bytes, offset: int, entity_key: str, kind: str) -> tuple[dict[str, object], int]:
    """扫描一个 Entity，并保留按 KSY 重建运行字段所需的块偏移。"""

    entity_start = offset
    part1_payload, part1_size, offset = _read_sized_payload(blob, offset, f"{entity_key}.part1")
    part2_payload, part2_size, offset = _read_sized_payload(blob, offset, f"{entity_key}.part2")
    return {
        "span": [entity_start, offset],
        "kind": kind,
        "entityPart1PayloadOffset": part1_payload,
        "entityPart1PayloadSize": part1_size,
        "entityPart2PayloadOffset": part2_payload,
        "entityPart2PayloadSize": part2_size,
    }, offset


def encode_big5_fixed(text: str, size: int) -> bytes:
    """把编辑后的文本编码为 Big5 定长零填充字段。"""

    raw = text.encode(BIG5_ENCODING)
    if len(raw) > size:
        raise ValueError(f"Big5 字段过长：{text!r} 需要 {len(raw)} 字节，最多 {size} 字节")
    return raw + b"\x00" * (size - len(raw))


def _write_field(output: bytearray, field: dict[str, object], value: Any) -> None:
    """按字段类型把值写回 bytearray。"""

    offset = int(field["offset"])
    field_type = str(field["type"])
    if field_type == "str":
        size = int(field.get("size", 0))
        output[offset : offset + size] = encode_big5_fixed(str(value), size)
        return
    if field_type == "s4":
        struct.pack_into("<i", output, offset, int(value))
        return
    if field_type == "u4":
        struct.pack_into("<I", output, offset, int(value))
        return
    raise ValueError(f"不支持的 .stg 字段类型：{field_type}")


def apply_stg_scenario_changes(blob: bytes, changes: list[dict[str, object]]) -> bytes:
    """把编辑器 scenarioChanges 中可定点回写的 update 操作应用到 .stg。"""

    index = build_stg_patch_index(blob)
    output = bytearray(blob)
    for change in changes:
        if change.get("op") != "update":
            continue
        key = str(change.get("key", ""))
        field_name = str(change.get("field", ""))
        field = index.get(key, {}).get(field_name)
        if field is None:
            continue
        _write_field(output, field, change.get("after"))
    return bytes(output)


__all__ = [
    "PatchField",
    "apply_stg_scenario_changes",
    "build_stg_layout_index",
    "build_stg_patch_index",
    "encode_big5_fixed",
]
