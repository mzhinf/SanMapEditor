from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from san_tools.codecs.stage_ini_codec import build_payload, rebuild_stage_ini


ROOT = Path(__file__).resolve().parents[1]


def size_block(payload: bytes) -> bytes:
    """构造 stage.ini 的长度前缀块。"""

    return len(payload).to_bytes(4, "little") + payload


class TestStageIniCompatibilityRoundtrip(unittest.TestCase):
    """验证旧工作簿视图不会丢失块流追加后产生的余数字节。"""

    def test_non_aligned_compatibility_tail_roundtrips(self) -> None:
        """兼容尾区不足 76 字节的部分必须原样保留。"""

        blob = (
            (2).to_bytes(4, "little")
            + size_block(bytes(8))
            + size_block(bytes(4))
            + (2).to_bytes(4, "little")
            + size_block(bytes(12))
            + size_block(b"")
            + size_block(bytes(12))
            + size_block(b"")
            + b"\xaa\xbb"
        )
        root = ROOT / "derived" / "test_tmp" / "stage_ini_compatibility_roundtrip"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        (root / "stage.ini").write_bytes(blob)
        payload = build_payload(root)
        shutil.rmtree(root, ignore_errors=True)

        self.assertEqual(payload["header"]["tail_remainder_size"], 46)
        self.assertEqual(rebuild_stage_ini(payload), blob)


if __name__ == "__main__":
    unittest.main()
