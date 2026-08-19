"""Everything the two readable files stand on.

`cli.py` is the command and `app.py` is the screen; both are meant to be
understood from their Outline alone. This is where the machinery went so they
could stay that way — read once, then trusted.

Seven names, and each is a job someone says out loud: `Eval` reads the file and
the git behind it, `View` serves the page, `Window` shows it, `Confirm` is the
human yes, `Target` is where a run goes, `Match` decides whether an assert holds,
`Run` walks a case through both, and `Check` proves the contract itself.
"""

import atexit
import hashlib
import importlib
import json
import re
import socket
import subprocess
import sys
import threading
import unicodedata
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]
RESERVED = {"user", "agent", "tool", "tools", "budget", "judge", "min_score"}

# No file until someone points at one. `View.serve` sets it, and the app renders
# the "not set" screen while it is None — a default here would open an example
# nobody asked for and call it their data.
EVAL_FILE: Path | None = None



class Eval:
    """The eval file, and the git it is read from.

    The working tree is whatever someone happens to have open right now; the
    commit is what actually ran. A report that reads the tree can show a spec
    that was never committed, so there is deliberately NO fallback to disk: a
    path missing from the commit raises.
    """

    @staticmethod
    def _git(anchor: Path, *args: str) -> str:
        """Run git inside the repo that holds `anchor`. Raises with git's own words."""
        # ponytail: one subprocess per call, no caching. Milliseconds against a warm
        # git; cache it when a page starts doing hundreds.
        done = subprocess.run(["git", "-C", str(anchor), *args], capture_output=True, text=True)
        if done.returncode:
            raise FileNotFoundError(f"git {' '.join(args)}: {done.stderr.strip()}")
        return done.stdout.rstrip("\n")

    @staticmethod
    def show(path: Path, ref: str = "HEAD") -> str:
        """File content as of `ref`. Raises if the path is not in that commit."""
        root = Path(Eval._git(path.parent, "rev-parse", "--show-toplevel"))
        return Eval._git(path.parent, "show", f"{ref}:{path.resolve().relative_to(root)}")

    @staticmethod
    def origin(anchor: Path | None = None, ref: str = "HEAD") -> str:
        """Which branch and commit the content came from, e.g. `main @ a1a146ed9`."""
        anchor = anchor or EVAL_FILE
        if anchor is None:
            return ""
        where = anchor.parent if anchor.is_file() else anchor
        # An eval outside a repo is a normal thing to open — a scratch file, a case
        # someone was handed. `_git` raising is right for `show`, where an
        # uncommitted spec would be a lie about what ran; here it is only the
        # provenance line, and it took the whole screen down with a 500.
        try:
            branch = Eval._git(where, "rev-parse", "--abbrev-ref", ref)
        except FileNotFoundError:
            return "fora de um repositório"
        return f"{branch} @ {Eval._git(where, 'rev-parse', '--short', ref)}"

    @staticmethod
    def runs_of(eval_file: Path) -> list:
        """The runs for this eval: `output/<name>.runs.yaml` beside it.

        Falls back to the second document inside the file, because that is where runs
        used to live and those files are still real. A run is a measurement, so the
        older shape gets read rather than migrated.
        """
        beside = eval_file.parent / "output" / f"{eval_file.stem}.runs.yaml"
        if beside.is_file():
            return yaml.safe_load(beside.read_text()) or []
        documents = [d or [] for d in yaml.safe_load_all(eval_file.read_text())]
        return documents[1] if len(documents) > 1 else []

    @staticmethod
    def open() -> str | None:
        """o eval as of HEAD, never from the working tree.

        When the file is not in that commit this returns git's own words about it, so
        the page shows what is missing instead of quietly falling back to the tree.
        """
        if EVAL_FILE is None:
            return None
        try:
            return Eval.show(EVAL_FILE)
        except FileNotFoundError as e:
            return str(e)

    @staticmethod
    def read(file_source: str) -> tuple[list, list]:
        """The file's two yaml documents: the spec, and the runs newest first.

        Comments carry the teaching in this file and are dropped here on purpose —
        forty lines of them were burying the four lines of trace.
        """
        docs = [d or [] for d in yaml.safe_load_all(file_source)]
        spec = docs[0] if docs else []
        inside = docs[1] if len(docs) > 1 else []
        beside = Eval.runs_of(EVAL_FILE) if EVAL_FILE is not None else []
        # `output/` wins when it exists: it is where the runner writes now, and a
        # stale second document would show an older verdict as if it were current.
        return spec, (beside or inside)

    @staticmethod
    def turn_verb(turn: dict) -> str:
        """A turn's verb: `user`, `agent`, `skill`, `skill_resource`. Anything but
        `happened`, which is the runner writing back, not a step."""
        return next(k for k in turn if k != "happened")


