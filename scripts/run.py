# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Run an eval file against its target and write what happened.

    uv run scripts/run.py path/to/eval.yaml

The run lands in `output/` beside the file, newest first, and past runs are never
rewritten. Exit code is the verdict: 0 held, 1 diverged — so CI needs no parsing.

One verb. The machinery lives in `runner.py`.
"""

import sys
from pathlib import Path

from runner import Run


def run(eval_file: Path) -> int:
    """Execute the cases and report where the record went."""
    destination, held = Run(eval_file).execute()
    print(f"{'PASS' if held else 'FAILED'} — {destination}", flush=True)
    return 0 if held else 1


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1]).resolve() if sys.argv[1:] else None))
