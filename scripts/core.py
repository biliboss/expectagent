"""The eval file, and the git it is read from.

The working tree is whatever someone happens to have open right now; the commit
is what actually ran. A report that reads the tree can show a spec that was never
committed, so there is deliberately NO fallback to disk: a path missing from the
commit raises.

    python3 core.py     # self-check
"""

import subprocess
from pathlib import Path

import yaml

# No file until someone points at one. `shared.View.serve` sets it, and the app
# renders the "not set" screen while it is None — a default here would open an
# example nobody asked for and call it their data.
EVAL_FILE: Path | None = None


def _git(anchor: Path, *args: str) -> str:
    """Run git inside the repo that holds `anchor`. Raises with git's own words."""
    # ponytail: one subprocess per call, no caching. Milliseconds against a warm
    # git; cache it when a page starts doing hundreds.
    done = subprocess.run(["git", "-C", str(anchor), *args], capture_output=True, text=True)
    if done.returncode:
        raise FileNotFoundError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.rstrip("\n")


def show(path: Path, ref: str = "HEAD") -> str:
    """File content as of `ref`. Raises if the path is not in that commit."""
    root = Path(_git(path.parent, "rev-parse", "--show-toplevel"))
    return _git(path.parent, "show", f"{ref}:{path.resolve().relative_to(root)}")


def origin(anchor: Path | None = None, ref: str = "HEAD") -> str:
    """Which branch and commit the content came from, e.g. `main @ a1a146ed9`."""
    anchor = anchor or EVAL_FILE
    if anchor is None:
        return ""
    branch = _git(anchor.parent if anchor.is_file() else anchor, "rev-parse", "--abbrev-ref", ref)
    return f"{branch} @ {_git(anchor.parent if anchor.is_file() else anchor, 'rev-parse', '--short', ref)}"


def eval_open() -> str | None:
    """o eval as of HEAD, never from the working tree.

    When the file is not in that commit this returns git's own words about it, so
    the page shows what is missing instead of quietly falling back to the tree.
    """
    if EVAL_FILE is None:
        return None
    try:
        return show(EVAL_FILE)
    except FileNotFoundError as e:
        return str(e)


def eval_read(file_source: str) -> tuple[list, list]:
    """The file's two yaml documents: the spec, and the runs newest first.

    Comments carry the teaching in this file and are dropped here on purpose —
    forty lines of them were burying the four lines of trace.
    """
    docs = [d or [] for d in yaml.safe_load_all(file_source)]
    return (docs[0] if docs else [], docs[1] if len(docs) > 1 else [])


def turn_verb(turn: dict) -> str:
    """A turn's verb: `user`, `agent`, `skill`, `skill_resource`. Anything but
    `happened`, which is the runner writing back, not a step."""
    return next(k for k in turn if k != "happened")


def selftest() -> None:
    """Prove `show` reads the commit, and that the two documents parse."""
    print(f"origin {origin()}")
    spec, runs = eval_read(show(EVAL_FILE))
    print(f"spec: {len(spec)} case(s) · runs: {len(runs)}")
    assert spec, "spec came back empty from the commit"

    # Negative control: this file exists on disk and not in the commit. The day
    # something adds a working-tree fallback, this stops raising and the check
    # stops being worth running — so it is the assertion that matters most.
    ghost = EVAL_FILE.parent / "not_committed.yaml"
    ghost.write_text("case: ghost\n", encoding="utf-8")
    try:
        show(ghost)
        raise AssertionError("read the working tree — this path is not in the commit")
    except FileNotFoundError as e:
        print(f"OK: not in commit, and it says so — {e}")
    finally:
        ghost.unlink()

    print("OK: show reads from the commit, not from disk")


if __name__ == "__main__":
    selftest()
