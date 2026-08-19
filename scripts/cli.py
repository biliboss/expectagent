# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#   "jsonschema",
#   "python-fasthtml",
#   "pyyaml",
#   "uvicorn",
#   "pytauri==0.8.*",
#   "pytauri-wheel==0.8.*",
# ]
# ///
"""The command.

    expectagent view  path/to/eval.yaml   # open it, for a human to confirm
    expectagent run   path/to/eval.yaml   # execute it against its target
    expectagent check path/to/eval.yaml   # validate it against the contract
    expectagent       path/to/eval.yaml   # view is the default

One class, one method per verb — the Outline of this file IS the command surface,
so a verb that exists is a verb you can see. The machinery lives in `shared.py`
and `runner.py`.
"""

import sys
from pathlib import Path

from shared import Check, Run, View


class ExpectAgent:
    """The verbs. Each takes the eval file and returns the process exit code."""

    VERBS = ("view", "run", "check")

    @staticmethod
    def view(file_source: Path | None) -> int:
        """Show the case and wait for a person.

        Exits 0 confirmed, 2 dismissed, 3 when a window already had this file and
        was raised instead — that third one is nobody's answer, and a caller that
        reads it as approval is reading a yes that was never given.
        """
        return View.show(file_source)

    @staticmethod
    def run(file_source: Path | None) -> int:
        """Execute the case against its target; write the run beside it.

        Exit code is the verdict, so CI parses nothing.
        """
        if file_source is None:
            raise SystemExit("run needs a file: expectagent run path/to/eval.yaml")
        destination, held = Run(file_source).execute()
        print(f"{'PASS' if held else 'FAILED'} — {destination}", flush=True)
        return 0 if held else 1

    @staticmethod
    def check(file_source: Path | None) -> int:
        """Validate a file against the contract. With no file, prove the contract."""
        import json

        if file_source is None:
            return Check.selftest()
        return 1 if Check.file(file_source, json.loads(Check.SCHEMA_FILE.read_text())) else 0

    @staticmethod
    def main(argv: list[str]) -> int:
        """Pick the verb, resolve the file, go.

        `view` is the default because opening a file to look at it is the thing
        people do without thinking; running one is a decision they type out.
        """
        verb = argv[0] if argv and argv[0] in ExpectAgent.VERBS else None
        rest = argv[1:] if verb else argv
        return getattr(ExpectAgent, verb or "view")(View.resolve(rest))


if __name__ == "__main__":
    raise SystemExit(ExpectAgent.main(sys.argv[1:]))
