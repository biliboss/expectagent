# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#   "pytauri==0.8.*",
#   "pytauri-wheel==0.8.*",
#   "python-fasthtml",
#   "monsterui",
#   "pyyaml",
#   "uvicorn",
# ]
# ///
"""Open Expect Agent in a window.

    uv run scripts/expectagent.py                       # the eval in examples/
    uv run scripts/expectagent.py path/to/eval.yaml
    uv run scripts/expectagent.py --web                 # no window, browser only

The window is Tauri through `pytauri-wheel`: a precompiled wheel, so no Rust
toolchain. It points at the local server instead of bundling a frontend, which is
the same mechanism pytauri's own dev mode uses — one view, two ways to look at it.

`requires-python` stops below 3.14 because `pytauri-wheel` 0.8 ships wheels up to
cp313. Without the ceiling uv resolves to 3.14 and finds no binary.
"""

import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
DEFAULT_EVAL = ROOT / "examples" / "ping_pong.yaml"


class View:
    """The HTML, served on loopback. Same page `view.py` serves on its own."""

    @staticmethod
    def free_port() -> int:
        """A port the OS just confirmed is free.

        A fixed port is the reopen bug: the previous process still holds the
        socket and the second window dies on "address already in use".
        """
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    @staticmethod
    def serve(eval_file: Path, port: int) -> None:
        """Start the server on a daemon thread; return once it answers.

        Daemon, so closing the window ends the process with nobody to join. It
        binds loopback only — the window is the sole client.
        """
        import uvicorn

        sys.path.insert(0, str(Path(__file__).parent))
        import core

        # Set before importing `view`: `template` does `from core import EVAL_FILE`,
        # which binds a copy at import time.
        core.EVAL_FILE = eval_file

        from view import app

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        threading.Thread(target=uvicorn.Server(config).run, daemon=True).start()

        url = View.url(port)
        for _ in range(100):  # 10s ceiling; answers in about one
            try:
                urlopen(url, timeout=0.1).read(1)
                return
            except (URLError, OSError):
                threading.Event().wait(0.1)
        raise SystemExit(f"the view never answered at {url} — run scripts/view.py to see why")

    @staticmethod
    def url(port: int) -> str:
        return f"http://127.0.0.1:{port}/"


class Shell:
    """How the view gets shown. The window when it can, the browser when it cannot."""

    @staticmethod
    def window(port: int) -> int:
        """The Tauri window pointed at the local server. Returns its exit code."""
        from anyio.from_thread import start_blocking_portal
        from pytauri import Commands
        from pytauri_wheel.lib import builder_factory, context_factory

        # No commands registered: the window only renders. Every piece of state
        # lives in the file, and the runner writes it — never the window.
        commands = Commands()

        with start_blocking_portal("asyncio") as portal:
            app = builder_factory().build(
                context=context_factory(
                    APP_DIR,
                    tauri_config={"build": {"frontendDist": f"http://127.0.0.1:{port}"}},
                ),
                invoke_handler=commands.generate_handler(portal),
            )
            return app.run_return()

    @staticmethod
    def browser(port: int) -> int:
        """Open the same view in the default browser and stay up until Ctrl-C."""
        url = View.url(port)
        print(f"the view is at {url} — Ctrl-C to stop")
        webbrowser.open(url)
        threading.Event().wait()  # the daemon server dies with this process
        return 0


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("-")]
    eval_file = Path(args[0]).resolve() if args else DEFAULT_EVAL
    if not eval_file.is_file():
        raise SystemExit(f"no such file: {eval_file}")

    port = View.free_port()
    View.serve(eval_file, port)

    if "--web" in argv:
        return Shell.browser(port)
    try:
        return Shell.window(port)
    except ImportError as e:
        # No native wheel — Python outside cp39..cp313, or an unbuilt platform.
        # The product does not die with the window: the same view opens anyway.
        print(f"window unavailable ({e}); falling back to the browser", file=sys.stderr)
        return Shell.browser(port)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
