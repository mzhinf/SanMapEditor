"""三国霸业地图编辑器桌面启动器。"""

from __future__ import annotations

import argparse
import functools
import http.server
import queue
import sys
import threading
import webbrowser
from pathlib import Path

from san_tools.map.editor_runtime_session import (
    RuntimeInputError,
    RuntimeSession,
    RuntimeSessionManager,
)


APP_TITLE = "三国霸业地图编辑器 2.0"
APP_CREATOR = "mzhinf"
DATA_DIR_NAME = "editor-data"


LAUNCHER_EMPTY = "empty"
LAUNCHER_IMPORTING = "importing"
LAUNCHER_FAILED = "failed"
LAUNCHER_LOADED = "loaded"


class ReplaceCurrentSessionError(RuntimeInputError):
    """表示重新导入前尚未获得用户的明确替换确认。"""


class LauncherRuntimeController:
    """管理启动器导入状态，并把耗时生成逻辑与 Tk 界面分离。"""

    def __init__(
        self,
        release_info: dict[str, object],
        manager: RuntimeSessionManager | None = None,
    ) -> None:
        self.release_info = dict(release_info)
        self.manager = manager or RuntimeSessionManager()
        self.state = LAUNCHER_EMPTY
        self.message = "尚未导入地图项目"

    @property
    def current(self) -> RuntimeSession | None:
        """返回当前成功会话；导入失败时旧会话仍由管理器保留。"""

        return self.manager.current

    def cleanup_stale(self) -> list[Path]:
        """启动时清理异常退出遗留的过期会话。"""

        return self.manager.cleanup_stale()

    def _begin_import(self, replace_confirmed: bool) -> None:
        """校验替换授权并进入导入中状态。"""

        if self.current is not None and not replace_confirmed:
            raise ReplaceCurrentSessionError("重新选择资源前必须确认替换当前会话")
        self.state = LAUNCHER_IMPORTING
        self.message = "正在校验文件并生成临时会话……"

    def _finish_import(self, session: RuntimeSession) -> RuntimeSession:
        """记录成功状态和可供界面展示的输入摘要。"""

        self.state = LAUNCHER_LOADED
        warning_note = f"，{len(session.report.warnings)} 条提示" if session.report.warnings else ""
        self.message = f"已加载 {session.stage}：{len(session.report.files)} 个输入文件{warning_note}"
        return session

    def _fail_import(self, exc: Exception) -> None:
        """记录失败状态，不主动清理管理器保留的旧会话。"""

        self.state = LAUNCHER_FAILED
        self.message = str(exc)

    def import_stage(self, stage_path: Path, replace_confirmed: bool = False) -> RuntimeSession:
        """从用户明确选择的 stageXX.m 创建或替换会话。"""

        self._begin_import(replace_confirmed)
        try:
            return self._finish_import(
                self.manager.create_from_stage(stage_path, stage_path.parent, self.release_info)
            )
        except Exception as exc:
            self._fail_import(exc)
            raise

    def import_directory(self, source_dir: Path, replace_confirmed: bool = False) -> RuntimeSession:
        """从只含一个地图的用户目录创建或替换会话。"""

        self._begin_import(replace_confirmed)
        try:
            return self._finish_import(
                self.manager.create_from_directory(source_dir, self.release_info)
            )
        except Exception as exc:
            self._fail_import(exc)
            raise

    def close(self) -> None:
        """清理当前临时会话。"""

        self.manager.close()


class EditorRequestHandler(http.server.SimpleHTTPRequestHandler):
    """提供编辑器静态文件，并禁用缓存以确保修改立即生效。"""

    def __init__(self, *args: object, directory_provider=None, **kwargs: object) -> None:
        """为每个请求读取当前会话根，使同一端口可安全切换内容。"""

        if directory_provider is None:
            raise ValueError("缺少编辑器内容目录提供器")
        super().__init__(
            *args,
            directory=str(directory_provider()),
            **kwargs,
        )

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """桌面版本不输出 HTTP 访问日志。"""


class EditorHTTPServer(http.server.ThreadingHTTPServer):
    """在固定本机端口上提供可原子切换的编辑器内容目录。"""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir_lock = threading.Lock()
        self._data_dir = data_dir.expanduser().resolve()
        handler = functools.partial(
            EditorRequestHandler,
            directory_provider=self.current_data_dir,
        )
        super().__init__(("127.0.0.1", 0), handler)
        self.daemon_threads = True

    def current_data_dir(self) -> Path:
        """返回新请求应读取的当前内容根。"""

        with self._data_dir_lock:
            return self._data_dir

    def switch_data_dir(self, data_dir: Path) -> Path:
        """把后续请求切换到已经完整生成的新会话目录。"""

        resolved = data_dir.expanduser().resolve()
        if not (resolved / "index.html").is_file():
            raise FileNotFoundError(f"编辑器会话缺少 index.html：{resolved}")
        with self._data_dir_lock:
            self._data_dir = resolved
        return resolved


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
        if (resolved / "index.html").is_file() and (resolved / "release-info.json").is_file():
            return resolved
    searched = "\n".join(str(path) for path in candidates)
    raise FileNotFoundError(f"找不到编辑器数据目录，已检查：\n{searched}")


