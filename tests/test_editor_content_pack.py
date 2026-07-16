"""验证独立内容包的生成、审计、缓存载入和组合分发。"""

from __future__ import annotations

import json
import shutil
import unittest
import zipfile
from pathlib import Path

from san_tools.map.compose_editor_distribution import compose_editor_distribution
from san_tools.map.editor_content_pack import (
    CONTENT_PACK_FORMAT,
    CONTENT_PACK_MANIFEST,
    ContentPackError,
    inspect_content_pack,
    load_content_pack,
    write_content_pack,
)
from san_tools.map.editor_runtime_session import RuntimeSessionManager


ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / "derived" / "test_tmp" / "editor_content_pack"


class TestEditorContentPack(unittest.TestCase):
    """覆盖内容包无代码边界、恶意包拒绝、缓存复用和组合 ZIP。"""

    def setUp(self) -> None:
        """为每项测试准备最小但可由浏览器读取的关卡 Bundle。"""

        shutil.rmtree(TEST_TMP, ignore_errors=True)
        self.stage_dir = TEST_TMP / "bundle" / "stage01"
        self.stage_dir.mkdir(parents=True)
        stage = {
            "format": "san-map-editor-v2",
            "stage": "stage01",
            "width": 2,
            "height": 2,
            "image": "map.png",
            "resources": "resources.json",
            "minimap": {"image": "minimap.png"},
            "records": [[0] * 11 for _ in range(4)],
        }
        (self.stage_dir / "stage.json").write_text(json.dumps(stage), encoding="utf-8")
        (self.stage_dir / "resources.json").write_text('{"layers": {}}', encoding="utf-8")
        (self.stage_dir / "map.png").write_bytes(b"map")
        (self.stage_dir / "minimap.png").write_bytes(b"mini")
        (self.stage_dir / "editor.html").write_text("旧编辑器代码", encoding="utf-8")
        self.pack = TEST_TMP / "stage01.sanmap-pack"

    def build_pack(self) -> Path:
        """生成当前测试使用的独立内容包。"""

        write_content_pack(self.stage_dir, self.pack, [{"role": "map", "name": "stage01.m"}])
        return self.pack

    def test_pack_excludes_editor_code_and_cache_uses_current_template(self) -> None:
        """内容包不得携带 editor.html，缓存入口必须由当前程序模板生成。"""

        self.build_pack()
        with zipfile.ZipFile(self.pack) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read(CONTENT_PACK_MANIFEST).decode("utf-8"))
        self.assertEqual(manifest["format"], CONTENT_PACK_FORMAT)
        self.assertNotIn("content/stage01/editor.html", names)

        cache = TEST_TMP / "cache"
        loaded = load_content_pack(self.pack, {"app_title": "测试编辑器"}, cache)
        editor = loaded.data_dir / "stage01" / "editor.html"
        self.assertTrue(editor.is_file())
        self.assertIn("三国霸业地图编辑器", editor.read_text(encoding="utf-8"))
        self.assertFalse(loaded.reused)
        editor.write_text("过期缓存页面", encoding="utf-8")
        reused = load_content_pack(self.pack, {"app_title": "测试编辑器"}, cache)
        self.assertTrue(reused.reused)
        self.assertEqual(reused.root, loaded.root)
        self.assertNotIn("过期缓存页面", editor.read_text(encoding="utf-8"))

    def test_rejects_external_reference_before_writing_archive(self) -> None:
        """封包前拒绝外部路径，并保留已有的有效归档。"""

        self.build_pack()
        original = self.pack.read_bytes()
        stage_path = self.stage_dir / "stage.json"
        stage = json.loads(stage_path.read_text(encoding="utf-8"))
        stage["image"] = "../outside.png"
        stage_path.write_text(json.dumps(stage), encoding="utf-8")

        with self.assertRaisesRegex(ContentPackError, "路径越界"):
            write_content_pack(self.stage_dir, self.pack)
        self.assertEqual(self.pack.read_bytes(), original)

    def test_rejects_hash_tampering_and_path_traversal(self) -> None:
        """内容包必须拒绝哈希篡改和 ZIP 路径穿越。"""

        self.build_pack()
        tampered = TEST_TMP / "tampered.sanmap-pack"
        with zipfile.ZipFile(self.pack) as source, zipfile.ZipFile(tampered, "w") as target:
            for info in source.infolist():
                blob = source.read(info.filename)
                if info.filename.endswith("resources.json"):
                    blob += b"tampered"
                target.writestr(info.filename, blob)
        with self.assertRaisesRegex(ContentPackError, "大小不一致|哈希不一致"):
            inspect_content_pack(tampered)

        traversal = TEST_TMP / "traversal.sanmap-pack"
        with zipfile.ZipFile(traversal, "w") as archive:
            archive.writestr("../escape.txt", b"bad")
            archive.writestr(CONTENT_PACK_MANIFEST, "{}")
        with self.assertRaisesRegex(ContentPackError, "路径越界"):
            inspect_content_pack(traversal)

    def test_runtime_manager_preserves_persistent_cache_on_close(self) -> None:
        """内容包会话关闭时只停止服务，不删除可复用的哈希缓存。"""

        self.build_pack()
        manager = RuntimeSessionManager(session_base=TEST_TMP / "sessions")
        session = manager.create_from_content_pack(self.pack, cache_base=TEST_TMP / "cache")
        self.assertTrue(session.persistent)
        self.assertTrue(session.root.is_dir())
        manager.close()
        self.assertTrue(session.root.is_dir())

    def test_composes_five_file_release_with_nested_content_pack(self) -> None:
        """组合分发只在基础五文件之外增加经过审计的独立内容包。"""

        self.build_pack()
        release = TEST_TMP / "release"
        (release / "editor-data").mkdir(parents=True)
        (release / "SanMapEditor.exe").write_bytes(b"exe")
        (release / "editor-data" / "index.html").write_text("index", encoding="utf-8")
        (release / "editor-data" / "release-info.json").write_text("{}", encoding="utf-8")
        (release / "使用说明.txt").write_text("说明", encoding="utf-8")
        (release / "编辑器使用指南.md").write_text("指南", encoding="utf-8")
        output = TEST_TMP / "with-stage.zip"
        result = compose_editor_distribution(release, [self.pack], output)
        self.assertEqual(result["stages"], ["stage01"])
        with zipfile.ZipFile(output) as archive:
            names = {info.filename for info in archive.infolist() if not info.is_dir()}
        self.assertEqual(len(names), 6)
        self.assertIn("content-packs/stage01.sanmap-pack", names)


if __name__ == "__main__":
    unittest.main()
