"""Serving the view on loopback: the port, the server, the URL, the browser.

Lives apart from `expectagent.py` so that entry point stays one verb. Everything
here is machinery — the kind of thing you read once and then trust.
"""

import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


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
    def serve(eval_file: Path | None, port: int) -> None:
        """Start the server on a daemon thread; return once it answers.

        Daemon, so Ctrl-C ends the process with nobody to join. It binds loopback
        only — nothing off this machine can reach it.
        """
        import uvicorn

        sys.path.insert(0, str(Path(__file__).parent))
        import core

        # Set before importing `view`: `app` does `from core import EVAL_FILE`,
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
    def resolve(argv: list[str]) -> Path | None:
        """Which eval file the command was pointed at, or None when it was not.

        None is a state the app renders, not an error: opening a default example
        would put someone else's data on screen and let them mistake it for theirs.
        A path that was given and does not exist IS an error, and says so.
        """
        named = [arg for arg in argv if not arg.startswith("-")]
        if not named:
            return None
        chosen = Path(named[0]).resolve()
        if not chosen.is_file():
            raise SystemExit(f"no such file: {chosen}")
        return chosen

    @staticmethod
    def show(eval_file: Path | None) -> int:
        """Serve it, open it, and stay up until Ctrl-C.

        The three steps never happen apart, so they are one call — the entry point
        should not have to know a port exists.
        """
        port = View.free_port()
        View.serve(eval_file, port)
        return View.open(port)

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