class Confirm:
    """The person's yes, and what it is worth: the exit code the caller reads.

    APPROVED means someone looked at the screen and said so. Closing the window
    without confirming exits DISMISSED, so an agent that opened this can tell
    approval from walking away — silence is not consent, and the whole product
    rests on a human having actually looked.
    """

    APPROVED = 0
    DISMISSED = 2
    # A launch that found a window already showing this file and raised it. Neither
    # 0 nor 2 would be true: nobody confirmed, and nobody walked away either — the
    # answer belongs to the window that has the file, and this process never hears it.
    HANDED_OFF = 3

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
    def page():
        """The ASGI app: one route to look, one to say yes.

        Built here rather than at import time because `run` and `check` never
        serve anything, and importing the page costs a second they should not pay.

        The CSS is VENDORED and served from this process, never linked to a CDN:
        the window has to work on a plane. `heroui.min.css` is HeroUI's own
        prebuilt file — component classes only, no Tailwind utilities, which is
        why `theme.css` beside it carries both the Catppuccin palette and the
        eight layout rules this screen needs.

        pico=False: HeroUI brings its own reset, and leaving Pico on loads a
        second one that fights it.
        """
        from app import App
        from fasthtml.common import Link, fast_app

        # `static_path` and not a route of our own: FastHTML already answers any
        # request ending in a static extension from that folder, and a hand-written
        # `/css/...` route never sees the request — it 404s from the static handler
        # first. Measured, not guessed.
        page = fast_app(
            pico=False,
            static_path=str(ROOT / "assets"),
            hdrs=(
                Link(rel="stylesheet", href="/heroui.min.css"),
                Link(rel="stylesheet", href="/theme.css"),
            ),
        )[0]

        # A `def` and not a lambda because FastHTML resolves a param from its
        # ANNOTATION, and a lambda cannot carry one: without it the param is
        # ignored and the click silently does nothing.
        @page.get("/")
        def index(run: int = 0):
            return App(Eval.open(), run)

        # The one thing this screen can change in the world. It ends the session
        # with APPROVED, so whoever opened the window learns a human actually said
        # yes — closing it instead exits DISMISSED, and silence never counts as
        # consent.
        @page.post("/confirm")
        def confirm():
            Confirm.approve()
            return App(Eval.open(), confirmed=True)

        # How a second launch finds this one. `/alive` is the handshake — a stale
        # lock file points at a port nobody is listening on, or worse at somebody
        # else's server, so the port alone is never taken as proof.
        @page.get("/alive")
        def alive():
            return "expectagent"

        @page.post("/raise")
        def raise_window():
            Window.focus()
            return "ok"

        return page

    LOCKS = Path.home() / ".expectagent"

    @staticmethod
    def lock_of(eval_file: Path | None) -> Path:
        """The lock for THIS file. One window per eval, not one per machine.

        Per file and not per process because a running window cannot be told to
        show a different eval: pytauri exposes no `eval` or `navigate` on a window,
        so there is no way to make it re-fetch. Focusing it for another file would
        put the wrong case in front of someone about to confirm one.
        """
        key = hashlib.sha1(str(eval_file or "no-file").encode()).hexdigest()[:16]
        return View.LOCKS / f"{key}.port"

    @staticmethod
    def running(eval_file: Path | None) -> int | None:
        """The port of a live window for this file, or None."""
        lock = View.lock_of(eval_file)
        if not lock.exists():
            return None
        try:
            port = int(lock.read_text().strip())
            with urlopen(f"http://127.0.0.1:{port}/alive", timeout=0.5) as answer:
                return port if answer.read() == b"expectagent" else None
        except (ValueError, URLError, OSError):
            lock.unlink(missing_ok=True)  # stale: the process died without cleaning up
            return None

    @staticmethod
    def serve(eval_file: Path | None, port: int) -> None:
        """Start the server on a daemon thread; return once it answers.

        Daemon, so Ctrl-C ends the process with nobody to join. It binds loopback
        only — nothing off this machine can reach it.
        """
        import uvicorn

        sys.path.insert(0, str(Path(__file__).parent))

        # `global`, not a local of the same name: `app.py` reads `shared.EVAL_FILE`
        # by attribute, so a local assignment here would leave it None and render
        # the "no file" screen for a file that was given.
        global EVAL_FILE
        EVAL_FILE = eval_file

        config = uvicorn.Config(View.page(), port=port, host="127.0.0.1", log_level="warning")
        threading.Thread(target=uvicorn.Server(config).run, daemon=True).start()

        url = View.url(port)
        for _ in range(100):  # 10s ceiling; answers in about one
            try:
                urlopen(url, timeout=0.1).read(1)
                return
            except (URLError, OSError):
                threading.Event().wait(0.1)
        raise SystemExit(f"the view never answered at {url} — run it again with the server in the foreground to see why")

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

        A window already showing this file is RAISED instead of a second one being
        built: two windows on one eval means two people can confirm the same case
        and only one of them is heard.
        """
        already = View.running(eval_file)
        if already is not None:
            urlopen(
                urllib.request.Request(f"http://127.0.0.1:{already}/raise", method="POST"),
                timeout=2,
            ).read()
            print("já estava aberto — trouxe a janela pra frente", flush=True)
            # Not APPROVED: nobody confirmed anything here. The window that owns
            # the file owns the answer, and this process never learns it.
            return Confirm.HANDED_OFF

        port = View.free_port()
        View.serve(eval_file, port)
        View.LOCKS.mkdir(parents=True, exist_ok=True)
        lock = View.lock_of(eval_file)
        lock.write_text(str(port))
        atexit.register(lambda: lock.unlink(missing_ok=True))
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

    handle = None  # the live window, so a second launch can raise this one

    @staticmethod
    def place(window) -> None:
        """Fullscreen on monitor 0.

        Order matters and is the only reason this is not one line: fullscreen takes
        the monitor the window is currently ON, so the window has to be MOVED to
        monitor 0 first. Going fullscreen and then setting a position would be
        setting a position on a window that no longer honours one.

        Fullscreen and not maximized: a case is the only thing on screen while
        someone decides whether it is right, and on macOS fullscreen is also what
        gives it its own Space — so it stays put instead of being buried by the
        editor it was opened from.
        """
        monitors = window.available_monitors()
        monitor = monitors[Window.MONITOR] if len(monitors) > Window.MONITOR else monitors[0]
        origin_x, origin_y = monitor.position

        from pytauri import Position

        window.set_position(Position.Physical((origin_x, origin_y)))
        window.set_fullscreen(True)

    @staticmethod
    def focus() -> None:
        """Bring the live window forward. Called from the HTTP thread.

        Through `run_on_main_thread` because that is where the window lives: called
        straight from the request thread these are a crash on macOS, not a no-op.
        """
        window = Window.handle
        if window is None:
            return
        window.run_on_main_thread(
            lambda: (window.unminimize(), window.show(), window.set_focus())
        )

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

            Window.handle = window
            Window.place(window)
            print(
                f"window fullscreen on monitor {Window.MONITOR}",
                flush=True,  # stdout is a pipe here, and a buffered line reads as a hang
            )
            Confirm.app_handle = app
            window.show()
            app.run_return()
            # Tauri exits 0 whether someone confirmed or just closed the window,
            # so the answer comes from the flag and not from its exit code.
            return Confirm.APPROVED if Confirm.decided.is_set() else Confirm.DISMISSED


class Target:
    """Where the run goes. Declared in the file, never wired into the tool."""

    def __init__(self, settings: dict):
        self.spec = settings.get("target") or {"kind": "process", "command": "cat"}
        self.kind = self.spec["kind"]

    def ask(self, message: str) -> dict:
        """Send one user message; get back `{reply, calls}`.

        A target that answers something else is a broken adapter, and saying so
        here beats a confusing assert failure three lines later.
        """
        answer = getattr(self, f"_{self.kind}")(message)
        if not isinstance(answer, dict) or "reply" not in answer:
            raise SystemExit(
                f"the {self.kind} target must answer {{\"reply\": ..., \"calls\": [...]}}, got: {answer!r}"
            )
        answer.setdefault("calls", [])
        return answer

    def _process(self, message: str) -> dict:
        """A command that reads the request on stdin and prints one JSON line."""
        done = subprocess.run(
            self.spec["command"], shell=True, input=json.dumps({"input": message}),
            capture_output=True, text=True,
        )
        if done.returncode:
            raise SystemExit(f"target exited {done.returncode}: {done.stderr.strip()[:400]}")
        return json.loads(done.stdout.strip().splitlines()[-1])

    def _http(self, message: str) -> dict:
        request = urllib.request.Request(
            self.spec["url"],
            data=json.dumps({"input": message}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read())

    def _in_process(self, message: str) -> dict:
        """`module:function`, imported and called. The target lives in this process."""
        import importlib

        module_name, _, function_name = self.spec["callable"].partition(":")
        return getattr(importlib.import_module(module_name), function_name)(message)


class Match:
    """Whether a value satisfies an assert. Knows nothing about targets."""

    @staticmethod
    def prepare(value: str, steps: dict) -> str:
        """Run the declared preparation before comparing.

        Declared in the file and visible in a diff — that is what separates this
        from the runner quietly sanding the reply down until it passes.
        """
        if "extract" in steps:
            found = re.search(steps["extract"], value)
            value = (found.group(1) if found.lastindex else found.group(0)) if found else ""
        for pattern in steps.get("redact", []):
            value = re.sub(pattern, "", value)
        for step in steps.get("normalize", []):
            if step == "case":
                value = value.lower()
            elif step == "whitespace":
                value = " ".join(value.split())
            elif step == "punctuation":
                value = re.sub(r"[^\w\s]", "", value)
            elif step == "emoji":
                value = "".join(c for c in value if unicodedata.category(c) != "So")
            else:
                raise SystemExit(f"normalize step not implemented: {step}")
        return value

    @staticmethod
    def check(value, assertion) -> str:
        """Empty string when it holds; otherwise why it did not."""
        if not isinstance(assertion, dict):
            return "" if value == assertion else f"expected {assertion!r}, got {value!r}"

        value = Match.prepare(str(value), assertion["prepare"]) if "prepare" in assertion else value
        for name, expected in assertion.items():
            if name == "prepare":
                continue
            complaint = Match._one(value, name, expected)
            if complaint:
                return complaint
        return ""

    @staticmethod
    def _one(value, name: str, expected) -> str:
        text = str(value)
        if name == "equals":
            return "" if value == expected else f"expected {expected!r}, got {value!r}"
        if name == "contains":
            if not isinstance(expected, dict):
                expected = {"all": expected if isinstance(expected, list) else [expected]}
            for wanted in expected.get("all", []):
                if str(wanted) not in text:
                    return f"missing {wanted!r}"
            if "any" in expected and not any(str(w) in text for w in expected["any"]):
                return f"none of {expected['any']!r} present"
            for forbidden in expected.get("none", []):
                if str(forbidden) in text:
                    return f"said {forbidden!r}, which it must not"
            return ""
        if name == "matches":
            return "" if re.search(expected, text) else f"does not match /{expected}/"
        if name == "one_of":
            return "" if value in expected else f"expected one of {expected!r}, got {value!r}"
        if name == "starts_with":
            return "" if text.startswith(expected) else f"does not start with {expected!r}"
        if name == "ends_with":
            return "" if text.endswith(expected) else f"does not end with {expected!r}"
        if name == "length":
            return Match._range(len(value), expected, "length")
        if name == "is":
            present = value not in (None, "")
            if expected == "present":
                return "" if present else "nothing came back"
            if expected == "absent":
                return "" if not present else f"expected nothing, got {value!r}"
        if name == "not":
            return "" if Match.check(value, expected) else "the negated assert held"
        if name == "all_of":
            return next((c for c in (Match.check(value, a) for a in expected) if c), "")
        if name == "any_of":
            complaints = [Match.check(value, a) for a in expected]
            return "" if any(c == "" for c in complaints) else " / ".join(complaints)
        # Declared in the schema, not implemented here. Failing loudly is the
        # point: a matcher that quietly passes is a green eval that measures
        # nothing, which is the failure this project exists to prevent.
        raise SystemExit(f"assert not implemented in the runner: {name!r}")

    @staticmethod
    def _range(value: float, expected, label: str) -> str:
        if not isinstance(expected, dict):
            return "" if value == expected else f"{label} {value}, expected {expected}"
        for name, bound in expected.items():
            if name == "gte" and value < bound:
                return f"{label} {value} below {bound}"
            if name == "lte" and value > bound:
                return f"{label} {value} above {bound}"
            if name == "gt" and value <= bound:
                return f"{label} {value} not above {bound}"
            if name == "lt" and value >= bound:
                return f"{label} {value} not below {bound}"
        return ""


class Run:
    """One pass of a file against a target, and the record it leaves."""

    def __init__(self, eval_file: Path):
        self.eval_file = eval_file
        documents = [d or [] for d in yaml.safe_load_all(eval_file.read_text())]
        self.spec = documents[0] if documents else []
        self.settings = next(
            (entry["expectagent"] for entry in self.spec if "expectagent" in entry), {}
        )
        self.cases = [entry for entry in self.spec if "expectagent" not in entry]
        self.verbs = set(self.settings.get("verbs", []))
        self.target = Target(self.settings)

    def verb(self, turn: dict) -> str:
        """The turn's verb: the one key that is not the runner writing back."""
        return next(k for k in turn if k not in ("happened", "input", "args", "returns"))

    def case(self, case: dict) -> tuple[list, bool]:
        """Walk one case. Returns the turns as they happened, and whether it held.

        It stops at the first turn that diverges: the turns after a break did not
        run, so reporting them as anything would be inventing a measurement.
        """
        name, turns = next(iter(case.items()))
        answered, calls, played = None, [], []

        for turn in turns:
            verb = self.verb(turn)
            played.append(dict(turn))

            if verb == "user":
                answered = self.target.ask(turn["user"])
                calls = list(answered["calls"])
                continue
            if answered is None:
                played[-1]["happened"] = "nothing was sent — the case has no `user` turn first"
                return played, False

            complaint = self.turn(turn, verb, answered, calls)
            if complaint:
                played[-1]["happened"] = complaint
                return played, False

        return played, True

    def turn(self, turn: dict, verb: str, answered: dict, calls: list) -> str:
        """Empty string when the turn held; otherwise what happened instead."""
        if verb == "agent":
            return Match.check(answered["reply"], turn["agent"])
        if verb == "tools":
            return self.sequence(turn["tools"], calls)
        if verb in ("tool", *self.verbs):
            return self.call(turn, verb, calls)
        if verb in ("judge", "budget", "min_score"):
            # Real asserts with no runner behind them yet. Saying so beats a run
            # that reads as passing because a whole family was skipped.
            raise SystemExit(f"`{verb}` is in the contract but not in the runner yet")
        raise SystemExit(f"unknown verb {verb!r} — declare it in `expectagent.verbs`")

    def call(self, turn: dict, verb: str, calls: list) -> str:
        """The next call must be this one. Position is the assertion."""
        wanted = turn.get("args", {}).get("name") if verb == "tool" else turn[verb]
        name = turn["tool"] if verb == "tool" else verb
        made = calls.pop(0) if calls else None
        if made is None:
            return f"expected {name}({wanted}), but no call was left"
        if made.get("name") != name or str(made.get("input", "")) != str(wanted):
            return f"expected {name}({wanted}), got {made.get('name')}({made.get('input')})"
        return ""

    def sequence(self, wanted: dict, calls: list) -> str:
        """Asserts about the call sequence as a whole, not one position."""
        made = [c.get("name") for c in calls]
        for name, expected in wanted.items():
            if name == "only":
                stranger = next((n for n in made if n not in expected), None)
                if stranger:
                    return f"called {stranger!r}, which is not in the allowlist"
            elif name == "never":
                called = next((n for n in expected if n in made), None)
                if called:
                    return f"called {called!r}, which it must never call"
            elif name == "must":
                missing = next((n for n in expected if n not in made), None)
                if missing:
                    return f"never called {missing!r}"
            elif name == "times":
                complaint = Match._range(len(made), expected, "call count")
                if complaint:
                    return complaint
            else:
                raise SystemExit(f"tools.{name} is in the contract but not in the runner yet")
        return ""

    def output(self) -> Path:
        """Where the run is written: `output/` beside the case, unless told otherwise.

        Beside the case because a run is about THAT file, and a shared results
        directory makes you cross-reference to learn what broke.
        """
        declared = self.settings.get("runs")
        if declared:
            path = Path(declared)
            return path if path.is_absolute() else self.eval_file.parent / path
        return self.eval_file.parent / "output" / f"{self.eval_file.stem}.runs.yaml"

    def execute(self) -> tuple[Path, bool]:
        """Run every case, write the record, return where it went and the verdict."""
        played, held = [], True
        for case in self.cases:
            name = next(iter(case))
            turns, ok = self.case(case)
            played.append({name: turns})
            held = held and ok

        record = {
            "run": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "verdict": "PASS" if held else "FAILED",
            "target": self.target.spec.get("model") or self.target.kind,
            "cases": played,
        }

        destination = self.output()
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Newest first, and past runs are never rewritten — each one is a
        # measurement of a moment, and editing it would erase what was true then.
        previous = yaml.safe_load(destination.read_text()) if destination.exists() else []
        destination.write_text(
            yaml.safe_dump([record] + (previous or []), allow_unicode=True, sort_keys=False)
        )
        return destination, held


