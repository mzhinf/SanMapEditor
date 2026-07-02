import unittest
from pathlib import Path

from san_tools.analysis.stage_site_links import build_stage_site_links

ROOT = Path(__file__).resolve().parents[1]


class TestStageSiteLinks(unittest.TestCase):

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
