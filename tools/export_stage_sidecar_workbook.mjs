import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

function parseArgs(argv) {
  const args = {
    inputJson: "derived/sidecar_analysis/stage_sidecar_tables.json",
    output: "derived/sidecar_analysis/stg_evt_analysis.xlsx",
    previewDir: "derived/sidecar_analysis/previews",
  };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--input-json") {
      args.inputJson = argv[index + 1];
      index += 1;
    } else if (token === "--output") {
      args.output = argv[index + 1];
      index += 1;
    } else if (token === "--preview-dir") {
      args.previewDir = argv[index + 1];
      index += 1;
    }
  }
  return args;
}

function normalizeCell(value) {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "number" || typeof value === "boolean" || value instanceof Date) {
    return value;
  }
  if (Array.isArray(value) || typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function guessColumnWidth(key) {
  if (/^w\d{2}$/.test(key)) {
    return 9;
  }
  if (key === "stage") {
    return 12;
  }
  if (key === "suffix") {
    return 8;
  }
  if (key.endsWith("_offset") || key.includes("index") || key.includes("count") || key.includes("width") || key.includes("height")) {
    return 12;
  }
  if (key.includes("ascii") || key.includes("tokens")) {
    return 22;
  }
  if (key.includes("layout") || key.includes("texts") || key.includes("stages") || key.includes("columns")) {
    return 28;
  }
  if (key.includes("text") || key.includes("title") || key.includes("nonzero")) {
    return 24;
  }
  if (key.includes("xref")) {
    return 30;
  }
  return 14;
}

function applySheetStyle(sheet, rowCount, columns) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);

  const headerRange = sheet.getRangeByIndexes(0, 0, 1, columns.length);
  headerRange.format = {
    fill: "#0F766E",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "Center",
    verticalAlignment: "Center",
  };
  headerRange.format.rowHeight = 26;

  if (rowCount > 1) {
    const bodyRange = sheet.getRangeByIndexes(1, 0, rowCount - 1, columns.length);
    bodyRange.format = {
      verticalAlignment: "Top",
      wrapText: true,
    };
    bodyRange.format.borders = { preset: "all", style: "thin", color: "#D9E2EC" };
  }

  for (let col = 0; col < columns.length; col += 1) {
    const width = guessColumnWidth(columns[col]);
    sheet.getRangeByIndexes(0, col, Math.max(rowCount, 1), 1).format.columnWidth = width;
  }
}

function addRowsSheet(workbook, name, rows, preferredOrder = null) {
  const sheet = workbook.worksheets.add(name);
  const columnSet = new Set(preferredOrder ?? []);
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      columnSet.add(key);
    }
  }
  const columns = preferredOrder
    ? [...preferredOrder, ...[...columnSet].filter((key) => !preferredOrder.includes(key))]
    : [...columnSet];
  const matrix = [columns];
  for (const row of rows) {
    matrix.push(columns.map((key) => normalizeCell(row[key])));
  }
  sheet.getRangeByIndexes(0, 0, matrix.length, columns.length).values = matrix;
  applySheetStyle(sheet, matrix.length, columns);
  return sheet;
}

function addNotesSheet(workbook, payload) {
  const sheet = workbook.worksheets.add("说明");
  sheet.showGridLines = false;

  sheet.getRange("A1:D1").merge();
  sheet.getRange("A1").values = [["三国霸业 .stg/.evt 逆向导出总览"]];
  sheet.getRange("A1").format = {
    fill: "#0F172A",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    horizontalAlignment: "Left",
    verticalAlignment: "Center",
  };
  sheet.getRange("A1:D1").format.rowHeight = 28;

  sheet.getRange("A2:D4").values = [
    ["游戏目录", payload.game_dir, "关卡数", payload.selected_stages.length],
    ["导出 JSON", "derived/sidecar_analysis/stage_sidecar_tables.json", "导出 Excel", "derived/sidecar_analysis/stg_evt_analysis.xlsx"],
    ["用途", "把当前 .stg/.evt 文本、记录、家族、候选字段摊平成可筛选表", "阅读顺序", "先看 说明 / 家族总计 / 文本槽位，再下钻到 stg记录 或 evt记录"],
  ];
  sheet.getRange("A2:D4").format = {
    wrapText: true,
    verticalAlignment: "Top",
    borders: { preset: "all", style: "thin", color: "#D9E2EC" },
  };

  const noteRows = payload.tables.notes.map((row) => [row["主题"], row["内容"]]);
  sheet.getRangeByIndexes(5, 0, 1, 2).values = [["主题", "内容"]];
  sheet.getRangeByIndexes(6, 0, noteRows.length, 2).values = noteRows;
  const header = sheet.getRangeByIndexes(5, 0, 1, 2);
  header.format = {
    fill: "#0F766E",
    font: { bold: true, color: "#FFFFFF" },
  };
  const body = sheet.getRangeByIndexes(6, 0, noteRows.length, 2);
  body.format = {
    wrapText: true,
    verticalAlignment: "Top",
    borders: { preset: "all", style: "thin", color: "#D9E2EC" },
  };

  sheet.getRange("A:A").format.columnWidth = 18;
  sheet.getRange("B:B").format.columnWidth = 96;
  sheet.getRange("C:C").format.columnWidth = 18;
  sheet.getRange("D:D").format.columnWidth = 28;
  return sheet;
}

