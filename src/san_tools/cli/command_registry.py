from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandEntry:
    """描述一个可通过统一入口调用的命令。"""

    name: str
    module: str
    summary: str


COMMANDS: tuple[CommandEntry, ...] = (
    CommandEntry('render-map', 'san_tools.map.render_m_cel_map', '渲染 stageNN.m + kingdom.cel/.atr 地图图像'),
    CommandEntry('export-editor-bundle', 'san_tools.map.export_editor_bundle', '导出浏览器地图编辑器 bundle'),
    CommandEntry('apply-editor-patch', 'san_tools.map.apply_editor_patch', '把编辑器 patch 安全写回复制后的 .m 文件'),
    CommandEntry('build-minimap-sidecars', 'san_tools.map.build_minimap_sidecars', '根据 .m 重建 .s/.x 的有效区并保留尾区'),
    CommandEntry('export-map-previews', 'san_tools.map.export_map_previews', '批量导出地图预览图'),
    CommandEntry('extract-kingdom', 'san_tools.map.extract_kingdom', '解包 kingdom.cel/.atr 资源'),
    CommandEntry('stitch-kingdom', 'san_tools.map.stitch_kingdom_tiles', '拼接 kingdom tile 样张'),
    CommandEntry('export-m-layers', 'san_tools.map.export_m_layers', '批量导出 .m 三层索引图与附加字段图'),
    CommandEntry('build-editor-release', 'san_tools.map.build_editor_release', '构建地图编辑器 Windows 发布包'),
    CommandEntry('launch-editor', 'san_tools.map.editor_desktop_launcher', '启动已生成的桌面编辑器数据'),
    CommandEntry('analyze-assets', 'san_tools.analysis.analyze_assets', '分析游戏目录中的 EXE、资源和文件分布'),
    CommandEntry('analyze-sidecars', 'san_tools.analysis.analyze_stage_sidecars', '分析 .stg/.evt/.spr/.dor/.s/.x sidecar'),
    CommandEntry('analyze-stg-family-alignment', 'san_tools.analysis.analyze_stg_family_alignment', '分析旧版 .stg 记录家族对齐关系'),
    CommandEntry('analyze-evt-resources', 'san_tools.analysis.analyze_evt_resources', '分析 .evt 与 TalkNN.txt / stageNN.txt 的关联'),
    CommandEntry('analyze-dor', 'san_tools.analysis.analyze_dor', '解析 .dor 的分组、城门坐标与据点坐标'),
    CommandEntry('analyze-stage-site-links', 'san_tools.analysis.stage_site_links', '根据 .dor/.stg 坐标建立城门与据点归属表'),
    CommandEntry('analyze-stg-field-values', 'san_tools.analysis.analyze_stg_field_values', '统计 .stg 各字段取值与不确定字段值'),
    CommandEntry('analyze-m-byte-fields', 'san_tools.analysis.analyze_m_byte_fields', '分析 .m 原始 +0x08..+0x0F 与地图的关系'),
    CommandEntry('analyze-minimap-sidecars', 'san_tools.analysis.analyze_minimap_sidecars', '分析 .s/.x 与地图缩略缓存的关系'),
    CommandEntry('analyze-minimap-color-relation', 'san_tools.analysis.analyze_minimap_color_relation', '统计 minimap_color 与 acwx/acwy/acwz 的关系'),
    CommandEntry('export-sidecar-tables', 'san_tools.pipelines.export_stage_sidecar_tables', '导出 sidecar 分析表'),
    CommandEntry('export-stage-ini-json', 'san_tools.pipelines.export_stage_ini_tables', '导出 stage.ini 结构化 JSON'),
    CommandEntry('export-stage-ini-txt-tables', 'san_tools.pipelines.export_stage_ini_txt_tables', '导出 stage.ini 文本关联 JSON'),
    CommandEntry('build-stage-ini', 'san_tools.pipelines.build_stage_ini', '根据 JSON 回写 stage.ini'),
    CommandEntry('export-stage-ini-workbook', 'san_tools.pipelines.export_stage_ini_txt_workbook', '导出 stage.ini Excel 工作簿'),
    CommandEntry('import-stage-ini-workbook', 'san_tools.pipelines.import_stage_ini_txt_workbook', '把 stage.ini Excel 工作簿读回 JSON'),
    CommandEntry('build-stage-ini-from-workbook', 'san_tools.pipelines.build_stage_ini_from_txt_workbook', '根据 stage.ini Excel 工作簿回写二进制'),
    CommandEntry('export-stg-raw-chain', 'san_tools.pipelines.export_stg_raw_chain', '导出 .stg 原始记录链'),
    CommandEntry('export-stg-hierarchy', 'san_tools.pipelines.export_stg_hierarchy', '导出 .stg 势力/城市层级'),
    CommandEntry('export-stg-city-troop', 'san_tools.pipelines.export_stg_city_troop_analysis', '导出 .stg 城池状态与士兵候选表'),
    CommandEntry('export-stg-workbook', 'san_tools.pipelines.export_stg_workbook', '导出 .stg Excel 工作簿'),
    CommandEntry('roundtrip-stg-json', 'san_tools.pipelines.roundtrip_stg_json', '执行 .stg -> json -> .stg，并可移除保留字段'),
    CommandEntry('import-stg-workbook', 'san_tools.pipelines.import_stg_workbook', '根据 .stg Excel 工作簿回写二进制'),
    CommandEntry('export-stg-phase7', 'san_tools.pipelines.export_stg_phase7_links', '导出旧版 .stg 字段候选对照表'),
    CommandEntry('convert-game-texts', 'san_tools.text.convert_game_texts', '批量把游戏文本转换成 UTF-8 对照目录'),
    CommandEntry('encode-convert', 'san_tools.text.encode_convert', '按目录执行 Big5 与 UTF-8 双向转换'),
)


def command_map() -> dict[str, CommandEntry]:
    """按命令名返回注册表，便于统一入口查找。"""

    return {entry.name: entry for entry in COMMANDS}


