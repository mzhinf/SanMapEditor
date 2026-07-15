"""验证运行时输入识别、临时会话事务和清理边界。"""

from __future__ import annotations

import json
import os
import shutil
import struct
import time
import unittest
from pathlib import Path

from san_tools.map.editor_runtime_session import (
    SESSION_MARKER_NAME,
    RuntimeInputError,
    RuntimeSessionManager,
    build_casefold_index,
    runtime_input_specs,
    validate_runtime_inputs,
)


ROOT = Path(__file__).resolve().parents[1]
TEST_TMP = ROOT / "derived" / "test_tmp" / "editor_runtime_session"


def write_valid_stage(path: Path, width: int = 1, height: int = 1) -> None:
    """写入只含最小合法头和 Cell 的测试 .m。"""

    header = struct.pack("<II", width, height) + b"Hello1.0"
    path.write_bytes(header + bytes(width * height * 16))


def write_complete_inputs(root: Path, stage: str = "stage01") -> Path:
    """写入校验器需要的完整同组占位文件。"""

    root.mkdir(parents=True, exist_ok=True)
    stage_path = root / f"{stage}.m"
    write_valid_stage(stage_path)
    for spec in runtime_input_specs(stage):
        if spec.role == "map" or not spec.required:
            continue
        (root / spec.filename).write_bytes(f"测试：{spec.role}".encode("utf-8"))
    return stage_path


def fake_exporter(report, data_dir: Path) -> dict[str, object]:
    """模拟真实 Bundle 导出器，只写会话入口用于生命周期测试。"""

    stage_dir = data_dir / report.stage
    stage_dir.mkdir(parents=True)
    (stage_dir / "editor.html").write_text("runtime editor", encoding="utf-8")
    (data_dir / "index.html").write_text("runtime index", encoding="utf-8")
    return {"stage": report.stage, "file_count": len(report.files)}


class TestRuntimeInputValidation(unittest.TestCase):
    """覆盖文件清单、场景匹配和结构校验。"""

    def setUp(self) -> None:
        """为每项输入测试准备干净目录。"""

        shutil.rmtree(TEST_TMP, ignore_errors=True)
        TEST_TMP.mkdir(parents=True)

    def test_complete_inputs_record_hashes_without_repository_fallback(self) -> None:
        """完整用户目录应生成来源、大小和哈希均明确的报告。"""

        source = TEST_TMP / "complete"
        stage_path = write_complete_inputs(source)

        report = validate_runtime_inputs(stage_path)

        self.assertTrue(report.valid)
        self.assertEqual(report.stage, "stage01")
        self.assertEqual(len(report.files), 9)
        self.assertTrue(all(item.path.parent == source.resolve() for item in report.files))
        self.assertTrue(all(len(item.sha256) == 64 for item in report.files))
        self.assertIn("可选文件未提供：kingdom.atr", report.warnings)

    def test_missing_stage_sidecar_reports_other_stage_as_mismatch(self) -> None:
        """缺少当前 .x 但存在其他场景 .x 时必须同时报告缺失和编号错配。"""

        source = TEST_TMP / "mismatch"
        stage_path = write_complete_inputs(source)
        (source / "stage01.x").unlink()
        (source / "stage02.x").write_bytes(b"other")

        report = validate_runtime_inputs(stage_path)

        self.assertFalse(report.valid)
        self.assertIn("stage01.x", report.missing)
        self.assertEqual(report.mismatched["stage01.x"], ["stage02.x"])
        with self.assertRaisesRegex(RuntimeInputError, "场景编号不匹配"):
            report.require_valid()

    def test_invalid_map_header_is_rejected(self) -> None:
        """文件名正确但头结构错误时不得创建半更新会话。"""

        source = TEST_TMP / "bad-map"
        stage_path = write_complete_inputs(source)
        stage_path.write_bytes(b"not-a-map")

        report = validate_runtime_inputs(stage_path)

        self.assertFalse(report.valid)
        self.assertTrue(any("不是有效" in error for error in report.errors))

    def test_casefold_index_exposes_duplicate_names(self) -> None:
        """即使当前文件系统不允许大小写重复，也要覆盖跨平台重复检测。"""

        first = Path("A/kingdom.cel")
        second = Path("B/KINGDOM.CEL")
        unique, duplicates = build_casefold_index([first, second])

        self.assertNotIn("kingdom.cel", unique)
        self.assertEqual(duplicates["kingdom.cel"], [first, second])

    def test_directory_with_multiple_maps_requires_explicit_selection(self) -> None:
        """目录中存在多个地图时不得静默选择第一个。"""

        source = TEST_TMP / "multiple"
        write_complete_inputs(source, "stage01")
        write_valid_stage(source / "stage02.m")
        manager = RuntimeSessionManager(fake_exporter, TEST_TMP / "sessions")

        with self.assertRaisesRegex(RuntimeInputError, "多个地图"):
            manager.create_from_directory(source)


