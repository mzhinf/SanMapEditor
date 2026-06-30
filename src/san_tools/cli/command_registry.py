from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandEntry:
    """描述一个可通过统一入口调用的命令。"""

    name: str
    module: str
    summary: str


COMMANDS: tuple[CommandEntry, ...] = (
    CommandEntry("render-map", "san_tools.map.render_m_cel_map", "渲染 stageNN.m + kingdom.cel/.atr 地图图像"),
    CommandEntry("export-editor-bundle", "san_tools.map.export_editor_bundle", "导出浏览器地图编辑器 bundle"),
    CommandEntry("apply-editor-patch", "san_tools.map.apply_editor_patch", "把编辑器 patch 安全写回复制后的 .m 文件"),
    CommandEntry("export-map-previews", "san_tools.map.export_map_previews", "批量导出地图预览图"),
    CommandEntry("extract-kingdom", "san_tools.map.extract_kingdom", "解包 kingdom.cel/.atr 资源"),
    CommandEntry("stitch-kingdom", "san_tools.map.stitch_kingdom_tiles", "拼接 kingdom tile 样张"),
    CommandEntry("analyze-sidecars", "san_tools.analysis.analyze_stage_sidecars", "分析 .stg/.evt/.spr/.dor/.s/.x sidecar"),
    CommandEntry("export-sidecar-tables", "san_tools.pipelines.export_stage_sidecar_tables", "导出 sidecar 分析表"),
    CommandEntry("export-stage-ini-json", "san_tools.pipelines.export_stage_ini_tables", "导出 stage.ini 结构化 JSON"),
    CommandEntry("export-stage-ini-txt-tables", "san_tools.pipelines.export_stage_ini_txt_tables", "导出 stage.ini 文本关联 JSON"),
    CommandEntry("build-stage-ini", "san_tools.pipelines.build_stage_ini", "根据 JSON 回写 stage.ini"),
    CommandEntry("export-stage-ini-workbook", "san_tools.pipelines.export_stage_ini_txt_workbook", "导出 stage.ini Excel 工作簿"),
    CommandEntry("import-stage-ini-workbook", "san_tools.pipelines.import_stage_ini_txt_workbook", "把 stage.ini Excel 工作簿读回 JSON"),
    CommandEntry("build-stage-ini-from-workbook", "san_tools.pipelines.build_stage_ini_from_txt_workbook", "根据 stage.ini Excel 工作簿回写二进制"),
    CommandEntry("export-stg-raw-chain", "san_tools.pipelines.export_stg_raw_chain", "导出 .stg 原始记录链"),
    CommandEntry("export-stg-hierarchy", "san_tools.pipelines.export_stg_hierarchy", "导出 .stg 势力/城池层级"),
    CommandEntry("export-stg-city-troop", "san_tools.pipelines.export_stg_city_troop_analysis", "导出 .stg 城池状态与士兵候选表"),
    CommandEntry("export-stg-workbook", "san_tools.pipelines.export_stg_workbook", "导出 .stg Excel 工作簿"),
    CommandEntry("import-stg-workbook", "san_tools.pipelines.import_stg_workbook", "根据 .stg Excel 工作簿回写二进制"),
    CommandEntry("export-stg-phase7", "san_tools.pipelines.export_stg_phase7_links", "导出旧版 .stg 字段候选对照表"),
    CommandEntry("convert-game-texts", "san_tools.text.convert_game_texts", "批量把游戏文本转换成 UTF-8 对照目录"),
)


def command_map() -> dict[str, CommandEntry]:
    """按命令名返回注册表，便于统一入口查找。"""

    return {entry.name: entry for entry in COMMANDS}
