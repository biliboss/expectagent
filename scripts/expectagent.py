# /// script
# requires-python = ">=3.12"
# dependencies = ["python-fasthtml", "monsterui", "pyyaml", "uvicorn"]
# ///
"""Open Expect Agent in a browser.

    uv run scripts/expectagent.py                       # the eval in examples/
    uv run scripts/expectagent.py path/to/eval.yaml

One verb. The machinery it calls lives in `shared.py`.
"""

import sys
from pathlib import Path

from shared import DEFAULT_EVAL, View


def expectagent(argv: list[str]) -> int:
    """Serve the eval file on loopback and hand it to the browser."""
    named = [arg for arg in argv if not arg.startswith("-")]
    file_source = Path(named[0]).resolve() if named else DEFAULT_EVAL
    if not file_source.is_file():
        raise SystemExit(f"no such file: {file_source}")

    port = View.free_port()
    View.serve(file_source, port)
    return View.open(port)


if __name__ == "__main__":
    raise SystemExit(expectagent(sys.argv[1:]))
