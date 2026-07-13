import argparse
import json
import unittest
from pathlib import Path

from san_tools.analysis.analyze_dor import parse_dor
from san_tools.analysis.analyze_stg import read_xlsx_tables, parse_stg
from san_tools.codecs.stg_stream_codec_refactored import cli_parse

ROOT = Path(__file__).resolve().parents[1]


class TestAssets(unittest.TestCase):

    def test_dor(self):
        door_groups = parse_dor('H:/Workstation/san/三国霸业/stage01.dor')
        for door_group in door_groups:
            for k, v in door_group.items():
                if k == 'doors':
                    for door in v:
                        print(door['raw'])
                else:
                    print(k, v)

    def test_stg(self):
        table_path = Path('H:/Workstation/san/outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx')
        stg_path = Path('H:/Workstation/san/三国霸业/stage01.stg')

        tables = read_xlsx_tables(table_path)
        # Ensure table keys exist, so the script can still run without conversion workbook.
        for key in ["general", "castle", "magic", "soldier"]:
            tables.setdefault(key, [])

        scenarios = []
        scenario = parse_stg(stg_path, tables)
        scenarios.append(scenario)
        # out_json = args.out / f"{stg_path.stem}.json"
        # out_json.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")

        # write_csvs(scenarios, args.out)
        # (args.out / "stg_structured_report.md").write_text(markdown_summary(scenarios, tables), encoding="utf-8")
        # print(f"Wrote {len(scenarios)} scenario JSON files + CSV/Markdown to: {args.out}")

    def test_convert_stg(self):
        stg_path = Path('H:/Workstation/san/三国霸业/stage01.stg')
        table_path = Path('H:/Workstation/san/三国霸业')
        xlsx_path = Path('H:/Workstation/san/outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx')
        out_path = Path('H:/Workstation/san/derived')

        cli_parse([stg_path],
                  tables_dir=table_path,
                  xlsx_path=xlsx_path,
                  out_dir=out_path,
                  include_words=False,
                  strict=True,
                  detect_tail_entities=True)