def editor_entry_path(data_dir: Path, stage: str = "stage01") -> str:
    """优先打开指定关卡，不存在时退回编辑器索引。"""

    if (data_dir / stage / "editor.html").is_file():
        return f"/{stage}/editor.html"
    return "/index.html"


def load_release_info(data_dir: Path) -> dict[str, str]:
    """读取发布包元数据；开发目录不存在时使用明确默认值。"""

    info_path = data_dir / "release-info.json"
    if not info_path.is_file():
        return {"app_title": APP_TITLE, "creator": APP_CREATOR, "build_date": "开发版", "build_time": "开发版"}
    import json

    payload = json.loads(info_path.read_text(encoding="utf-8"))
    return {
        "app_title": str(payload.get("app_title") or APP_TITLE),
        "creator": str(payload.get("creator") or APP_CREATOR),
        "build_date": str(payload.get("build_date") or "未知"),
        "build_time": str(payload.get("build_time") or "未知"),
    }


def create_editor_server(data_dir: Path) -> EditorHTTPServer:
    """创建仅监听本机随机端口的静态文件服务器。"""

    return EditorHTTPServer(data_dir)


def check_editor_data(data_dir: Path, stage: str) -> int:
    """无界面检查入口文件和本机服务器是否能够创建。"""

    entry = editor_entry_path(data_dir, stage)
    if entry == "/index.html" and not (data_dir / "index.html").is_file():
        return 3
    server = create_editor_server(data_dir)
    server.server_close()
    return 0


