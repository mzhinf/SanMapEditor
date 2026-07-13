from __future__ import annotations

import argparse
import base64
import json
import shutil
import struct
import uuid
from collections import Counter
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from san_tools.analysis.analyze_dor import parse_dor
from san_tools.analysis.stage_site_links import build_stage_site_links
from san_tools.codecs import stage_ini_codec
from san_tools.codecs.stage_ini_excel_codec import write_workbook
from san_tools.codecs.stage_ini_txt_linkage import build_bundle as build_stage_ini_linkage_bundle
from san_tools.map.editor_model import StgFile
from san_tools.map.stg_editor_patch import build_stg_layout_index, build_stg_patch_index
from san_tools.project_paths import find_text_data_dir

try:
    from .extract_kingdom import DEFAULT_PALETTE_SOURCE, find_game_dir, load_palette
    from .render_m_cel_map import canvas_size, make_diamond_tile, make_object, parse_counted_cel, render_stage
except ImportError:
    from extract_kingdom import DEFAULT_PALETTE_SOURCE, find_game_dir, load_palette
    from render_m_cel_map import canvas_size, make_diamond_tile, make_object, parse_counted_cel, render_stage

try:
    from .palette import PAINT_RGB_PALETTE_HEX, SAN_RGB_PALETTE
except ImportError:
    try:
        from .palette import PAINT_RGB_FLAG_PALETTE as PAINT_RGB_PALETTE_HEX, SAN_RGB_PALETTE
    except ImportError:
        try:
            from palette import PAINT_RGB_PALETTE_HEX, SAN_RGB_PALETTE
        except ImportError:
            try:
                from palette import PAINT_RGB_FLAG_PALETTE as PAINT_RGB_PALETTE_HEX, SAN_RGB_PALETTE
            except ImportError:
                try:
                    from .palette import SAN_RGB_PALETTE
                except ImportError:
                    from palette import SAN_RGB_PALETTE
                PAINT_RGB_PALETTE_HEX = [f"#{red:02x}{green:02x}{blue:02x}" for red, green, blue in SAN_RGB_PALETTE[:256]]

try:
    from minimap_sidecar import ACTIVE_ROWS, GRID_SIZE, validate_sidecar_blob
except ImportError:
    from san_tools.map.minimap_sidecar import ACTIVE_ROWS, GRID_SIZE, validate_sidecar_blob

MAIN_HEADER_SIZE = stage_ini_codec.MAIN_HEADER_SIZE
EDITOR_BUILD_DATE_TOKEN = "__SAN_EDITOR_BUILD_DATE__"

FIELD_NAMES = [
    "acwx",
    "acwy",
    "acwz",
    "reserved0",
    "terrain_tag",
    "blocked",
    "site_trigger",
    "site_area",
    "reserved1",
    "minimap_color",
    "reserved2",
]

EDITABLE_LAYERS = ("acwx", "acwy", "acwz")
POINT_LAYER_FIELDS = ("terrain_tag", "blocked", "site_trigger", "site_area")
FIELD_META = [
    {"name": "acwx", "alias": "terrain_base", "label": "底层地表", "editable": True, "reserved": False},
    {"name": "acwy", "alias": "terrain_overlay", "label": "叠加地表", "editable": True, "reserved": False},
    {"name": "acwz", "alias": "object_overlay", "label": "物件层", "editable": True, "reserved": False},
    {"name": "reserved0", "alias": "", "label": "保留字段 0", "editable": False, "reserved": True},
    {"name": "terrain_tag", "alias": "", "label": "地形标记", "editable": True, "reserved": False},
    {"name": "blocked", "alias": "", "label": "阻挡标记", "editable": True, "reserved": False},
    {"name": "site_trigger", "alias": "", "label": "据点势力范围", "editable": True, "reserved": False},
    {"name": "site_area", "alias": "", "label": "据点核心区域", "editable": True, "reserved": False},
    {"name": "reserved1", "alias": "", "label": "保留字段 1", "editable": False, "reserved": True},
    {"name": "minimap_color", "alias": "", "label": "小地图颜色", "editable": True, "reserved": False, "sidecarSource": True},
    {"name": "reserved2", "alias": "", "label": "保留字段 2", "editable": False, "reserved": True},
]
EDITABLE_RECORD_FIELDS = [entry["name"] for entry in FIELD_META if entry.get("editable")]


def read_stage_records(stage_path: Path) -> tuple[int, int, list[list[int]]]:
    blob = stage_path.read_bytes()
    width, height = struct.unpack_from("<II", blob, 0)
    if blob[8:16] != b"Hello1.0":
        raise ValueError(f"not a stage .m file: {stage_path}")
    records: list[list[int]] = []
    for i in range(width * height):
        off = 16 + i * 16
        records.append([
            struct.unpack_from("<h", blob, off)[0],
            struct.unpack_from("<h", blob, off + 2)[0],
            struct.unpack_from("<h", blob, off + 4)[0],
            struct.unpack_from("<h", blob, off + 6)[0],
            blob[off + 8],
            blob[off + 9],
            blob[off + 10],
            blob[off + 11],
            blob[off + 12],
            blob[off + 13],
            struct.unpack_from("<H", blob, off + 14)[0],
        ])
    return width, height, records


def write_editor_template(template: Path, out_path: Path, build_date: str | None = None) -> None:
    """写入编辑器模板，并把打包日期占位符替换为当天日期。"""

    source = template.read_text(encoding="utf-8")
    if EDITOR_BUILD_DATE_TOKEN not in source:
        raise ValueError(f"编辑器模板缺少打包日期占位符：{template}")
    source = source.replace(EDITOR_BUILD_DATE_TOKEN, build_date or date.today().isoformat())
    out_path.write_text(source, encoding="utf-8")


