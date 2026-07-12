"""三国霸业地图编辑器桌面启动器。"""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
import threading
import webbrowser
from pathlib import Path


APP_TITLE = "三国霸业地图编辑器 2.0"
DATA_DIR_NAME = "editor-data"


class EditorRequestHandler(http.server.SimpleHTTPRequestHandler):
    """提供编辑器静态文件，并禁用缓存以确保修改立即生效。"""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """桌面版本不输出 HTTP 访问日志。"""


def find_editor_data_dir(explicit: Path | None = None) -> Path:
    """查找包含编辑器索引的发布数据目录。"""

    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / DATA_DIR_NAME)
    else:
        project_root = Path(__file__).resolve().parents[3]
        candidates.extend((Path.cwd() / "derived" / "editor", project_root / "derived" / "editor"))

    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (resolved / "index.html").is_file() and (resolved / "index.json").is_file():
            return resolved
    searched = "\n".join(str(path) for path in candidates)
    raise FileNotFoundError(f"找不到编辑器数据目录，已检查：\n{searched}")


def editor_entry_path(data_dir: Path, stage: str = "stage01") -> str:
    """优先打开指定关卡，不存在时退回编辑器索引。"""

    if (data_dir / stage / "editor.html").is_file():
        return f"/{stage}/editor.html"
    return "/index.html"


def create_editor_server(data_dir: Path) -> http.server.ThreadingHTTPServer:
    """创建仅监听本机随机端口的静态文件服务器。"""

    handler = functools.partial(EditorRequestHandler, directory=str(data_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    return server


def check_editor_data(data_dir: Path, stage: str) -> int:
    """无界面检查入口文件和本机服务器是否能够创建。"""

    entry = editor_entry_path(data_dir, stage)
    if entry == "/index.html" and not (data_dir / "index.html").is_file():
        return 3
    server = create_editor_server(data_dir)
    server.server_close()
    return 0


def run_launcher(data_dir: Path, stage: str, open_browser: bool = True) -> int:
    """启动 HTTP 服务和一个用于重新打开或停止编辑器的小窗口。"""

    import tkinter as tk
    from tkinter import messagebox, ttk

    server = create_editor_server(data_dir)
    port = int(server.server_address[1])
    url = f"http://127.0.0.1:{port}{editor_entry_path(data_dir, stage)}"
    server_thread = threading.Thread(target=server.serve_forever, name="editor-http", daemon=True)
    server_thread.start()

    root = tk.Tk()
    root.title(APP_TITLE)
    root.resizable(False, False)
    root.geometry("420x166")
    root.columnconfigure(0, weight=1)

    ttk.Label(root, text="地图编辑器正在运行", font=("Microsoft YaHei UI", 13, "bold")).grid(row=0, column=0, padx=20, pady=(20, 8))
    ttk.Label(root, text="编辑器已在默认浏览器中打开。关闭此窗口将停止本地服务。", wraplength=370, justify="center").grid(row=1, column=0, padx=20, pady=4)
    controls = ttk.Frame(root)
    controls.grid(row=2, column=0, pady=16)
    ttk.Button(controls, text="打开编辑器", command=lambda: webbrowser.open(url)).grid(row=0, column=0, padx=6)

    def close_launcher() -> None:
        """停止服务器并关闭启动器窗口。"""

        server.shutdown()
        server.server_close()
        root.destroy()

    ttk.Button(controls, text="停止并退出", command=close_launcher).grid(row=0, column=1, padx=6)
    root.protocol("WM_DELETE_WINDOW", close_launcher)
    if open_browser and not webbrowser.open(url):
        messagebox.showinfo(APP_TITLE, f"请在浏览器中打开：\n{url}")
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    """解析桌面启动参数。"""

    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--data-dir", type=Path, help="编辑器静态数据目录")
    parser.add_argument("--stage", default="stage01", help="启动后优先打开的关卡")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--check", action="store_true", help="只检查发布数据并立即退出")
    args = parser.parse_args(argv)
    try:
        data_dir = find_editor_data_dir(args.data_dir)
    except FileNotFoundError as exc:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_TITLE, str(exc))
        root.destroy()
        return 2
    if args.check:
        return check_editor_data(data_dir, args.stage)
    return run_launcher(data_dir, args.stage, not args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
