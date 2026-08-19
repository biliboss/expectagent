# /// script
# requires-python = ">=3.12"
# dependencies = ["python-fasthtml", "monsterui", "pyyaml", "uvicorn"]
# ///
"""Open Expect Agent in a browser.

    uv run scripts/expectagent.py path/to/eval.yaml
    uv run scripts/expectagent.py                       # asks which file, on screen

One verb, one name. The machinery it calls lives in `shared.py`, and the argument
parsing happens at the boundary below — so this takes a file, not a command line.
"""

import sys
from pathlib import Path

from shared import View


def expectagent(file_source: Path | None) -> int:
    """Serve the eval file on loopback and hand it to the browser."""
    return View.show(file_source)


if __name__ == "__main__":
    raise SystemExit(expectagent(View.resolve(sys.argv[1:])))