def write_stage_json(
    out_path: Path,
    stage_name: str,
    width: int,
    height: int,
    records: list[list[int]],
    layout: str,
    origin: tuple[int, int],
    image_name: str,
    minimap_name: str,
    render_meta: dict,
    palette_source: str,
    sidecar_meta: dict,
    point_palette: list[str],
    minimap_palette: list[str],
    site_links: dict[str, object],
    scenario_files: dict[str, object],
    scenario_model: dict[str, object],
    common_model: dict[str, object],
) -> None:
    data = {
        "format": "san-editor-stage-v1",
        "stage": stage_name,
        "width": width,
        "height": height,
        "layout": layout,
        "origin": list(origin),
        "tile": {"width": 40, "height": 20, "row_step": 10, "odd_row_x": 20},
        "fields": FIELD_NAMES,
        "fieldMeta": FIELD_META,
        "editableLayers": EDITABLE_RECORD_FIELDS,
        "resourceLayers": list(EDITABLE_LAYERS),
        "pointLayers": list(POINT_LAYER_FIELDS),
        "editableRecordFields": EDITABLE_RECORD_FIELDS,
        "palette": palette_source,
        "pointPalette": point_palette,
        "minimapPalette": minimap_palette,
        "siteLinks": site_links,
        "scenarioFiles": scenario_files,
        "scenarioModel": scenario_model,
        "commonModel": common_model,
        "image": image_name,
        "minimap": {"image": minimap_name, "source": "rendered-map", "sync": "derived-from-m-records"},
        "sidecars": sidecar_meta,
        "resources": "resources.json",
        "records": records,
        "render": render_meta,
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def indexed_to_rgba(image: Image.Image, alpha_mask: Image.Image | None = None) -> Image.Image:
    rgba = image.convert("RGBA")
    if alpha_mask is None:
        alpha_mask = image.point(lambda value: 255 if value else 0).convert("L")
    rgba.putalpha(alpha_mask)
    return rgba


def fit_thumbnail(image: Image.Image, box_size: int) -> Image.Image:
    thumb = Image.new("RGBA", (box_size, box_size), (0, 0, 0, 0))
    work = image.copy()
    work.thumbnail((box_size - 8, box_size - 16), Image.Resampling.NEAREST)
    x = (box_size - work.width) // 2
    y = max(2, (box_size - work.height) // 2 - 4)
    thumb.alpha_composite(work, (x, y))
    return thumb


def build_resource_image(layer: str, entry: dict, palette: list[int]) -> tuple[Image.Image, dict]:
    if layer in ("acwx", "acwy"):
        tile, diamond_mask = make_diamond_tile(entry["pixels"], palette)
        alpha = diamond_mask if layer == "acwx" else None
        image = indexed_to_rgba(tile, alpha)
        meta = {"width": 40, "height": 20}
        return image, meta
    obj = make_object(entry, palette)
    image = indexed_to_rgba(obj)
    meta = {
        "width": entry["width"],
        "height": entry["height"],
        "xAnchor": entry["x_anchor"],
        "yAnchor": entry["y_anchor"],
    }
    return image, meta


def pack_fixed_atlas(items: list[tuple[int, Image.Image, dict]], cell_size: tuple[int, int]) -> tuple[Image.Image, dict[int, list[int]]]:
    cell_w, cell_h = cell_size
    cols = 32
    rows = max(1, (len(items) + cols - 1) // cols)
    atlas = Image.new("RGBA", (cols * cell_w, rows * cell_h), (0, 0, 0, 0))
    rects: dict[int, list[int]] = {}
    for n, (index, image, _meta) in enumerate(items):
        x = (n % cols) * cell_w
        y = (n // cols) * cell_h
        atlas.alpha_composite(image, (x, y))
        rects[index] = [x, y, image.width, image.height]
    return atlas, rects


def pack_shelf_atlas(items: list[tuple[int, Image.Image, dict]], max_width: int = 4096, pad: int = 1) -> tuple[Image.Image, dict[int, list[int]]]:
    shelves: list[tuple[int, int, list[tuple[int, int, Image.Image]]]] = []
    x = 0
    y = 0
    shelf_h = 0
    current: list[tuple[int, int, Image.Image]] = []
    rects: dict[int, list[int]] = {}
    for index, image, _meta in items:
        w, h = image.size
        if x and x + w > max_width:
            shelves.append((y, shelf_h, current))
            y += shelf_h + pad
            x = 0
            shelf_h = 0
            current = []
        current.append((x, index, image))
        rects[index] = [x, y, w, h]
        x += w + pad
        shelf_h = max(shelf_h, h)
    if current:
        shelves.append((y, shelf_h, current))
    height = max(1, y + shelf_h)
    atlas = Image.new("RGBA", (max_width, height), (0, 0, 0, 0))
    for shelf_y, _shelf_h, shelf_items in shelves:
        for item_x, _index, image in shelf_items:
            atlas.alpha_composite(image, (item_x, shelf_y))
    used_width = max((rect[0] + rect[2] for rect in rects.values()), default=1)
    return atlas.crop((0, 0, used_width, height)), rects


def layer_usage(records: list[list[int]], layer: str) -> dict[int, int]:
    field = FIELD_NAMES.index(layer)
    usage: dict[int, int] = {}
    for record in records:
        value = record[field]
        if value >= 0:
            usage[value] = usage.get(value, 0) + 1
    return usage


def export_resource_catalog(blocks: dict, palette: list[int], stage_dir: Path, records: list[list[int]]) -> dict:
    catalog = {"format": "san-editor-resources-v2", "layers": {}}
    usage_by_layer = {layer: layer_usage(records, layer) for layer in EDITABLE_LAYERS}
    for layer in EDITABLE_LAYERS:
        box = 56 if layer != "acwz" else 72
        cols = 16 if layer != "acwz" else 12
        entries = []
        sprites: list[tuple[int, Image.Image, dict]] = []
        draw_items: list[tuple[int, Image.Image, dict]] = []
        usage = usage_by_layer[layer]
        for index, entry in enumerate(blocks[layer]["entries"]):
            if entry is None:
                continue
            image, meta = build_resource_image(layer, entry, palette)
            meta["used"] = usage.get(index, 0)
            sprites.append((index, fit_thumbnail(image, box), meta.copy()))
            draw_items.append((index, image, meta.copy()))
        sprites.sort(key=lambda item: item[0])
        draw_items.sort(key=lambda item: item[0])
        if layer in ("acwx", "acwy"):
            draw_atlas, draw_rects = pack_fixed_atlas(draw_items, (40, 20))
        else:
            draw_atlas, draw_rects = pack_shelf_atlas(draw_items)
        draw_image_name = f"draw_{layer}.png"
        draw_atlas.save(stage_dir / draw_image_name)
        rows = max(1, (len(sprites) + cols - 1) // cols)
        atlas = Image.new("RGBA", (cols * box, rows * box), (0, 0, 0, 0))
        draw = ImageDraw.Draw(atlas)
        for n, (index, thumb, meta) in enumerate(sprites):
            x = (n % cols) * box
            y = (n // cols) * box
            atlas.alpha_composite(thumb, (x, y))
            draw.text((x + 3, y + box - 12), str(index), fill=(255, 255, 255, 230), stroke_width=1, stroke_fill=(0, 0, 0, 220))
            entries.append({"index": index, "atlas": [x, y, box, box], "draw": draw_rects[index], **meta})
        image_name = f"resources_{layer}.png"
        atlas.save(stage_dir / image_name)
        catalog["layers"][layer] = {"image": image_name, "drawImage": draw_image_name, "tileSize": box, "columns": cols, "entries": entries}
    (stage_dir / "resources.json").write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return catalog




def _optional_site_entities(site) -> list[tuple[str, object]]:
    """按 stg.ksy 中的可选 Entity flag 顺序收集附加实体。"""

    return [
        ("optional_entity_27c", site.optional_entity_27c),
        ("optional_entity_280", site.optional_entity_280),
        ("optional_entity_284", site.optional_entity_284),
        ("optional_entity_288", site.optional_entity_288),
        ("optional_entity_28c", site.optional_entity_28c),
    ]


def _entity_to_editor_row(entity, entity_key: str, entity_index: int, entity_group: str, site_key: str, site, force_key: str, force_index: int, force, patch_fields: dict[str, object], stg_layout: dict[str, object]) -> dict[str, object]:
    """把 stg.ksy 的 Entity 字段压缩成编辑器需要的字段级行。"""

    body = entity.part2.body
    return {
        "entityKey": entity_key,
        "entityIndex": entity_index,
        "entityGroup": entity_group,
        "entity_name": body.entity_name,
        "person_id": body.person_id,
        "portrait_id": body.portrait_id,
        "static_owner_id": body.static_owner_id,
        "static_location_id": body.static_location_id,
        "command": body.command,
        "soldier_type_id": body.soldier_type_id,
        "level": body.level,
        "troop_count": body.troop_count,
        "martial_force": body.martial_force,
        "intellect": body.intellect,
        "loyalty": body.loyalty,
        "patchFields": patch_fields,
        "stgLayout": stg_layout,
        "parentSiteKey": site_key,
        "parent_site_name": site.site_name,
        "parentForceKey": force_key,
        "parent_force_index": force_index,
        "parent_force_name": force.force_name,
        "actual_force_index": force_index,
        "actual_force_name": force.force_name,
    }


def build_big5_char_map(strings: list[str]) -> dict[str, list[int]]:
    """为浏览器端 .stg 名称回写准备 Big5 字符表。"""

    char_map = {chr(value): [value] for value in range(0x20, 0x7F)}
    for text in strings:
        for char in text:
            if not char or char in char_map:
                continue
            try:
                char_map[char] = list(char.encode("big5"))
            except UnicodeEncodeError:
                continue
    return char_map


def build_editor_scenario_model(game_dir: Path, stage_name: str) -> dict[str, object]:
    """从 .stg 对象流导出势力、据点和武将的嵌套归属模型。"""

    source = game_dir / f"{stage_name}.stg"
    if not source.exists():
        return {"available": False, "source": "stg", "reason": f"缺少 {source.name}", "forces": [], "sites": [], "entities": []}
    try:
        blob = source.read_bytes()
        stg = StgFile.from_bytes(blob)
        patch_index = build_stg_patch_index(blob)
        layout_index = build_stg_layout_index(blob)
    except ValueError as exc:
        return {"available": False, "source": "stg", "reason": f"无法解析 {source.name}: {exc}", "forces": [], "sites": [], "entities": []}

    forces: list[dict[str, object]] = []
    sites: list[dict[str, object]] = []
    entities: list[dict[str, object]] = []
    for force_index, force in enumerate(stg.forces):
        force_key = f"force:{force_index}"
        force_site_keys: list[str] = []
        for site_index, site in enumerate(force.sites):
            site_key = f"{force_key}/site:{site_index}"
            force_site_keys.append(site_key)
            entity_keys: list[str] = []
            for entity_index, entity in enumerate(site.entities):
                entity_key = f"{site_key}/entity:{entity_index}"
                entity_keys.append(entity_key)
                entities.append(_entity_to_editor_row(entity, entity_key, entity_index, "primary", site_key, site, force_key, force_index, force, patch_index.get(entity_key, {}), layout_index["entities"].get(entity_key, {})))
            for entity_group, entity in _optional_site_entities(site):
                if entity is None:
                    continue
                entity_index = len(entity_keys)
                entity_key = f"{site_key}/{entity_group}"
                entity_keys.append(entity_key)
                entities.append(_entity_to_editor_row(entity, entity_key, entity_index, entity_group, site_key, site, force_key, force_index, force, patch_index.get(entity_key, {}), layout_index["entities"].get(entity_key, {})))
            site_body = site.part1.body
            sites.append({
                "siteKey": site_key,
                "siteIndex": site_index,
                "site_name": site_body.site_name,
                "city_index": site_body.city_index,
                "house_attr": site_body.house_attr,
                "castle_scale": site_body.castle_scale,
                "population": site_body.population,
                "gold": site_body.gold,
                "food": site_body.food,
                "standby_soldier": site_body.standby_soldier,
                "develop": site_body.develop,
                "commerce": site_body.commerce,
                "security": site_body.security,
                "coord_x": site_body.coord_x,
                "coord_y": site_body.coord_y,
                "governor": site_body.governor,
                "site_serial_010": site.part2.body.site_serial_010,
                "primary_entity_count": site.primary_entity_count,
                "entityKeys": entity_keys,
                "patchFields": patch_index.get(site_key, {}),
                "stgLayout": layout_index["sites"].get(site_key, {}),
                "parentForceKey": force_key,
                "parent_force_index": force_index,
                "parent_force_name": force.force_name,
            })
        forces.append({
            "forceKey": force_key,
            "forceIndex": force_index,
            "force_name": force.part1.body.force_name,
            "force_slot_or_index_14": force.part1.body.force_slot_or_index_14,
            "force_lord_person_id": force.part1.body.force_lord_person_id,
            "force_index_1based": force.part2.body.force_index_1based,
            "site_count": force.site_count,
            "siteKeys": force_site_keys,
            "patchFields": patch_index.get(force_key, {}),
            "stgLayout": layout_index["forces"].get(force_key, {}),
        })
    scenario_strings = [force["force_name"] for force in forces] + [site["site_name"] for site in sites] + [entity["entity_name"] for entity in entities]
    return {
        "available": True,
        "source": "stg",
        "path": source.name,
        "force_count": stg.force_count,
        "scenario_title": stg.root_part1.body.scenario_title,
        "scenario_year_start": stg.root_part1.body.scenario_year_start,
        "scenario_year_end": stg.root_part1.body.scenario_year_end,
        "big5CharMap": build_big5_char_map(scenario_strings),
        "stgLayout": layout_index["layout"],
        "forces": forces,
        "sites": sites,
        "entities": entities,
    }


def _pick_master_rows(rows: list[dict[str, object]], fields: tuple[str, ...], limit: int = 512) -> list[dict[str, object]]:
    """从 stage.ini 母表行中挑选前端索引需要的稳定字段。"""

    return [{field: row.get(field, "") for field in fields} for row in rows[:limit]]


def _read_cp950_tsv_table(path: Path) -> dict[str, object]:
    """读取 Big5/CP950 制表文本，并保留原始表头顺序以支持浏览器端回写。"""

    if not path.exists():
        return {"available": False, "headers": [], "rawHeaders": [], "rows": [], "reason": f"缺少 {path.name}"}
    text = path.read_text(encoding="cp950", errors="replace")
    lines = [line.rstrip("\r") for line in text.split("\n") if line.strip()]
    if not lines:
        return {"available": False, "headers": [], "rawHeaders": [], "rows": [], "reason": f"{path.name} 为空"}
    raw_headers = [item for item in lines[0].split("\t")]
    headers = [item.strip() or f"col_{index}" for index, item in enumerate(raw_headers)]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cells = [item.strip() for item in line.split("\t")]
        if not cells or not cells[0]:
            continue
        row = {headers[index] if index < len(headers) else f"col_{index}": value for index, value in enumerate(cells)}
        rows.append(row)
    return {"available": True, "headers": headers, "rawHeaders": raw_headers, "rows": rows}


def _read_cp950_tsv(path: Path) -> list[dict[str, str]]:
    """读取游戏目录中的 Big5/CP950 制表文本，供编辑器索引使用。"""

    table = _read_cp950_tsv_table(path)
    return list(table.get("rows", []))


def _to_int(value: object, default: int = 0) -> int:
    """把文本字段安全转为整数；空值或异常值按默认值处理。"""

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def build_history_general_rows(game_dir: Path, general_master: list[dict[str, object]]) -> list[dict[str, object]]:
    """合并 History.txt 与 general.txt，导出未登场武将的只读候选列表。"""

    history_rows = _read_cp950_tsv(game_dir / "History.txt")
    general_rows = _read_cp950_tsv(game_dir / "general.txt")
    master_by_name = {str(row.get("name", "")).strip(): row for row in general_master if row.get("name")}
    master_by_id = {str(row.get("record_id_candidate", "")).strip(): row for row in general_master if str(row.get("record_id_candidate", "")).strip()}
    general_by_name = {row.get("姓名", "").strip(): row for row in general_rows if row.get("姓名")}
    general_by_id = {row.get("人物編號", "").strip(): row for row in general_rows if row.get("人物編號")}
    result: list[dict[str, object]] = []
    seen: set[int] = set()
    for history in history_rows:
        name = history.get("武將名", "").strip()
        person_id = _to_int(history.get("編號"), 0)
        general = general_by_id.get(str(person_id)) or general_by_name.get(name) or {}
        master = master_by_id.get(str(person_id)) or master_by_name.get(name) or {}
        command = _to_int(general.get("統御力"), 0)
        if command <= 0 or person_id in seen:
            continue
        seen.add(person_id)
        result.append({
            "source": "History.txt",
            "name": name or str(general.get("姓名", "")) or str(master.get("name", "")),
            "person_id": person_id,
            "portrait_id": _to_int(general.get("頭像編號"), _to_int(master.get("record_index"), person_id)),
            "command": command,
            "soldier_type_id": _to_int(general.get("兵種號"), 0),
            "troop_count": _to_int(general.get("帶兵數"), 0),
            "martial_force": _to_int(general.get("武力"), 0),
            "intellect": _to_int(general.get("智力"), 0),
            "history_force_id": _to_int(history.get("屬國"), 0),
            "join_year": _to_int(history.get("加入年"), 0),
            "join_month": _to_int(history.get("加入月"), 0),
            "join_day": _to_int(history.get("加入日"), 0),
            "stage_ini_record_index": master.get("record_index", ""),
        })
    return result


def build_history_table_model(game_dir: Path) -> dict[str, object]:
    """导出 History.txt 的原始列模型，供前端按 history 数据源编辑加入时间等字段。"""

    table = _read_cp950_tsv_table(game_dir / "History.txt")
    if not table.get("available"):
        return table
    rows = []
    for index, row in enumerate(table.get("rows", [])):
        values = dict(row)
        row_key = str(values.get("編號", values.get("编号", ""))).strip() or str(index + 1)
        values["rowKey"] = row_key
        rows.append(values)
    return {
        "available": True,
        "source": "History.txt",
        "path": "History.txt",
        "headers": table.get("headers", []),
        "rawHeaders": table.get("rawHeaders", []),
        "rows": rows,
    }


def build_editor_common_model(root: Path) -> dict[str, object]:
    """导出 stage.ini 中可作为全局武将、技能、城池和兵种索引的轻量母表。"""

    try:
        payload = stage_ini_codec.build_payload(root)
    except (FileNotFoundError, ValueError) as exc:
        return {"available": False, "source": "stage.ini", "reason": str(exc), "generals": [], "skills": [], "cities": [], "soldiers": []}

    tables = payload.get("tables", {})
    tail_records = tables.get("tail_records", [])
    skill_names = {"說服", "鼓舞", "大喝", "迷惑", "怒殺技"}
    skill_candidates = [
        row for row in tail_records
        if row.get("name") and (150 <= int(row.get("record_index", -1)) <= 173 or "技" in str(row.get("name")) or row.get("name") in skill_names)
    ]
    game_dir = find_game_dir(root)
    general_master = tables.get("general_master", [])
    history_generals = build_history_general_rows(game_dir, general_master)
    history_table = build_history_table_model(game_dir)
    common_strings = [str(row.get("name", "")) for rows in (general_master, skill_candidates, tables.get("city_master", []), tables.get("troop_master", [])) for row in rows]
    common_strings.extend(str(row.get("name", "")) for row in history_generals)
    common_strings.extend(str(header) for header in history_table.get("rawHeaders", []))
    common_strings.extend(str(value) for row in history_table.get("rows", []) for value in row.values())
    return {
        "available": True,
        "source": "stage.ini",
        "path": Path(str(payload.get("stage_ini_path", "stage.ini"))).name,
        "big5CharMap": build_big5_char_map(common_strings),
        "generals": _pick_master_rows(general_master, ("record_index", "record_id_candidate", "name", "label", "family_guess")),
        "historyGenerals": history_generals,
        "historyTable": history_table,
        "skills": _pick_master_rows(skill_candidates, ("record_index", "name", "label", "family_guess")),
        "cities": _pick_master_rows(tables.get("city_master", []), ("record_index", "name", "label", "place_id_candidate_stage_ini", "family_guess")),
        "soldiers": _pick_master_rows(tables.get("troop_master", []), ("record_index", "name", "label", "family_guess")),
    }


def _palette_to_flat_rgb(palette: list[int]) -> list[int]:
    """把渲染调色板转换为 Pillow P 图像可使用的 768 项 RGB 列表。"""

    flat: list[int] = []
    for item in palette[:256]:
        if isinstance(item, int):
            flat.extend(((item >> 16) & 0xFF, (item >> 8) & 0xFF, item & 0xFF))
        else:
            red, green, blue = item
            flat.extend((int(red), int(green), int(blue)))
    flat.extend([0] * (768 - len(flat)))
    return flat[:768]


def export_heads_atlas(game_dir: Path, stage_dir: Path, palette: list[int]) -> dict[str, object]:
    """从 heads.dat 导出武将头像图集，供编辑器按 portrait_id 切片显示。"""

    source = game_dir / "heads.dat"
    if not source.exists():
        return {"available": False, "reason": "缺少 heads.dat"}
    blob = source.read_bytes()
    if len(blob) < 8:
        return {"available": False, "reason": "heads.dat 长度不足"}
    first_offset = int.from_bytes(blob[:4], "little")
    if first_offset <= 0 or first_offset % 4 != 0 or first_offset > len(blob):
        return {"available": False, "reason": "heads.dat 偏移表无效"}
    raw_offsets = [int.from_bytes(blob[index:index + 4], "little") for index in range(0, first_offset, 4)]
    offsets = [offset for offset in raw_offsets if first_offset <= offset < len(blob)]
    if not offsets:
        return {"available": False, "reason": "heads.dat 未找到头像偏移"}
    offsets = sorted(dict.fromkeys(offsets))
    first_width = int.from_bytes(blob[offsets[0]:offsets[0] + 2], "little")
    first_height = int.from_bytes(blob[offsets[0] + 2:offsets[0] + 4], "little")
    if first_width <= 0 or first_height <= 0:
        return {"available": False, "reason": "heads.dat 头像尺寸无效"}
    columns = 16
    rows = (len(offsets) + columns - 1) // columns
    atlas = Image.new("P", (columns * first_width, rows * first_height), 0)
    atlas.putpalette(_palette_to_flat_rgb(palette))
    count = 0
    for index, offset in enumerate(offsets):
        if offset + 4 > len(blob):
            continue
        width = int.from_bytes(blob[offset:offset + 2], "little")
        height = int.from_bytes(blob[offset + 2:offset + 4], "little")
        size = width * height
        start = offset + 4
        end = start + size
        if width != first_width or height != first_height or end > len(blob):
            continue
        image = Image.frombytes("P", (width, height), blob[start:end])
        image.putpalette(atlas.getpalette())
        atlas.paste(image, ((index % columns) * first_width, (index // columns) * first_height))
        count += 1
    out_name = "heads.png"
    atlas.convert("RGBA").save(stage_dir / out_name)
    return {
        "available": count > 0,
        "source": "heads.dat",
        "path": "heads.dat",
        "image": out_name,
        "count": count,
        "width": first_width,
        "height": first_height,
        "columns": columns,
    }



STAGE_INI_FIELD_MAP = {
    "site": {
        "row_key": "city_index",
        "sheet": "castle",
        "fields": {
            "city_index": "\u90fd\u5e02\u7d22\u5f15",
            "house_attr": "\u623f\u5b50\u5c6c\u6027",
            "castle_scale": "\u57ce\u898f\u6a21",
            "population": "\u4eba\u53e3",
            "gold": "\u91d1",
            "food": "\u7ce7",
            "standby_soldier": "\u5f85\u547d\u58eb\u5175",
            "develop": "\u958b\u767c\u503c",
            "commerce": "\u5546\u696d\u503c",
            "security": "\u6cbb\u5b89\u503c",
            "coord_x": "\u5ea7\u6a19X",
            "coord_y": "\u5ea7\u6a19Y",
            "governor": "\u592a\u5b88",
        },
    },
    "entity": {
        "row_key": "person_id",
        "sheet": "general",
        "fields": {
            "person_id": "\u4eba\u7269\u7de8\u865f",
            "portrait_id": "\u982d\u50cf\u7de8\u865f",
            "static_owner_id": "\u6240\u5c6c\u541b\u4e3b",
            "static_location_id": "\u6240\u5728\u5730",
            "command": "\u7d71\u5fa1\u529b",
            "soldier_type_id": "\u5175\u7a2e\u865f",
            "level": "\u7b49\u7d1a",
            "troop_count": "\u5e36\u5175\u6578",
            "martial_force": "\u6b66\u529b",
            "intellect": "\u667a\u529b",
            "loyalty": "\u5fe0\u8aa0\u503c",
        },
    },
}


def _stage_ini_append_layout(
    bundle: dict[str, object],
    payload: dict[str, object],
    sheet_name: str,
) -> dict[str, object]:
    """根据已确认的连续数值流反推出新增母表逻辑行的布局。"""

    model = bundle["conversion_models"].get(sheet_name, {})
    row_models = sorted(model.get("row_models", {}).values(), key=lambda row: int(row["stream_start_dword"]))
    if len(row_models) < 2:
        raise ValueError(f"{sheet_name} 母表缺少足够的连续行，无法计算新增布局")
    starts = [int(row["stream_start_dword"]) for row in row_models]
    step_counts = Counter(b - a for a, b in zip(starts, starts[1:]) if b > a)
    row_dwords = step_counts.most_common(1)[0][0]
    numeric_counts = Counter(int(row["numeric_count"]) for row in row_models)
    numeric_count = numeric_counts.most_common(1)[0][0]
    title_bytes = (row_dwords - numeric_count) * 4
    if title_bytes <= 0:
        raise ValueError(f"{sheet_name} 母表标题槽长度无效：{title_bytes}")
    last = row_models[-1]
    section = str(last["stream_section"])
    section_base = MAIN_HEADER_SIZE if section == "main" else int(payload["header"]["tail_offset"])
    insert_offset = section_base + (int(last["stream_start_dword"]) + int(last["numeric_count"])) * 4
    return {
        "sheet": sheet_name,
        "section": section,
        "insertOffset": insert_offset,
        "rowBytes": row_dwords * 4,
        "titleBytes": title_bytes,
        "numericCount": numeric_count,
        "numericHeaders": list(model.get("value_headers", []))[:numeric_count],
    }


def build_stage_ini_patch_model(root: Path, game_dir: Path) -> dict[str, object]:
    """\u4e3a\u6d4f\u89c8\u5668\u4fdd\u5b58 stage.ini \u51c6\u5907 dword \u7ea7\u5b57\u6bb5\u6620\u5c04\u4e0e\u5de5\u4f5c\u7c3f\u57fa\u51c6\u884c\u3002"""

    stage_ini = game_dir / "stage.ini"
    try:
        txt_dir = find_text_data_dir(root)
    except FileNotFoundError as exc:
        return {"available": False, "reason": str(exc)}
    if not stage_ini.exists():
        return {"available": False, "reason": f"缺少 {stage_ini}"}
    try:
        tmp_parent = root / "derived" / "test_tmp" / "stage_ini_patch_model_runs"
        tmp_parent.mkdir(parents=True, exist_ok=True)
        tmp_root = tmp_parent / f"stage_ini_patch_model_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=False, exist_ok=False)
        shutil.copyfile(stage_ini, tmp_root / "stage.ini")
        shutil.copytree(txt_dir, tmp_root / "data" / "text", dirs_exist_ok=True)
        bundle = build_stage_ini_linkage_bundle(tmp_root)
        shutil.rmtree(tmp_root, ignore_errors=True)
    except (FileNotFoundError, ValueError, OSError) as exc:
        return {"available": False, "reason": str(exc)}

    payload = stage_ini_codec.build_payload(game_dir)
    header = payload["header"]
    section_base = {"main": MAIN_HEADER_SIZE, "tail": int(header["tail_offset"])}
    field_locations: dict[str, dict[str, dict[str, dict[str, int]]]] = {"general": {}, "castle": {}}
    for sheet_name in ("general", "castle"):
        model = bundle["conversion_models"].get(sheet_name, {})
        headers = list(model.get("value_headers", []))
        for row_id, row_model in model.get("row_models", {}).items():
            section = str(row_model["stream_section"])
            base = section_base[section]
            start_dword = int(row_model["stream_start_dword"])
            row_locations: dict[str, dict[str, int]] = {}
            for index, header_name in enumerate(headers[: int(row_model["numeric_count"])]):
                row_locations[str(header_name)] = {"byteOffset": base + (start_dword + index) * 4, "size": 4}
            field_locations[sheet_name][str(row_id)] = row_locations

    workbook_sheets = []
    for sheet in bundle["conversion_workbook_sheets"]:
        if sheet["name"] in {"general", "castle"}:
            workbook_sheets.append({"name": sheet["name"], "headers": sheet["headers"], "rows": sheet["rows"]})
    return {
        "available": True,
        "source": "stage.ini + data/text",
        "fileSize": int(header["file_size"]),
        "fieldMap": STAGE_INI_FIELD_MAP,
        "fieldLocations": field_locations,
        "appendLayout": {
            "mainCount": int(header["main_count"]),
            "mainStride": int(header["main_stride"]),
            "tailOffset": int(header["tail_offset"]),
            "tailStride": int(header["tail_stride"]),
            "general": _stage_ini_append_layout(bundle, payload, "general"),
            "castle": _stage_ini_append_layout(bundle, payload, "castle"),
        },
        "workbookSheets": workbook_sheets,
    }

def _xlsx_cell_value(value: object) -> object:
    """把 stage.ini 解析值规整为 xlsx 可直接写入的单元格值。"""

    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        return ""
    return value


def _stage_ini_sheet(name: str, rows: list[dict[str, object]], preferred: tuple[str, ...] = ()) -> dict[str, object]:
    """按稳定字段顺序生成一个 stage.ini 工作簿页。"""

    headers: list[str] = []
    for field in preferred:
        if field not in headers:
            headers.append(field)
    for row in rows:
        for field in row:
            if field not in headers:
                headers.append(field)
    if not headers:
        headers = ["说明"]
        values = [["无数据"]]
    else:
        values = [[_xlsx_cell_value(row.get(field, "")) for field in headers] for row in rows]
    return {"name": name, "headers": headers, "rows": values}


def build_stage_ini_workbook_sheets(game_dir: Path) -> list[dict[str, object]]:
    """把 stage.ini 字段级解析结果导出为编辑器随包工作簿。"""

    payload = stage_ini_codec.build_payload(game_dir)
    tables = payload.get("tables", {})
    header = payload.get("header", {})
    summary_rows = [[key, _xlsx_cell_value(value)] for key, value in header.items()]
    summary_rows.insert(0, ["stage_ini_path", payload.get("stage_ini_path", "stage.ini")])
    return [
        {"name": "stage_ini_info", "headers": ["字段", "值"], "rows": summary_rows},
        _stage_ini_sheet("general_master", tables.get("general_master", []), ("record_index", "record_id_candidate", "name", "label", "family_guess")),
        _stage_ini_sheet("city_master", tables.get("city_master", []), ("record_index", "place_id_candidate_stage_ini", "name", "label", "family_guess")),
        _stage_ini_sheet("troop_master", tables.get("troop_master", []), ("record_index", "record_id_candidate", "name", "label", "family_guess")),
        _stage_ini_sheet("main_records", tables.get("main_records", []), ("record_index", "name", "raw_hex", "u16_words")),
        _stage_ini_sheet("tail_records", tables.get("tail_records", []), ("record_index", "name", "raw_hex", "u16_words")),
    ]

def copy_scenario_reference_files(game_dir: Path, stage_dir: Path, stage_name: str) -> dict[str, object]:
    """复制编辑器导出时需要原样保留的剧本侧参考文件。"""

    references: dict[str, object] = {}
    for key, source_name, out_name in (
        ("dor", f"{stage_name}.dor", f"{stage_name}.dor"),
        ("stg", f"{stage_name}.stg", f"{stage_name}.stg"),
        ("heads", "heads.dat", "heads.dat"),
        ("history", "History.txt", "History.txt"),
    ):
        source = game_dir / source_name
        if not source.exists():
            references[key] = {"available": False, "reason": f"缺少 {source_name}"}
            continue
        shutil.copyfile(source, stage_dir / out_name)
        references[key] = {"available": True, "path": out_name, "bytes": source.stat().st_size}
    stage_ini = game_dir / "stage.ini"
    if stage_ini.exists():
        shutil.copyfile(stage_ini, stage_dir / "stage.ini")
        references["stageIni"] = {"available": True, "path": "stage.ini", "bytes": stage_ini.stat().st_size}
        try:
            workbook_path = stage_dir / "stage_ini.xlsx"
            write_workbook(workbook_path, build_stage_ini_workbook_sheets(game_dir))
            references["stageIniWorkbook"] = {"available": True, "path": workbook_path.name, "bytes": workbook_path.stat().st_size}
        except (FileNotFoundError, ValueError, OSError) as exc:
            references["stageIniWorkbook"] = {"available": False, "reason": str(exc)}
    else:
        references["stageIni"] = {"available": False, "reason": "缺少 stage.ini"}
        references["stageIniWorkbook"] = {"available": False, "reason": "缺少 stage.ini"}
    return references

def export_minimap(map_path: Path, out_path: Path, max_width: int = 280) -> None:
    image = Image.open(map_path).convert("RGB")
    scale = max_width / image.width
    size = (max_width, max(1, round(image.height * scale)))
    image.resize(size, Image.Resampling.BILINEAR).save(out_path)


def build_sidecar_export_meta(
    game_dir: Path,
    stage_name: str,
    grid_size: int = GRID_SIZE,
    active_rows: int = ACTIVE_ROWS,
) -> dict:
    """为编辑页导出 `.s/.x` 准备参考尾区。"""

    cut = grid_size * active_rows
    tails: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    for suffix in ("s", "x"):
        reference_path = game_dir / f"{stage_name}.{suffix}"
        if not reference_path.exists():
            missing.append(suffix)
            continue
        blob = reference_path.read_bytes()
        validate_sidecar_blob(blob, grid_size)
        tail = blob[cut:]
        tails[suffix] = {
            "reference": str(reference_path),
            "tailBase64": base64.b64encode(tail).decode("ascii"),
            "tailBytes": len(tail),
        }
    available = len(tails) == 2 and not missing
    meta = {
        "available": available,
        "gridSize": grid_size,
        "activeRows": active_rows,
        "tailRows": grid_size - active_rows,
        "referenceStem": stage_name,
        "tails": tails,
    }
    if not available:
        missing_text = ", ".join(f".{suffix}" for suffix in missing) if missing else "参考尾区"
        meta["reason"] = f"当前关卡缺少完整的 {missing_text} 参考文件，编辑页导出 `.s/.x` 时会对尾区使用 0 填充。"
    return meta


def resolve_editor_template(root: Path) -> Path:
    """只使用源码目录内的编辑器模板，避免继续依赖 tools 包装层。"""

    candidate = Path(__file__).with_name("editor_app.html")
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"找不到编辑器模板：{candidate}")



def build_dor_stg_site_links(root: Path, stage: str, reason: str = "") -> dict[str, object]:
    """在辅助文本缺失时，仅依据 .dor 城门和 .stg 据点坐标建立归属。"""

    game_dir = find_game_dir(root)
    dor_path = game_dir / f"{stage}.dor"
    stg_path = game_dir / f"{stage}.stg"
    if not dor_path.exists() or not stg_path.exists():
        missing = dor_path.name if not dor_path.exists() else stg_path.name
        raise FileNotFoundError(missing)
    stg = StgFile.from_bytes(stg_path.read_bytes())
    cities: list[dict[str, object]] = []
    city_by_coord: dict[str, dict[str, object]] = {}
    for force_index, force in enumerate(stg.forces):
        for site_index, site in enumerate(force.sites):
            body = site.part1.body
            site_key = f"force:{force_index}/site:{site_index}"
            city = {
                "siteKey": site_key,
                "cityName": body.site_name,
                "forceIndex": force_index,
                "forceName": force.force_name,
                "cityIndex": body.city_index,
                "sourceRecordIndex": site_index,
                "mapX": body.coord_x,
                "mapY": body.coord_y,
                "expectedX": body.coord_x,
                "expectedY": body.coord_y,
                "gateIndices": [],
                "gateCount": 0,
            }
            cities.append(city)
            city_by_coord[f"{body.coord_x},{body.coord_y}"] = city

    gates: list[dict[str, object]] = []
    for group in parse_dor(dor_path):
        group_index = int(group["group"])
        for door in group["doors"]:
            coord_key = f"{int(door['site_x'])},{int(door['site_y'])}"
            city = city_by_coord.get(coord_key)
            gate = {
                "gateIndex": len(gates),
                "group": group_index,
                "doorIndex": int(door["index"]),
                "doorX": int(door["door_x"]),
                "doorY": int(door["door_y"]),
                "dir": int(door["dir"]),
                "siteX": int(door["site_x"]),
                "siteY": int(door["site_y"]),
                "siteKey": city["siteKey"] if city else coord_key,
                "cityName": city["cityName"] if city else "",
            }
            gates.append(gate)
            if city is not None:
                city["gateIndices"].append(gate["gateIndex"])
    matched_gate_count = 0
    for city in cities:
        city["gateCount"] = len(city["gateIndices"])
        matched_gate_count += city["gateCount"]
    return {
        "available": bool(cities) and bool(gates),
        "stage": stage,
        "reason": reason,
        "cityCount": len(cities),
        "gateCount": len(gates),
        "matchedGateCount": matched_gate_count,
        "unmatchedGateCount": len(gates) - matched_gate_count,
        "cities": cities,
        "gates": gates,
        "sources": {"dor": str(dor_path), "stg": str(stg_path), "mode": "dor-stg-fallback"},
    }
def build_editor_site_links(root: Path, stage: str) -> dict[str, object]:
    """生成据点/城门联动信息，优先使用完整分析，失败时回退到 .dor/.stg。"""

    try:
        payload = build_stage_site_links(root, stage)
        if payload.get("available"):
            return payload
        return build_dor_stg_site_links(root, stage, str(payload.get("reason", "")))
    except (FileNotFoundError, ValueError) as exc:
        try:
            return build_dor_stg_site_links(root, stage, f"完整据点分析不可用：{exc}")
        except (FileNotFoundError, ValueError) as fallback_exc:
            return {
                "available": False,
                "reason": f"无法生成据点/城门联动：{fallback_exc}",
                "cityCount": 0,
                "gateCount": 0,
                "matchedGateCount": 0,
                "unmatchedGateCount": 0,
                "cities": [],
                "gates": [],
                "sources": {},
            }
def write_editor_index(out_dir: Path, stages: list[dict]) -> None:
    options = "\n".join(
        f'<option value="{entry["path"]}">{entry["stage"]} ({entry["width"]}x{entry["height"]})</option>'
        for entry in stages
    )
    html = (
        '<!doctype html>\n<html lang="zh-CN">\n<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>San 地图编辑器索引</title>'
        '<style>body{font-family:Segoe UI,Arial,sans-serif;margin:32px;background:#f4f2ec;color:#202124}'
        'main{max-width:720px}select,button{height:32px;font:inherit}select{min-width:260px}a{color:#0f766e}</style></head>'
        '<body><main><h1>San 地图编辑器</h1><p>选择已经导出的关卡编辑页。</p>'
        f'<select id="stage">{options}</select> <button id="open">打开</button>'
        '<p><a href="index.json">index.json</a></p></main>'
        "<script>document.getElementById('open').onclick=()=>{const v=document.getElementById('stage').value;if(v) location.href=v;};</script>"
        '</body></html>\n'
    )
    (out_dir / "index.html").write_text(html, encoding="utf-8")


def export_editor_bundle(root: Path, stage: str, out_dir: Path, layout: str, layers: str, palette_source: str) -> dict:
    game_dir = find_game_dir(root)
    stage_path = game_dir / f"{stage}.m"
    if not stage_path.exists():
        raise FileNotFoundError(stage_path)

    width, height, records = read_stage_records(stage_path)
    source_w, source_h, ox, oy = canvas_size(width, height, layout)
    stage_dir = out_dir / stage
    stage_dir.mkdir(parents=True, exist_ok=True)

    palette = load_palette(game_dir, palette_source)
    blocks = parse_counted_cel(game_dir / "kingdom.cel")
    map_path = stage_dir / "map.png"
    render_meta = render_stage(stage_path, blocks, palette, map_path, layout, layers, None)
    render_meta["source_output_size"] = [source_w, source_h]
    sidecar_meta = build_sidecar_export_meta(game_dir, stage, GRID_SIZE, ACTIVE_ROWS)
    site_links = build_editor_site_links(root, stage)
    scenario_files = copy_scenario_reference_files(game_dir, stage_dir, stage)
    scenario_model = build_editor_scenario_model(game_dir, stage)
    common_model = build_editor_common_model(root)
    common_model["heads"] = export_heads_atlas(game_dir, stage_dir, SAN_RGB_PALETTE)
    common_model["stageIniPatchModel"] = build_stage_ini_patch_model(root, game_dir)

    export_resource_catalog(blocks, palette, stage_dir, records)
    export_minimap(map_path, stage_dir / "minimap.png")
    write_stage_json(
        stage_dir / "stage.json",
        stage,
        width,
        height,
        records,
        layout,
        (ox, oy),
        "map.png",
        "minimap.png",
        render_meta,
        palette_source,
        sidecar_meta,
        PAINT_RGB_PALETTE_HEX,
        [f"#{red:02x}{green:02x}{blue:02x}" for red, green, blue in SAN_RGB_PALETTE[:256]],
        site_links,
        scenario_files,
        scenario_model,
        common_model,
    )
    template = resolve_editor_template(root)
    write_editor_template(template, stage_dir / "editor.html")

    index_path = out_dir / "index.json"
    existing = {"stages": []}
    if index_path.exists():
        existing = json.loads(index_path.read_text(encoding="utf-8"))
    stages = {entry["stage"]: entry for entry in existing.get("stages", [])}
    stages[stage] = {"stage": stage, "path": f"{stage}/editor.html", "width": width, "height": height}
    existing["stages"] = sorted(stages.values(), key=lambda item: item["stage"])
    index_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    write_editor_index(out_dir, existing["stages"])

    return {"stage": stage, "width": width, "height": height, "out": str(stage_dir), "records": len(records)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--stage", default="stage11")
    parser.add_argument("--all", action="store_true", help="Export editor bundles for every stage*.m file")
    parser.add_argument("--out", default="derived/editor", type=Path)
    parser.add_argument("--layout", choices=["stagger"], default="stagger")
    parser.add_argument("--layers", default="xyz")
    parser.add_argument("--palette", default=DEFAULT_PALETTE_SOURCE)
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    if args.all:
        game_dir = find_game_dir(root)
        results = []
        for stage_path in sorted(game_dir.glob("stage*.m")):
            results.append(export_editor_bundle(root, stage_path.stem, out_dir, args.layout, args.layers, args.palette))
        print(json.dumps({"count": len(results), "stages": results}, ensure_ascii=False))
    else:
        result = export_editor_bundle(root, args.stage, out_dir, args.layout, args.layers, args.palette)
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
