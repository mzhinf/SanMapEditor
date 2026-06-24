import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const artifactToolEntry = "C:/Users/mzhinf/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";
const { SpreadsheetFile, Workbook } = await import(pathToFileURL(artifactToolEntry).href);

function parseArgs(argv) {
  const args = {
    inputJson: "derived/stage_ini_analysis/stage_ini_tables.json",
    output: "derived/stage_ini_analysis/stage_ini_analysis.xlsx",
    previewDir: "derived/stage_ini_analysis/previews",
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

function sanitizeText(value) {
  return String(value).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");
}

function normalizeCell(value) {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "number" || typeof value === "boolean" || value instanceof Date) {
    return value;
  }
  if (Array.isArray(value) || typeof value === "object") {
    return sanitizeText(JSON.stringify(value));
  }
  return sanitizeText(value);
}

function guessColumnWidth(key) {
  if (/^w\d{2,3}$/.test(key) || /^nw\d{2}$/.test(key)) {
    return 9;
  }
  if (key.includes("hex")) {
    return 42;
  }
  if (key.includes("words")) {
    return 30;
  }
  if (key.includes("offset") || key.includes("count") || key.includes("index") || key.includes("stride")) {
    return 12;
  }
  if (key.includes("name") || key.includes("label") || key.includes("family")) {
    return 18;
  }
  if (key.includes("strings") || key.includes("layout") || key.includes("nonzero")) {
    return 28;
  }
  return 14;
}

function applySheetStyle(sheet, rowCount, columns) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);

  const headerRange = sheet.getRangeByIndexes(0, 0, 1, columns.length);
  headerRange.format = {
    fill: "#1D4ED8",
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
    sheet.getRangeByIndexes(0, col, Math.max(rowCount, 1), 1).format.columnWidth = guessColumnWidth(columns[col]);
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
  sheet.getRange("A1").values = [["三国霸业 stage.ini 逆向导出总览"]];
  sheet.getRange("A1").format = {
    fill: "#0F172A",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    horizontalAlignment: "Left",
    verticalAlignment: "Center",
  };
  sheet.getRange("A1:D1").format.rowHeight = 28;

  sheet.getRange("A2:D5").values = [
    ["源文件", payload.stage_ini_path, "文件大小", payload.header.file_size],
    ["主表记录数", payload.header.main_count, "主表步长", payload.header.main_stride],
    ["尾表记录数", payload.header.tail_count, "尾表步长", payload.header.tail_stride],
    ["导出 JSON", "derived/stage_ini_analysis/stage_ini_tables.json", "导出 Excel", "derived/stage_ini_analysis/stage_ini_analysis.xlsx"],
  ];
  sheet.getRange("A2:D5").format = {
    wrapText: true,
    verticalAlignment: "Top",
    borders: { preset: "all", style: "thin", color: "#D9E2EC" },
  };

  const noteRows = payload.notes.map((row) => [row["主题"], row["内容"]]);
  sheet.getRangeByIndexes(6, 0, 1, 2).values = [["主题", "内容"]];
  sheet.getRangeByIndexes(7, 0, noteRows.length, 2).values = noteRows;
  sheet.getRangeByIndexes(6, 0, 1, 2).format = {
    fill: "#1D4ED8",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRangeByIndexes(7, 0, noteRows.length, 2).format = {
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
addRowsSheet(workbook, "主表总计", payload.tables.main_family_totals, ["family_guess", "count"]);
addRowsSheet(workbook, "尾表总计", payload.tables.tail_family_totals, ["family_guess", "count"]);
addRowsSheet(workbook, "武将母表", payload.tables.general_master, [
  "record_index", "record_id_candidate", "name", "label", "family_guess", "nonzero_words",
]);
addRowsSheet(workbook, "城市母表", payload.tables.city_master, [
  "record_index", "name", "label", "family_guess", "normalized_family",
  "place_id_candidate_stage_ini", "small_field_a_candidate", "small_field_b_candidate",
  "value_a_candidate", "value_b_candidate", "value_c_candidate", "value_d_candidate",
  "normalized_nonzero_words",
]);
addRowsSheet(workbook, "兵种母表", payload.tables.troop_master, [
  "record_index", "name", "label", "family_guess", "normalized_family",
  "code_a_candidate", "code_b_candidate", "field_w24_candidate", "field_w26_candidate",
  "field_w36_candidate", "normalized_nonzero_words",
]);
addRowsSheet(workbook, "主表记录", payload.tables.main_records, [
  "record_index", "record_id_candidate", "family_guess", "name", "label", "strings_joined",
  "text_count", "nonzero_words", "raw_hex",
]);
addRowsSheet(workbook, "尾表记录", payload.tables.tail_records, [
  "record_index", "file_offset", "family_guess", "normalized_family", "name", "label",
  "text_layout", "strings_joined", "text_count", "nonzero_words", "normalized_nonzero_words", "raw_hex",
]);

await savePreview(workbook, previewDir, "主表总计", "main_family_totals.png");
await savePreview(workbook, previewDir, "尾表总计", "tail_family_totals.png");
await savePreview(workbook, previewDir, "城市母表", "city_master.png");
await savePreview(workbook, previewDir, "兵种母表", "troop_master.png");

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

console.log(JSON.stringify({ output: outputPath, previewDir }, null, 2));