class TestRuntimeSessionLifecycle(unittest.TestCase):
    """覆盖事务替换、失败回滚、过期清理和路径保护。"""

    def setUp(self) -> None:
        """为每项会话测试准备独立用户目录和会话根。"""

        shutil.rmtree(TEST_TMP, ignore_errors=True)
        TEST_TMP.mkdir(parents=True)
        self.source = TEST_TMP / "source"
        self.stage_path = write_complete_inputs(self.source)
        self.session_base = TEST_TMP / "sessions"

    def test_session_metadata_contains_only_explicit_inputs_and_cleans_on_close(self) -> None:
        """成功会话写入临时根，元数据记录输入且关闭后完全清理。"""

        manager = RuntimeSessionManager(fake_exporter, self.session_base)
        session = manager.create_from_stage(
            self.stage_path,
            release_info={"app_title": "测试编辑器"},
        )

        self.assertEqual(session.root.parent, self.session_base.resolve())
        self.assertTrue((session.root / SESSION_MARKER_NAME).is_file())
        metadata = json.loads((session.root / "session-info.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["stage"], "stage01")
        self.assertTrue(all(Path(item["path"]).parent == self.source.resolve() for item in metadata["inputs"]["files"]))
        release = json.loads((session.data_dir / "release-info.json").read_text(encoding="utf-8"))
        self.assertEqual(release["active_stage"], "stage01")
        manager.close()
        self.assertFalse(session.root.exists())
        self.assertIsNone(manager.current)

    def test_failed_reimport_preserves_current_session(self) -> None:
        """新导入生成失败时必须删除半成品并保留旧会话。"""

        manager = RuntimeSessionManager(fake_exporter, self.session_base)
        first = manager.create_from_stage(self.stage_path)

        def failing_exporter(_report, _data_dir: Path) -> dict[str, object]:
            raise ValueError("模拟导出失败")

        manager.exporter = failing_exporter
        (self.source / "heads.dat").write_bytes(b"changed-before-failure")
        with self.assertRaisesRegex(ValueError, "模拟导出失败"):
            manager.create_from_stage(self.stage_path)

        self.assertIs(manager.current, first)
        self.assertTrue(first.root.is_dir())
        session_dirs = [path for path in self.session_base.iterdir() if path.is_dir()]
        self.assertEqual(session_dirs, [first.root])
        manager.close()

    def test_unchanged_inputs_reuse_current_session(self) -> None:
        """来源和内容均未变化时复用现有会话，避免重复生成资源。"""

        manager = RuntimeSessionManager(fake_exporter, self.session_base)
        first = manager.create_from_stage(self.stage_path)
        second = manager.create_from_stage(self.stage_path)

        self.assertIs(second, first)
        self.assertEqual(len([path for path in self.session_base.iterdir() if path.is_dir()]), 1)
        manager.close()

    def test_successful_reimport_replaces_and_cleans_previous_session(self) -> None:
        """新会话完整生成后才删除旧会话，避免半更新状态。"""

        manager = RuntimeSessionManager(fake_exporter, self.session_base)
        first = manager.create_from_stage(self.stage_path)
        (self.source / "heads.dat").write_bytes(b"changed-heads")
        second = manager.create_from_stage(self.stage_path)

        self.assertFalse(first.root.exists())
        self.assertTrue(second.root.exists())
        self.assertIs(manager.current, second)
        manager.close()

    def test_stale_cleanup_only_removes_marked_direct_children(self) -> None:
        """过期回收不能删除无标记目录或会话根外路径。"""

        manager = RuntimeSessionManager(fake_exporter, self.session_base, stale_seconds=10)
        session = manager.create_from_stage(self.stage_path)
        manager.current = None
        marker = session.root / SESSION_MARKER_NAME
        old = time.time() - 20
        os.utime(marker, (old, old))
        unmarked = self.session_base / "user-folder"
        unmarked.mkdir()

        removed = manager.cleanup_stale(now=time.time())

        self.assertEqual(removed, [session.root.resolve()])
        self.assertFalse(session.root.exists())
        self.assertTrue(unmarked.is_dir())
        with self.assertRaisesRegex(RuntimeInputError, "路径越界"):
            manager.cleanup_session_dir(TEST_TMP / "outside")

    def test_default_exporter_failure_does_not_leave_partial_session(self) -> None:
        """真实导出器遇到无效占位资源时必须清理半成品目录。"""

        manager = RuntimeSessionManager(None, self.session_base)
        with self.assertRaises((ValueError, OSError)):
            manager.create_from_stage(self.stage_path)
        self.assertTrue(self.session_base.is_dir())
        session_dirs = [path for path in self.session_base.iterdir() if path.is_dir()]
        self.assertEqual(session_dirs, [])


if __name__ == "__main__":
    unittest.main()
