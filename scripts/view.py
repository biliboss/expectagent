# /// script
# requires-python = ">=3.12"
# dependencies = ["python-fasthtml", "monsterui", "pyyaml"]
# ///
"""The entry point: the app, the route, and serving it.

    uv run web.py              # serve
    uv run web.py --selftest   # check that the file is read from the commit

Inline deps (PEP 723) so uv resolves them per-run — no venv to create, activate
or forget. `app` lives here because uvicorn resolves it by that name.

pico=False: MonsterUI already ships FrankenUI + Tailwind, and leaving Pico on
loads a second CSS reset that fights the first. The theme is slate so the page is
grey and a divergence is the only coloured thing on it.
"""

import sys

from core import eval_open, selftest
from app import App
from fasthtml.common import fast_app, serve
from monsterui.all import Theme

app = fast_app(hdrs=Theme.slate.headers(), pico=False)[0]

# Registered as an expression, so no `index()` exists just to forward the call.
# One route. `?run=N` selects, and 0 is the newest because the runs are stored
# newest first — so opening the bare URL already shows the last run.
#
# It is a `def` and not a lambda because FastHTML resolves a param from its
# ANNOTATION, and a lambda cannot carry one: without it the param is ignored and
# the click silently does nothing.
@app.get("/")
def index(run: int = 0):
    return App(eval_open(), run)

if "--selftest" in sys.argv:
    selftest()
    raise SystemExit(0)

serve()
