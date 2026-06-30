from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from san_tools.codecs.scenario_text_codec import classify_text_blob, parse_loose_script_blocks, parse_numbered_sections


class ScenarioTextCodecTest(unittest.TestCase):
    """????????????????"""

    def test_parse_numbered_sections_keeps_ids_headers_and_body(self) -> None:
        text = "#000//??\r\n?????????\r\n#\r\n#098\r\n????\r\n#\r\n"
        sections = parse_numbered_sections(text)
        self.assertEqual(2, len(sections))
        self.assertEqual(0, sections[0]["id"])
        self.assertEqual("//??", sections[0]["header"])
        self.assertEqual("?????????", sections[0]["text"])
        self.assertEqual(98, sections[1]["id"])

    def test_parse_loose_script_blocks_splits_speaker_and_body(self) -> None:
        text = "??\r\n????\r\n\r\n??\r\n????????\r\n\r\n???????\r\n???????\r\n"
        blocks = parse_loose_script_blocks(text)
        self.assertEqual(3, len(blocks))
        self.assertEqual("??", blocks[0]["speaker"])
        self.assertEqual("????", blocks[0]["text"])
        self.assertEqual("??", blocks[1]["speaker"])
        self.assertIn("???????", blocks[2]["text"])
        self.assertEqual("", blocks[2]["speaker"])

    def test_classify_text_blob_distinguishes_text_and_binary(self) -> None:
        text_payload = "????\r\n????\r\n".encode("cp950")
        binary_payload = bytes([0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x41, 0x42, 0x43, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00])
        text_result = classify_text_blob(text_payload)
        binary_result = classify_text_blob(binary_payload)
        self.assertTrue(text_result["likely_text"])
        self.assertFalse(binary_result["likely_text"])
        self.assertGreater(binary_result["zero_ratio"], text_result["zero_ratio"])


if __name__ == "__main__":
    unittest.main()