async function savePreview(workbook, outputDir, sheetName, fileName) {
  const blob = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await blob.arrayBuffer()));
}

const args = parseArgs(process.argv.slice(2));
const inputJson = path.resolve(args.inputJson);
const outputPath = path.resolve(args.output);
const previewDir = path.resolve(args.previewDir);
const payload = JSON.parse(await fs.readFile(inputJson, "utf8"));

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const workbook = Workbook.create();
addNotesSheet(workbook, payload);
addRowsSheet(workbook, "关卡总览", payload.tables.overview, [
  "stage", "stg_title", "width", "height", "record_count", "year_start_candidate", "year_end_candidate",
  "has_stg", "has_evt", "has_s", "has_x", "s_size", "x_size", "s_x_same_ratio", "stg_family_count", "evt_family_count",
]);
addRowsSheet(workbook, "家族总计", payload.tables.family_totals, [
  "suffix", "family_guess", "total_records", "stage_count", "top_candidate_columns", "top_layouts", "stages",
]);
addRowsSheet(workbook, "文本槽位", payload.tables.text_slots, [
  "suffix", "family_guess", "text_offset", "hit_count",
]);
addRowsSheet(workbook, "候选字段", payload.tables.candidate_fields, [
  "stage", "suffix", "family_guess", "layout_summary", "word_index", "byte_offset", "nonzero_count", "lt_stage_width", "lt_stage_height", "sample_values", "family_id",
]);
addRowsSheet(workbook, "stg家族", payload.tables.families.filter((row) => row.suffix === "stg"), [
  "stage", "family_guess", "count", "layout_summary", "sample_record_indices", "sample_texts", "ascii_tokens", "family_id",
]);
addRowsSheet(workbook, "evt家族", payload.tables.families.filter((row) => row.suffix === "evt"), [
  "stage", "family_guess", "count", "layout_summary", "sample_record_indices", "sample_texts", "ascii_tokens", "family_id",
]);
addRowsSheet(workbook, "stg字符串", payload.tables.strings.filter((row) => row.suffix === "stg"), [
  "stage", "offset", "text", "source",
]);
addRowsSheet(workbook, "evt字符串", payload.tables.strings.filter((row) => row.suffix === "evt"), [
  "stage", "offset", "text", "source",
]);
addRowsSheet(workbook, "stg记录", payload.tables.stg_records, [
  "stage", "record_index", "family_guess", "text_layout", "texts_joined", "ascii_tokens", "nonzero_words", "text1_offset", "text1", "text2_offset", "text2", "text3_offset", "text3", "text4_offset", "text4",
]);
addRowsSheet(workbook, "evt记录", payload.tables.evt_records, [
  "stage", "record_index", "family_guess", "text_layout", "texts_joined", "ascii_tokens", "nonzero_words", "text1_offset", "text1", "text2_offset", "text2", "text3_offset", "text3", "text4_offset", "text4",
]);
addRowsSheet(workbook, "exe线索", payload.tables.exe_contexts, [
  "suffix", "offset", "va", "xref_offsets", "ascii",
]);

await savePreview(workbook, previewDir, "关卡总览", "overview.png");
await savePreview(workbook, previewDir, "家族总计", "family_totals.png");
await savePreview(workbook, previewDir, "文本槽位", "text_slots.png");

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

console.log(JSON.stringify({ output: outputPath, previewDir }, null, 2));
