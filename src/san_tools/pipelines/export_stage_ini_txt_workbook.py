from __future__ import annotations

import argparse
import json
from pathlib import Path

import san_tools.codecs.stage_ini_txt_linkage as linkage
from san_tools.codecs.stage_ini_excel_codec import write_workbook



def main() -> int:
    parser = argparse.ArgumentParser(description="Export stage.ini txt linkage workbooks using Python.")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--input-json", default="", help="Optional prebuilt stage_ini_txt_links.json")
    parser.add_argument("--output-dir", default="outputs/stage_ini_txt_analysis")
    parser.add_argument("--analysis-name", default="stage_ini_linked_tables.xlsx")
    parser.add_argument("--conversion-name", default="stage_ini_conversion_tables.xlsx")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.input_json:
        payload = json.loads(Path(args.input_json).resolve().read_text(encoding="utf-8"))
    else:
        payload = linkage.build_bundle(root)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (root / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis_path = output_dir / args.analysis_name
    conversion_path = output_dir / args.conversion_name
    write_workbook(analysis_path, payload["analysis_workbook_sheets"])
    write_workbook(conversion_path, payload["conversion_workbook_sheets"])

    print(json.dumps({
        "analysisXlsx": str(analysis_path),
        "conversionXlsx": str(conversion_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
