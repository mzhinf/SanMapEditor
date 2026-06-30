from __future__ import annotations

import argparse
import json
from pathlib import Path

from san_tools.codecs.stage_ini_excel_codec import read_workbook_tables



def main() -> int:
    parser = argparse.ArgumentParser(description="Import stage.ini Excel workbook to JSON using Python.")
    parser.add_argument("--input", default="outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx")
    parser.add_argument("--out", default="derived/stage_ini_txt_analysis/stage_ini_txt_workbook_import.json")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    out_path = Path(args.out).resolve()
    payload = read_workbook_tables(input_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"json": str(out_path), "sheetCount": len(payload["sheets"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
