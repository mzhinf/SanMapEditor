from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import san_tools.codecs.stage_ini_codec as stage_ini_codec
import san_tools.codecs.stage_ini_txt_linkage as linkage
from san_tools.codecs.stage_ini_excel_codec import read_workbook_tables



def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()



def main() -> int:
    parser = argparse.ArgumentParser(description="Build a new stage.ini from the linked Excel workbook.")
    parser.add_argument("workbook", help="Path to the exported workbook xlsx")
    parser.add_argument("root", nargs="?", default=".", help="Workspace root that contains stage.ini")
    parser.add_argument("--out", default="derived/stage_ini_txt_analysis/stage_ini_from_workbook.ini", help="Output stage.ini path")
    parser.add_argument("--compare-with", default="", help="Optional binary to compare with after rebuild")
    parser.add_argument("--dump-import-json", default="derived/stage_ini_txt_analysis/_tmp_workbook_import.json", help="Optional JSON dump of imported workbook")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    workbook_path = Path(args.workbook).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (root / out_path).resolve()

    workbook_payload = read_workbook_tables(workbook_path)
    if args.dump_import_json:
        import_json_path = Path(args.dump_import_json)
        if not import_json_path.is_absolute():
            import_json_path = (root / import_json_path).resolve()
        import_json_path.parent.mkdir(parents=True, exist_ok=True)
        import_json_path.write_text(json.dumps(workbook_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"json": str(import_json_path), "sheetCount": len(workbook_payload["sheets"])}, ensure_ascii=False, indent=2))

    stage_payload = linkage.apply_workbook_tables_to_stage_ini(root, workbook_payload["sheets"])
    rebuilt = stage_ini_codec.rebuild_stage_ini(stage_payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(rebuilt)

    compare_info = None
    if args.compare_with:
        compare_path = Path(args.compare_with)
        if not compare_path.is_absolute():
            compare_path = (root / compare_path).resolve()
        original = compare_path.read_bytes()
        compare_info = {
            "compare_with": str(compare_path),
            "byte_identical": rebuilt == original,
            "rebuilt_sha256": sha256_bytes(rebuilt),
            "compare_sha256": sha256_bytes(original),
        }

    print(json.dumps({
        "out": str(out_path),
        "size": len(rebuilt),
        "compare": compare_info,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
