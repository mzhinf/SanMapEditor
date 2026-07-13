import unittest
from pathlib import Path

from san_tools.analysis.stage_site_links import build_stage_site_links
from san_tools.project_paths import find_game_data_dir, find_text_data_dir

ROOT = Path(__file__).resolve().parents[1]


class TestStageSiteLinks(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        """仅在用户准备了 stage01 与文本映射时运行集成验证。"""

        try:
            game_dir = find_game_data_dir(ROOT)
            find_text_data_dir(ROOT)
        except FileNotFoundError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        if not (game_dir / "stage01.stg").exists():
            raise unittest.SkipTest("缺少 stage01.stg，跳过据点城门关联测试。")

    def test_stage01_site_links_cover_all_doors(self) -> None:
        payload = build_stage_site_links(ROOT, "stage01")

        self.assertTrue(payload["available"])
        self.assertEqual(payload["cityCount"], 38)
        self.assertEqual(payload["gateCount"], 148)
        self.assertEqual(payload["matchedGateCount"], 148)

        city = next(item for item in payload["cities"] if item["siteKey"] == "186,230")
        self.assertEqual(city["gateCount"], 4)


if __name__ == "__main__":
    unittest.main()