class Check:
    """The contract, proven: what it accepts, and what it must REFUSE.

    The negative controls are the half that matters. A schema with only good
    examples becomes decoration the day someone loosens an `additionalProperties`,
    and the good example keeps passing — which already happened here once, when
    every negative passed vacuously because `iter_errors` returns a generator.
    """

    SCHEMA_FILE = ROOT / "expectagent.schema.json"

    UM_TURNO = """
    - ping_pong:
      - user: ping
      - agent: pong
    """

    MULTITURNO = """
    - ping_pong_com_conhecimento:
      - user: ping
      - tool: knowledge.search
        args: {q: ping}
        returns:
          contains: runbook
      - tool: whatsapp.send
        times: 1
      - agent:
          contains: {all: [pong], none: ["🏓", "Pong!"]}
    """

    MOCADO = """
    - ping_pong_mocado:
      - user: ping
      - tool: knowledge.search
        mock: "pong vem do runbook"
      - agent: pong
    """

    RUNS = """
    - run: "2026-08-19T14:02Z"
      verdict: FAILED
      target: haiku-4.5
      cases:
      - ping_pong:
        - user: ping
        - agent: pong
          happened: "veio 'Pong! 🏓'"
    """

    SEQUENCIA = """
    - ping_pong_com_ordem:
      - user: ping
      - tools:
          includes: [knowledge.search, whatsapp.send]
          only: [knowledge.search, whatsapp.send, clock.now]
          never: [db.drop]
          before:
          - {first: knowledge.search, then: whatsapp.send}
          nth:
          - {index: -1, tool: whatsapp.send, args: {to: "+100000000"}}
          times: {lte: 4}
      - agent: pong
    """

    PRE_COMPARACAO = """
    - resposta_normalizada:
      - user: ping
      - agent:
          prepare: {normalize: [case, emoji, whitespace]}
          equals: pong
    - multipla_escolha:
      - user: "qual a capital? A) Lima B) Quito"
      - agent:
          prepare: {extract: "Answer:\\\\s*([A-D])"}
          one_of: [A, B, C, D]
    """

    ORCAMENTO = """
    - ping_pong_barato:
      - user: ping
      - agent: pong
      - budget:
          max_duration_ms: 1800
          max_cost_usd: 0.02
    """

    COMBINADORES = """
    - resposta_flexivel:
      - user: ping
      - agent:
          all_of:
          - {contains: {all: [pong]}}
          - {not: {contains: {any: ["🏓"]}}}
          - {length: {lte: 40}}
    """

    JUIZ = """
    - resposta_com_juiz:
      - user: "explica o que e um agente"
      - agent:
          length: {lte: 600}
      - judge:
          model: claude-haiku-4-5-20251001
          preset: conciseness
          min_score: 0.7
      - judge:
          model: claude-haiku-4-5-20251001
          rubric: "A resposta explica sem usar jargao de framework?"
          score: boolean
    """

    SIMILAR_E_FORMATO = """
    - saida_estruturada:
      - user: "devolve o json do pedido"
      - agent:
          is_valid:
            format: json
            schema: {type: object, required: [preco]}
      - agent:
          similar: {to: "apartamento de 3 quartos", method: rouge_l, min: 0.6}
    """

    VERBOS_PROPRIOS = """
    - expectagent:
        verbs: [skill, resource, script]
        target: {kind: process, command: "./meu_agente --json"}
        runs: runs/share_external.yaml

    - share_external_main:
      - user: manda pro meu cliente http://exemplo/imovel/1
      - skill: playbook
      - resource: playbook:how_to_route
      - script: whatsapp:send
        input: Peguei o link.
      - tools:
          only: [skill, resource, script]
          never: [criar_link_direto]
      - agent:
          contains: {all: [link], none: [5 minutos]}
    """

    GOOD = {
        "um turno": UM_TURNO,
        "multiturno": MULTITURNO,
        "mocado": MOCADO,
        "runs": RUNS,
        "sequencia de tools": SEQUENCIA,
        "extract e normalize": PRE_COMPARACAO,
        "orcamento": ORCAMENTO,
        "combinadores": COMBINADORES,
        "juiz com trela": JUIZ,
        "similar e formato": SIMILAR_E_FORMATO,
        "verbos proprios": VERBOS_PROPRIOS,
    }

    BAD = {
        "verbo que nao existe": "- x:\n  - usuario: ping\n",
        "turno com dois verbos": "- x:\n  - user: ping\n    agent: pong\n",
        "mock e returns juntos (tautologia)": (
            "- x:\n  - user: ping\n  - tool: t\n    mock: a\n    returns: a\n"
        ),
        "matcher inventado": "- x:\n  - user: ping\n  - agent: {contem: pong}\n",
        "matcher vazio": "- x:\n  - user: ping\n  - agent: {}\n",
        "caso com dois nomes": "- a:\n  - user: ping\n  b:\n  - user: ping\n",
        "caso sem turno": "- x: []\n",
        "close_to sem delta": "- x:\n  - user: ping\n  - agent: {close_to: {value: 1}}\n",
        "veredito que nao existe": (
            '- run: "2026-08-19T14:02Z"\n  verdict: MAYBE\n  cases: []\n'
        ),
        "campo a mais na run": (
            '- run: "2026-08-19T14:02Z"\n  verdict: PASS\n  cases: []\n  nota: oi\n'
        ),
        "primitiva de ordem inventada": (
            "- x:\n  - user: ping\n  - tools: {in_order: [a, b]}\n"
        ),
        "tools vazio": "- x:\n  - user: ping\n  - tools: {}\n",
        "before sem o par": "- x:\n  - user: ping\n  - tools: {before: [{first: a}]}\n",
        "nth sem tool": "- x:\n  - user: ping\n  - tools: {nth: [{index: 1}]}\n",
        "only com objeto em vez de nome": (
            "- x:\n  - user: ping\n  - tools: {only: [{tool: a}]}\n"
        ),
        "normalize com passo que nao existe": (
            "- x:\n  - user: ping\n  - agent: {normalize: [lowercase]}\n"
        ),
        "is_type com tipo inventado": (
            "- x:\n  - user: ping\n  - agent: {is_type: dict}\n"
        ),
        "all_of com um item so": (
            "- x:\n  - user: ping\n  - agent: {all_of: [{contains: pong}]}\n"
        ),
        "budget com chave desconhecida": (
            "- x:\n  - user: ping\n  - budget: {max_ms: 10}\n"
        ),
        "budget zerado": "- x:\n  - user: ping\n  - budget: {max_duration_ms: 0}\n",
        "juiz sem modelo pinado": (
            "- x:\n  - user: ping\n  - agent: pong\n  - judge: {preset: factuality}\n"
        ),
        "juiz sem criterio nenhum": (
            "- x:\n  - user: ping\n  - agent: pong\n  - judge: {model: claude-haiku-4-5-20251001}\n"
        ),
        "juiz com preset inventado": (
            "- x:\n  - user: ping\n  - agent: pong\n"
            "  - judge: {model: claude-haiku-4-5-20251001, preset: vibes}\n"
        ),
        "caso SO com juiz (nao falseia)": (
            "- x:\n  - user: ping\n  - judge: {model: claude-haiku-4-5-20251001, preset: correctness}\n"
        ),
        "min_score fora de 0..1": (
            "- x:\n  - user: ping\n  - agent: pong\n"
            "  - judge: {model: claude-haiku-4-5-20251001, preset: correctness, min_score: 7}\n"
        ),
        "contains vazio": "- x:\n  - user: ping\n  - agent: {contains: {}}\n",
        "similar sem piso": (
            "- x:\n  - user: ping\n  - agent: {similar: {to: pong, method: bleu}}\n"
        ),
        "similar com metodo inventado": (
            "- x:\n  - user: ping\n  - agent: {similar: {to: pong, method: vibes, min: 0.5}}\n"
        ),
        "is_valid com formato inventado": (
            "- x:\n  - user: ping\n  - agent: {is_valid: {format: toml}}\n"
        ),
        "not_contains, que virou contains.none": (
            "- x:\n  - user: ping\n  - agent: {not_contains: pong}\n"
        ),
        "peso zero": "- x:\n  - user: ping\n  - agent: {equals: pong, weight: 0}\n",
        "settings com chave inventada": (
            "- expectagent: {verbos: [skill]}\n- x:\n  - user: ping\n  - agent: pong\n"
        ),
        "verbo custom com maiuscula": (
            "- expectagent: {verbs: [Skill]}\n- x:\n  - user: ping\n  - agent: pong\n"
        ),
        "target sem kind": (
            "- expectagent: {target: {url: http://x}}\n- x:\n  - user: ping\n  - agent: pong\n"
        ),
        "target com kind inventado": (
            "- expectagent: {target: {kind: carrier_pigeon}}\n- x:\n  - user: ping\n  - agent: pong\n"
        ),
        "settings vazio": "- expectagent: {}\n- x:\n  - user: ping\n  - agent: pong\n",
        "verbs vazio": "- expectagent: {verbs: []}\n- x:\n  - user: ping\n  - agent: pong\n",
    }

    @staticmethod
    def table(schema: dict) -> None:
        """Toda primitiva citada na tabela do references/design.md existe no schema.

        Sem isto, a tabela vira folheto: ela promete `tools.after`, ninguem roda nada,
        e o primeiro usuario descobre que o campo nunca existiu. Linha ~~riscada~~ e
        exclusao declarada, e por isso nao entra na cobranca.
        """
        d = schema["$defs"]
        have = (
            set(d["matcher"]["properties"])
            | {f"tools.{k}" for k in d["toolsAssert"]["properties"]["tools"]["properties"]}
            | {f"budget.{k}" for k in d["budgetAssert"]["properties"]["budget"]["properties"]}
            | set(d["scoreAssert"]["properties"])
            | {f"judge.{k}" for k in d["judgeAssert"]["properties"]["judge"]["properties"]}
            | {f"prepare.{k}" for k in d["prepare"]["properties"]}
            | set(d["toolTurn"]["properties"])
        )

        table = (ROOT / "references" / "design.md").read_text()
        table = table.split("## O contrato de asserts")[1].split("\n## ")[0]

        promised: set[str] = set()
        for row in table.splitlines():
            cell = row.split("|")[1] if row.count("|") > 2 else ""
            if "~~" in cell:  # exclusao declarada
                continue
            promised |= set(re.findall(r"`([a-z_.]+)`", cell))

        missing = sorted(p for p in promised if p not in have)
        assert not missing, f"a tabela promete o que o schema nao tem: {missing}"
        print(f"OK: as {len(promised)} primitivas da tabela existem no schema")

    @staticmethod
    def file(eval_file: Path, schema: dict) -> int:
        """Validate ONE eval file. Returns the number of complaints, printed."""
        from jsonschema import Draft202012Validator

        validator = Draft202012Validator(schema)
        complaints = [
            error
            for document in yaml.safe_load_all(eval_file.read_text())
            for error in validator.iter_errors(document or [])
        ]
        for error in complaints[:5]:
            print(f"  {list(error.absolute_path)}: {error.message[:160]}")
        print(f"{eval_file.name}: {len(complaints) or 'no'} complaints")
        return len(complaints)

    @staticmethod
    def selftest() -> int:
        """Prove the schema accepts what it must and refuses what it must not."""
        from jsonschema import Draft202012Validator

        schema = json.loads(Check.SCHEMA_FILE.read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        print("OK: the contract is a valid JSON Schema 2020-12")

        for name, document in Check.GOOD.items():
            errors = sorted(validator.iter_errors(yaml.safe_load(document)), key=str)
            assert not errors, f"should have accepted — {name}: {errors[0].message}"
            print(f"OK: accepts {name}")

        for name, document in Check.BAD.items():
            # list(), not the generator: `iter_errors` returns a generator, and a
            # generator is ALWAYS truthy. Written as a bare assert this passed
            # vacuously for days — green, and measuring nothing.
            assert list(validator.iter_errors(yaml.safe_load(document))), f"NEGATIVE CONTROL FAILED — {name}"
            print(f"OK: refuses {name}")

        Check.table(schema)
        print(f"\n{len(Check.GOOD)} accepted, {len(Check.BAD)} refused.")
        return 0
