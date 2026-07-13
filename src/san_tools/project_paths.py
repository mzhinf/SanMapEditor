"""集中管理项目目录与用户自备游戏数据的定位规则。"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GAME_DATA_ENV = "SAN_GAME_DATA_DIR"
TEXT_DATA_ENV = "SAN_GAME_TEXT_DIR"

_GAME_MARKERS = ("stage.ini", "kingdom.cel", "heads.dat", "stage01.m", "Emperor.exe")
_TEXT_MARKERS = ("castle.txt", "general.txt", "History.txt")


def _unique_paths(paths: list[Path]) -> list[Path]:
    """按出现顺序去重，避免同一路径被反复探测。"""

    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        key = os.path.normcase(str(resolved))
        if key not in seen:
            result.append(resolved)
            seen.add(key)
    return result


def _environment_path(name: str) -> list[Path]:
    value = os.environ.get(name, "").strip()
    return [Path(value)] if value else []


def _contains_any(path: Path, markers: tuple[str, ...]) -> bool:
    return path.is_dir() and any((path / marker).exists() for marker in markers)


def find_game_data_dir(root: Path | None = None) -> Path:
    """查找游戏数据目录，优先使用环境变量和标准 ``data/game``。"""

    base = (root or PROJECT_ROOT).resolve()
    candidates = [
        *_environment_path(GAME_DATA_ENV),
        base,
        base / "data" / "game",
        PROJECT_ROOT / "data" / "game",
    ]
    for candidate in _unique_paths(candidates):
        if _contains_any(candidate, _GAME_MARKERS):
            return candidate

    raise FileNotFoundError(
        f"未找到游戏数据目录；请准备 {base / 'data' / 'game'}，"
        f"或设置环境变量 {GAME_DATA_ENV}。"
    )


def find_text_data_dir(root: Path | None = None) -> Path:
    """查找 UTF-8 文本表目录，默认使用标准 ``data/text``。"""

    base = (root or PROJECT_ROOT).resolve()
    candidates = [
        *_environment_path(TEXT_DATA_ENV),
        base,
        base / "data" / "text",
        PROJECT_ROOT / "data" / "text",
    ]
    for candidate in _unique_paths(candidates):
        if _contains_any(candidate, _TEXT_MARKERS):
            return candidate
    raise FileNotFoundError(
        f"未找到 UTF-8 文本表目录；请准备 {base / 'data' / 'text'}，"
        f"或设置环境变量 {TEXT_DATA_ENV}。"
    )
