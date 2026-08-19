"""Serving the view on loopback, and the window that shows it.

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


class Confirm:
    """The person's yes, and what it is worth: the exit code the caller reads.

    APPROVED means someone looked at the screen and said so. Closing the window
    without confirming exits DISMISSED, so an agent that opened this can tell
    approval from walking away — silence is not consent, and the whole product
    rests on a human having actually looked.
    """

    APPROVED = 0
    DISMISSED = 2

    decided = threading.Event()
    app_handle = None  # set by Window.open; None on the browser path

    @staticmethod
    def approve() -> None:
        """Record the yes and end the session. Called by the `/confirm` route.

        The exit is deferred a beat so the response reaches the screen first —
        killing the app mid-response would leave the person staring at a dead
        window wondering whether it took.
        """
        Confirm.decided.set()
        if Confirm.app_handle is not None:
            threading.Timer(0.4, lambda: Confirm.app_handle.exit(Confirm.APPROVED)).start()


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
        """Serve it, open it, and stay up until it closes.

        The steps never happen apart, so they are one call — the entry point should
        not have to know a port exists. The window is the default; the browser is
        what is left when there is no native wheel for this Python.
        """
        port = View.free_port()
        View.serve(eval_file, port)
        try:
            return Window.open(port)
        except ImportError as missing:
            print(f"window unavailable ({missing}); falling back to the browser", file=sys.stderr)
            return View.open(port)

    @staticmethod
    def url(port: int) -> str:
        return f"http://127.0.0.1:{port}/"

    @staticmethod
    def open(port: int) -> int:
        """Hand the URL to the browser and stay up until Ctrl-C."""
        url = View.url(port)
        print(f"the view is at {url} — ⌘⏎ to confirm, Ctrl-C to stop", flush=True)
        webbrowser.open(url)
        Confirm.decided.wait()  # the daemon server dies with this process
        return Confirm.APPROVED


class Window:
    """The desktop window: Tauri through `pytauri-wheel`, no Rust toolchain.

    The window is built in Python, not declared in `Tauri.toml` — pytauri does not
    create config windows at build time, so `[[app.windows]]` produced an app with
    zero windows and `get_webview_window` returned None. Measured, not assumed.

    It renders the same loopback URL the browser would, and registers no commands:
    every piece of state lives in the file, and the runner is what writes it.
    """

    MONITOR = 0

    @staticmethod
    def place(window) -> None:
        """Maximize on monitor 0 — the work area, not the whole glass.

        Order matters and is the only reason this is not one line: `maximize()`
        fills whatever monitor the window is currently on, so the window has to be
        MOVED to monitor 0 first. Maximizing first and moving after would drag a
        maximized window across monitors, which is not the same thing.

        Maximized rather than fullscreen: fullscreen takes over the desktop and
        hides the menu bar, and this is a window someone reads next to their
        editor, not a presentation.
        """
        monitors = window.available_monitors()
        monitor = monitors[Window.MONITOR] if len(monitors) > Window.MONITOR else monitors[0]
        origin_x, origin_y = monitor.position

        from pytauri import Position

        window.set_position(Position.Physical((origin_x, origin_y)))
        window.maximize()

    @staticmethod
    def open(port: int) -> int:
        """Build it hidden, measure the monitor, place it, then show. Returns the exit code.

        Hidden first because placing it needs a window to ask about monitors, and a
        visible one would flash at the default size on the wrong monitor and jump.
        """
        from anyio.from_thread import start_blocking_portal
        from pytauri import Commands, WebviewUrl
        from pytauri.webview import WebviewWindowBuilder
        from pytauri_wheel.lib import builder_factory, context_factory

        with start_blocking_portal("asyncio") as portal:
            app = builder_factory().build(
                context=context_factory(ROOT / "app"),
                invoke_handler=Commands().generate_handler(portal),
            )
            window = WebviewWindowBuilder.build(
                app,
                "main",
                WebviewUrl.External(View.url(port)),
                title="Expect Agent",
                visible=False,
            )

            Window.place(window)
            print(
                f"window maximized on monitor {Window.MONITOR}",
                flush=True,  # stdout is a pipe here, and a buffered line reads as a hang
            )
            Confirm.app_handle = app
            window.show()
            app.run_return()
            # Tauri exits 0 whether someone confirmed or just closed the window,
            # so the answer comes from the flag and not from its exit code.
            return Confirm.APPROVED if Confirm.decided.is_set() else Confirm.DISMISSED