def run_launcher(data_dir: Path, stage: str, open_browser: bool = True) -> int:
    """启动资源选择界面、本机服务和运行时临时会话。"""

    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    release_info = load_release_info(data_dir)
    app_title = release_info["app_title"]
    controller = LauncherRuntimeController(release_info)
    try:
        controller.cleanup_stale()
    except Exception as exc:
        controller.state = LAUNCHER_FAILED
        controller.message = f"过期会话清理失败：{exc}"

    server = create_editor_server(data_dir)
    port = int(server.server_address[1])
    base_url = f"http://127.0.0.1:{port}"
    initial_entry = editor_entry_path(data_dir, stage)
    if initial_entry != "/index.html":
        controller.state = LAUNCHER_LOADED
        controller.message = f"已加载开发数据：{stage}"
    server_thread = threading.Thread(
        target=server.serve_forever,
        name="editor-http",
        daemon=True,
    )
    server_thread.start()

    root = tk.Tk()
    root.title(app_title)
    root.resizable(False, False)
    root.geometry("620x290")
    root.columnconfigure(0, weight=1)
    state_var = tk.StringVar()
    detail_var = tk.StringVar()
    worker: threading.Thread | None = None
    closing = False
    closed = False
    result_queue = queue.Queue()

    title_label = ttk.Label(
        root,
        textvariable=state_var,
        font=("Microsoft YaHei UI", 13, "bold"),
    )
    title_label.grid(row=0, column=0, padx=24, pady=(20, 8))
    ttk.Label(
        root,
        text=f"创建者：{release_info['creator']}    打包时间：{release_info['build_time']}",
    ).grid(row=1, column=0, padx=24, pady=2)
    ttk.Label(
        root,
        textvariable=detail_var,
        wraplength=560,
        justify="center",
    ).grid(row=2, column=0, padx=24, pady=(8, 12))
    import_controls = ttk.Frame(root)
    import_controls.grid(row=3, column=0, pady=4)
    action_controls = ttk.Frame(root)
    action_controls.grid(row=4, column=0, pady=(10, 16))

    def editor_url() -> str:
        """返回当前状态页或已加载会话的编辑入口。"""

        current = controller.current
        entry = current.entry_path if current is not None else initial_entry
        return base_url + entry

    def open_editor() -> None:
        """打开当前状态对应的浏览器页面。"""

        url = editor_url()
        if not webbrowser.open(url):
            messagebox.showinfo(app_title, f"请在浏览器中打开：\n{url}")

    def refresh_launcher() -> None:
        """根据四种导入状态刷新文字和按钮可用性。"""

        labels = {
            LAUNCHER_EMPTY: "尚未导入地图项目",
            LAUNCHER_IMPORTING: "正在导入地图项目",
            LAUNCHER_FAILED: "地图项目导入失败",
            LAUNCHER_LOADED: "地图项目已加载",
        }
        state_var.set(labels.get(controller.state, "地图编辑器"))
        detail = controller.message
        if controller.state == LAUNCHER_FAILED and controller.current is not None:
            detail += f"\n当前 {controller.current.stage} 会话仍可继续使用。"
        detail_var.set(detail)
        busy = controller.state == LAUNCHER_IMPORTING
        control_state = tk.DISABLED if busy or closing else tk.NORMAL
        choose_file_button.configure(state=control_state)
        choose_dir_button.configure(state=control_state)
        open_button.configure(state=tk.DISABLED if busy else tk.NORMAL)

    def replacement_confirmed() -> bool:
        """已有会话时要求用户明确确认替换。"""

        if controller.current is None:
            return True
        return messagebox.askyesno(
            app_title,
            f"当前已加载 {controller.current.stage}。\n确认生成新会话并替换当前会话吗？",
        )

    def begin_import(kind: str, selected: Path) -> None:
        """在后台执行文件校验和资源生成，避免阻塞 Tk 消息循环。"""

        nonlocal worker
        if not replacement_confirmed():
            return
        replace_confirmed = controller.current is not None
        controller.state = LAUNCHER_IMPORTING
        controller.message = f"正在校验 {selected} 并生成临时会话……"
        refresh_launcher()

        def work() -> None:
            """只在线程中执行无 Tk 调用的耗时导入。"""

            try:
                if kind == "stage":
                    session = controller.import_stage(selected, replace_confirmed)
                else:
                    session = controller.import_directory(selected, replace_confirmed)
                result_queue.put(("loaded", session))
            except Exception as exc:
                result_queue.put(("failed", exc))

        worker = threading.Thread(target=work, name="editor-import", daemon=True)
        worker.start()

    def choose_stage_file() -> None:
        """选择一个 stageXX.m，并默认使用其所在目录配套文件。"""

        selected = filedialog.askopenfilename(
            title="选择 stageXX.m",
            filetypes=(("三国霸业地图", "stage*.m"), ("地图文件", "*.m")),
        )
        if selected:
            begin_import("stage", Path(selected))

    def choose_resource_directory() -> None:
        """选择只含一个 stageXX.m 的完整资源目录。"""

        selected = filedialog.askdirectory(title="选择完整游戏资源目录")
        if selected:
            begin_import("directory", Path(selected))

    def finish_shutdown() -> None:
        """停止 HTTP 服务并清理当前运行时会话。"""

        nonlocal closed
        if closed:
            return
        closed = True
        server.shutdown()
        server.server_close()
        controller.close()
        root.destroy()

    def close_launcher() -> None:
        """导入中等待事务结束再清理，其余状态立即退出。"""

        nonlocal closing
        closing = True
        if worker is not None and worker.is_alive():
            controller.message = "正在完成当前导入并清理临时文件，请稍候……"
            refresh_launcher()
            return
        finish_shutdown()

    def poll_import_result() -> None:
        """在 Tk 主线程处理后台结果、切换内容根并打开编辑页。"""

        nonlocal worker
        try:
            result, payload = result_queue.get_nowait()
        except queue.Empty:
            if not closed:
                root.after(100, poll_import_result)
            return
        worker = None
        if result == "loaded":
            session = payload
            server.switch_data_dir(session.data_dir)
            refresh_launcher()
            if not closing:
                open_editor()
        else:
            refresh_launcher()
            if not closing:
                messagebox.showerror(app_title, str(payload))
        if closing:
            finish_shutdown()
        elif not closed:
            root.after(100, poll_import_result)

    choose_file_button = ttk.Button(
        import_controls,
        text="选择 stageXX.m",
        command=choose_stage_file,
    )
    choose_file_button.grid(row=0, column=0, padx=6)
    choose_dir_button = ttk.Button(
        import_controls,
        text="选择资源目录",
        command=choose_resource_directory,
    )
    choose_dir_button.grid(row=0, column=1, padx=6)
    open_button = ttk.Button(action_controls, text="打开编辑器", command=open_editor)
    open_button.grid(row=0, column=0, padx=6)
    ttk.Button(action_controls, text="停止并退出", command=close_launcher).grid(
        row=0,
        column=1,
        padx=6,
    )
    root.protocol("WM_DELETE_WINDOW", close_launcher)
    refresh_launcher()
    root.after(100, poll_import_result)
    if open_browser:
        open_editor()
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
