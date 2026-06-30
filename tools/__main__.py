from __future__ import annotations

import argparse
import importlib
import sys
from contextlib import contextmanager
from typing import Iterator

from tools.command_registry import COMMANDS, command_map


@contextmanager
def patched_argv(argv: list[str]) -> Iterator[None]:
    """临时替换 sys.argv，让旧脚本 main() 可以继续复用 argparse。"""

    original = sys.argv[:]
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = original


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="三国霸业工具集统一入口。")
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("list", help="列出已注册命令")

    run_parser = subparsers.add_parser("run", help="执行已注册命令")
    run_parser.add_argument("command", help="命令名，可先用 list 查看")
    run_parser.add_argument("args", nargs=argparse.REMAINDER, help="透传给目标脚本的参数")
    return parser


def list_commands() -> int:
    print("可用命令：")
    for entry in COMMANDS:
        print(f"- {entry.name}: {entry.summary}")
    return 0


def run_command(command_name: str, extra_args: list[str]) -> int:
    registry = command_map()
    if command_name not in registry:
        available = ", ".join(sorted(registry))
        raise SystemExit(f"未知命令：{command_name}\n可用命令：{available}")

    entry = registry[command_name]
    module = importlib.import_module(entry.module)
    main_func = getattr(module, "main", None)
    if not callable(main_func):
        raise SystemExit(f"命令 {command_name} 对应模块 {entry.module} 缺少 main()")

    forwarded_args = list(extra_args)
    if forwarded_args[:1] == ["--"]:
        forwarded_args = forwarded_args[1:]

    with patched_argv([entry.module, *forwarded_args]):
        result = main_func()
    return int(result or 0)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.action == "list":
        return list_commands()
    if args.action == "run":
        return run_command(args.command, list(args.args))
    raise SystemExit(f"不支持的动作：{args.action}")


if __name__ == "__main__":
    raise SystemExit(main())