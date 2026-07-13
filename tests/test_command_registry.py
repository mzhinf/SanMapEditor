from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from san_tools.__main__ import run_command
from san_tools.cli.command_registry import COMMANDS, command_map


class TestCommandRegistry(unittest.TestCase):
    """验证统一入口中的公开命令不会因迁移遗漏而失效。"""

    def test_command_names_are_unique(self) -> None:
        """命令名必须唯一，否则后注册项会静默覆盖前项。"""

        self.assertEqual(len(COMMANDS), len(command_map()))

    def test_every_registered_command_supports_help(self) -> None:
        """每个公开命令至少必须能加载模块并显示 argparse 帮助。"""

        for entry in COMMANDS:
            with self.subTest(command=entry.name):
                output = io.StringIO()
                with redirect_stdout(output), redirect_stderr(output):
                    with self.assertRaises(SystemExit) as raised:
                        run_command(entry.name, ["--help"])
                self.assertEqual(raised.exception.code, 0, output.getvalue())
                self.assertIn("usage:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
