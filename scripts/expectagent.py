# /// script
# requires-python = ">=3.12"
# dependencies = ["python-fasthtml", "monsterui", "pyyaml", "uvicorn"]
# ///
"""Open Expect Agent in a browser.

    uv run scripts/expectagent.py                       # the eval in examples/
    uv run scripts/expectagent.py path/to/eval.yaml

It picks a free port, serves the view on loopback, and opens your browser at it.
Nothing to install beyond the four Python packages above, and no desktop
toolchain: the view is HTML, and a browser is the one renderer everyone already
has.
"""

import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVAL = ROOT / "examples" / "ping_pong.yaml"


class View:
    """The HTML, served on loopback. Same page `view.py` serves on its own."""

    @staticmethod
    def free_port() -> int:
        """A port the OS just confirmed is free.

        A fixed port is the reopen bug: the previous process still holds the
        socket and the second launch dies on "address already in use".
        """
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    @staticmethod
    def serve(eval_file: Path, port: int) -> None:
        """Start the server on a daemon thread; return once it answers.

        Daemon, so Ctrl-C ends the process with nobody to join. It binds loopback
        only — nothing off this machine can reach it.
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

    @staticmethod
    def open(port: int) -> int:
        """Hand the URL to the browser and stay up until Ctrl-C."""
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
    return View.open(port)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
