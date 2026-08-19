# /// script
# requires-python = ">=3.12"
# dependencies = ["python-fasthtml", "monsterui", "pyyaml", "uvicorn"]
# ///
"""Open Expect Agent in a browser.

    uv run scripts/expectagent.py                       # the eval in examples/
    uv run scripts/expectagent.py path/to/eval.yaml

One verb, one name. The machinery it calls lives in `shared.py`.
"""

import sys

from shared import View


def expectagent(argv: list[str]) -> int:
    """Serve the eval file on loopback and hand it to the browser."""
    file_source = View.resolve(argv)
    return View.show(file_source)


if __name__ == "__main__":
    raise SystemExit(expectagent(sys.argv[1:]))
