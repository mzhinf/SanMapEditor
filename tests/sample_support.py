"""为依赖用户自备游戏样本的集成测试提供统一跳过逻辑。"""

from __future__ import annotations

import unittest
from pathlib import Path

from san_tools.project_paths import find_game_data_dir, find_text_data_dir


def require_game_data(root: Path) -> Path:
    """返回游戏数据目录；缺失时把当前测试标记为跳过。"""

    try:
        return find_game_data_dir(root)
    except FileNotFoundError as exc:
        raise unittest.SkipTest(str(exc)) from exc


def require_text_data(root: Path) -> Path:
    """返回 UTF-8 文本目录；缺失时把当前测试标记为跳过。"""

    try:
        return find_text_data_dir(root)
    except FileNotFoundError as exc:
        raise unittest.SkipTest(str(exc)) from exc
