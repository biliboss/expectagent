"""The whole app: every screen it can show, under one name.

`App` is the only module-level name, and it does one thing — pick the screen the
state deserves. Each screen is a template under it; each template's widgets and
atoms nest under the screen they belong to. Every class is named like a component
because `__new__` returns the element: `App.EvalsTemplate.RunViewWidget.Turn(t)`,
never an instance to render later.

The vocabulary is HeroUI's, written as classes on plain elements: `card`,
`card__header`, `button button--primary`, `chip chip--danger`, `kbd`. There is no
React here and none is needed — every one of these screens is static, and the one
interactive thing on them is a form post. HeroUI ships those classes prebuilt in
`assets/heroui.min.css`, so nothing on this page is compiled at install time.

What HeroUI does NOT ship is Tailwind's utilities, so the handful of layout
classes (`page`, `stack`, `confirm`, `rules`, `trace`) are ours and live in
`assets/theme.css`, next to the Catppuccin Latte palette.

Reading the file, and the git behind it, lives in `shared.py`.
"""

import shared
from shared import Eval
from fasthtml.common import (
    H1,
    H2,
    H3,
    FT,
    Code,
    Details,
    Div,
    P,
    Pre,
    Span,
    Summary,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
)


class App:
    """Every screen, and the choice between them."""

    class Card:
        """The one shape every screen is built from: HeroUI's card, filled in.

        Written once because all five screens are a title, a line under it, and a
        body — repeating the four BEM classes at each call site is where a
        `card__title` eventually becomes a `card_title` and nobody notices.
        """

        def __new__(cls, *body, title=None, under=None, footer=None) -> FT:
            head = (
                Div(
                    H2(title, cls="card__title") if title else "",
                    P(under, cls="card__description") if under else "",
                    cls="card__header",
                )
                if title or under
                else ""
            )
            return Div(
                head,
                Div(*body, cls="card__content"),
                Div(footer, cls="card__footer") if footer else "",
                cls="card",
            )

    class SplashTemplate:
        """Before the first run: what was asked, and nothing pretending to be a result.

        A file with a spec and no runs is the normal state right after the
        interview, so this is not an error screen. It shows the cases as written
        and names the one command that changes the situation — an empty screen
        here would read as "broken" when it means "not measured yet".
        """

        class Confirm:
            """The yes, and the keystroke that gives it.

            The shortcut is bound on `body`, not on the button, so it works wherever
            the eye happens to be — a confirmation you have to click into first is a
            confirmation people click without reading.
            """

            def __new__(cls) -> FT:
                return Div(
                    Span("nada é construído antes daqui", cls="muted"),
                    Div(
                        "confirmar",
                        Span("⌘⏎", cls="kbd"),
                        cls="button button--primary",
                        hx_post="/confirm",
                        hx_target="#eval-body",
                        hx_swap="outerHTML",
                        hx_trigger="click, keydown[(metaKey||ctrlKey)&&key=='Enter'] from:body",
                    ),
                    cls="confirm",
                )

        def __new__(cls, spec: list) -> FT:
            # The confirm is a SIBLING of the card, not inside it: a sticky element
            # cannot leave its parent's box, and a footer's box is the bar itself.
            # Sharing a parent with the whole trace is what gives it room to ride.
            return Div(
                App.Card(
                    App.EvalsTemplate.RunViewWidget.Cases(spec),
                    title="é isso que ele tem que fazer?",
                    under="confirme, e o agente é construído contra isto",
                ),
                cls.Confirm(),
            )

    class ConfirmedTemplate:
        """After the yes: what was agreed, and that the window is done.

        It repeats the cases instead of collapsing to a checkmark, because the
        last thing on screen should be the thing that was agreed to.
        """

        def __new__(cls, spec: list) -> FT:
            return App.Card(
                App.EvalsTemplate.RunViewWidget.Cases(spec),
                title="confirmado",
                under="agora o agente pode ser construído contra isto",
                footer=Code("expectagent run", cls="code"),
            )

    class UnreadableTemplate:
        """The content came back, and it is not an eval.

        `Eval.open` reads the file as of HEAD and, when it is not in that commit,
        returns git's own words instead — on purpose, so nobody confirms a spec that
        was never committed. Those words then went straight into the YAML parser and
        took the screen down with a 500, which showed the person nothing at all.
        Here they are the screen.
        """

        def __new__(cls, content: str, why: str) -> FT:
            return App.Card(
                P(why, cls="muted"),
                Pre(Code(content[:2000])),
                title="não deu pra ler este arquivo",
                under="nada é confirmado a partir daqui",
            )

    class FileSourceNotSetTemplate:
        """No file was pointed at, so there is nothing to show and nothing to guess.

        Opening a default example here would put someone else's data on screen and
        let them mistake it for their own — the worst failure a tool about trusting
        output can have. So it asks, and shows the shape of the answer.
        """

        def __new__(cls) -> FT:
            return App.Card(
                Div(
                    P("aponte para um arquivo de eval:"),
                    Code("expectagent view caminho/do/eval.yaml", cls="code"),
                    P("ou comece pelo exemplo:", cls="muted"),
                    Code("expectagent view examples/ping_pong.yaml", cls="code"),
                    cls="stack",
                ),
                title="nenhum arquivo",
                under="o comando rodou sem dizer o que abrir",
            )

    class EvalsTemplate:
        """The eval file read against its runs: what broke, when, and the file itself."""

        class RunViewWidget:
            """One run, case by case — the newest by default, or whatever the list
            selected.

            It reads against the spec without repeating it: every turn line in a run
            mirrors the spec, so a run IS the spec with the divergences marked.
            """

            class Turn:
                """Atom — one turn of a trace.

                A turn that diverged trades its number for a red chip and is the one
                element on the screen with colour; `happened:` sits under it, in the
                runner's own words.
                """

                class Rules:
                    """Atom — a structured turn, one rule per line.

                    An assert like `tools:` carries nested dicts, and printing the
                    value renders Python's own repr — braces, quotes and all. The
                    person confirming this screen is being asked to agree with the
                    RULE, so the rule is what has to be readable; a leaf becomes
                    `path   value · value`, and the nesting becomes the path.
                    """

                    @staticmethod
                    def leaves(value, path: str = "") -> list:
                        """Walk to the leaves; a leaf is a scalar or a list of them.

                        A list that holds dicts keeps walking — the first cut stopped
                        there and joined them with `str`, which put Python's repr back
                        on the screen for any nested structure. It is the same defect
                        as printing a dict, one level down.
                        """
                        deep = App.EvalsTemplate.RunViewWidget.Turn.Rules.leaves
                        if isinstance(value, list) and any(isinstance(i, dict) for i in value):
                            return [
                                leaf
                                for position, item in enumerate(value, 1)
                                for leaf in deep(item, f"{path} {position}".strip())
                            ]
                        if not isinstance(value, dict):
                            items = value if isinstance(value, list) else [value]
                            return [(path, " · ".join(str(i) for i in items))]
                        return [
                            leaf
                            for key, inner in value.items()
                            for leaf in deep(inner, f"{path} {key}".strip())
                        ]

                    def __new__(cls, verb: str, value) -> FT:
                        # A grid, not a flex row: the label column is fixed so every
                        # rule in a case lines up on the same edge, and the value
                        # column takes the rest. As a flex row the value was squeezed
                        # to its label's width and wrapped four words deep.
                        return Div(
                            *[
                                part
                                for path, text in cls.leaves(value)
                                for part in (
                                    Span(f"{verb} {path}".strip(), cls="rules__label"),
                                    Code(text, cls="code rules__value"),
                                )
                            ],
                            cls="rules",
                        )

                def __new__(cls, turn: dict, position: int) -> FT:
                    verb = Eval.turn_verb(turn)
                    value = turn[verb]
                    broke = "happened" in turn
                    # A turn is not only its verb: `input`, `args`, `mock`, `returns`
                    # and `times` are fields of the same step, and the screen dropped
                    # them. The message the agent must SEND lived in `input`, so the
                    # one promise a person most needs to read was the invisible half.
                    fields = {k: v for k, v in turn.items() if k not in (verb, "happened")}
                    return Tr(
                        Td(
                            Span("✗", cls="chip chip--danger") if broke else str(position),
                            cls="trace__position",
                        ),
                        Td(
                            cls.Rules(verb, value)
                            if isinstance(value, dict)
                            else Code(f"{verb}: {value}", cls="code"),
                            *[cls.Rules(name, held) for name, held in fields.items()],
                            Div(f"happened: {turn['happened']}", cls="trace__happened")
                            if broke
                            else "",
                            cls="trace__turn",
                        ),
                    )

            class Trace:
                """Molecule — the turns of one case, in order.

                Numbered rows because the sequence is real: in this format the ORDER
                of the lines IS the assertion.

                A table and not a stepper: the stepper equalised its items and opened
                130px of nothing between one-line turns, so a nine-turn case ran three
                screens for the content of one. Rows put the numbers on a column the
                eye can run down, which is the only thing the rail was buying.
                """

                def __new__(cls, turns: list) -> FT:
                    return Table(
                        Tbody(
                            *[
                                App.EvalsTemplate.RunViewWidget.Turn(t, i)
                                for i, t in enumerate(turns, 1)
                            ]
                        ),
                        cls="trace",
                    )

            class Guardrails:
                """Molecule — the asserts that hold over the WHOLE case.

                The schema already draws this line: four shapes are named `*Turn` and
                happen at a position, four are named `*Assert` and are true of the run
                end to end. Numbering them together said `tools.only` happens after the
                last step, when it is a constraint on every step — the screen was
                asserting something the format does not.
                """

                KINDS = ("tools", "budget", "judge", "min_score")

                def __new__(cls, asserts: list) -> FT:
                    return App.Card(
                        *[
                            App.EvalsTemplate.RunViewWidget.Turn.Rules(
                                Eval.turn_verb(a), a[Eval.turn_verb(a)]
                            )
                            for a in asserts
                        ],
                        under="vale para o caso inteiro",
                    )

            class Cases:
                """Molecule — every case, name then trace. Also renders a bare spec."""

                # The reserved entry is SETTINGS, not a case: it declares the
                # vocabulary and where the run goes. Rendered as a case it got the
                # same weight as the behaviour being confirmed, which is the one
                # thing on screen the person is actually agreeing to.
                SETTINGS = "expectagent"

                class Case:
                    """Molecule — one case: its name, its ordered trace, its guardrails.

                    A case whose value is a STRING is a run from the earlier format,
                    when a passing case collapsed to `demo: PASSED`. Old runs are kept
                    verbatim because a run is a measurement, so this reads them
                    instead of raising.
                    """

                    def __new__(cls, name: str, turns) -> FT:
                        if not isinstance(turns, list):
                            return Div(H3(name), P(str(turns), cls="muted"), cls="stack")
                        widget = App.EvalsTemplate.RunViewWidget
                        steps = [
                            t for t in turns if Eval.turn_verb(t) not in widget.Guardrails.KINDS
                        ]
                        rules = [t for t in turns if Eval.turn_verb(t) in widget.Guardrails.KINDS]
                        return Div(
                            H3(name),
                            widget.Trace(steps),
                            widget.Guardrails(rules) if rules else "",
                            cls="stack",
                        )

                def __new__(cls, cases: list) -> FT:
                    return Div(
                        *[
                            cls.Case(name, turns)
                            for case in cases
                            for name, turns in case.items()
                            if name != cls.SETTINGS
                        ],
                        cls="stack stack--wide",
                    )

            def __new__(cls, run: dict) -> FT:
                verdict = run.get("verdict", "?")
                return App.Card(
                    cls.Cases(run.get("cases", [])),
                    title=run.get("run", "run"),
                    footer=Span(
                        verdict,
                        cls=f"chip chip--{'success' if verdict == 'PASS' else 'danger'}",
                    ),
                )

        class RunsWidget:
            """Every run the file remembers, newest first — and an index of failures.

            A column of timestamps only answers WHEN. The third column answers WHAT,
            so the list can be read for the failure instead of clicked through one run
            at a time. `selected_run` is the one the view is showing, marked in weight
            and not in colour: colour is spent on divergence and nothing else.
            """

            class Broke:
                """Atom — the first step that diverged, in `case · verb: value`.

                Empty when the run held. Absence reads as "nothing broke" without
                spending a word on it.
                """

                def __new__(cls, run: dict) -> str:
                    return next(
                        (
                            f"{name} · {Eval.turn_verb(t)}: {t[Eval.turn_verb(t)]}"
                            for case in run.get("cases", [])
                            for name, turns in case.items()
                            for t in (turns if isinstance(turns, list) else [])
                            if "happened" in t
                        ),
                        "",
                    )

            class Row:
                """Atom — one run's line, and the whole line is the control.

                The click carries `hx_push_url`, so the address bar keeps `?run=N` and
                the selected run survives a reload or a paste into someone else's chat.
                """

                def __new__(cls, run: dict, index: int, selected: bool) -> FT:
                    when = run.get("run", "?")
                    verdict = run.get("verdict", "?")
                    return Tr(
                        Td(Span(when, style="font-weight:600") if selected else when),
                        Td(
                            Span(verdict, cls="chip chip--danger")
                            if verdict != "PASS"
                            else ""
                        ),
                        Td(App.EvalsTemplate.RunsWidget.Broke(run), cls="muted"),
                        cls="runs__row",
                        hx_get=f"/?run={index}",
                        hx_target="#eval-body",
                        hx_swap="outerHTML",
                        hx_push_url="true",
                    )

            def __new__(cls, runs: list, selected_run: dict) -> FT:
                return App.Card(
                    Table(
                        Thead(Tr(Th("quando"), Th(""), Th("onde quebrou"))),
                        Tbody(*[cls.Row(r, i, r is selected_run) for i, r in enumerate(runs)]),
                        cls="table",
                    ),
                    title=f"{len(runs)} runs",
                )

        def __new__(cls, runs: list, selected: int) -> FT:
            return Div(
                cls.RunViewWidget(runs[selected]),
                cls.RunsWidget(runs, runs[selected]),
                cls="stack stack--wide",
            )

    def __new__(cls, file_source: str | None, selected: int = 0, confirmed: bool = False) -> FT:
        """Pick the screen the state deserves, and wrap it in the shell.

        Five states, and each has a screen: no file, a file that will not read, a
        file with no runs, that same file once someone confirmed it, and a file
        with runs. The shell — the name, the vocabulary, the origin, the raw
        source — only makes sense once a file exists, so the first states render
        bare.

        The whole body carries the htmx id, so selecting a run swaps the view AND
        the list in one exchange — two targets would let the selection drift out
        of step with what is on screen.
        """
        if file_source is None:
            return Div(cls.FileSourceNotSetTemplate(), cls="page", id="eval-body")

        try:
            spec, runs = Eval.read(file_source)
        except Exception as unreadable:
            return Div(
                cls.UnreadableTemplate(file_source, str(unreadable)),
                cls="page",
                id="eval-body",
            )

        # `?run=` comes from the address bar, so it is clamped rather than trusted:
        # an out-of-range index would be an IndexError served as a 500.
        selected = min(max(selected, 0), len(runs) - 1) if runs else 0
        # The vocabulary belongs in the shell, beside the file it describes: it is
        # true of every case in the file, so repeating it inside one of them said
        # it was that case's.
        verbs = next(
            (
                entry[cls.EvalsTemplate.RunViewWidget.Cases.SETTINGS].get("verbs", [])
                for entry in spec
                if cls.EvalsTemplate.RunViewWidget.Cases.SETTINGS in entry
            ),
            [],
        )
        return Div(
            Div(
                Div(
                    H1(shared.EVAL_FILE.name, style="font-size:1.25rem;margin:0"),
                    Span(" · ".join(verbs), cls="muted") if verbs else "",
                    style="display:flex;gap:.75rem;align-items:baseline",
                ),
                Span(Eval.origin(), cls="muted"),
                cls="page__head",
            ),
            cls.EvalsTemplate(runs, selected)
            if runs
            else (cls.ConfirmedTemplate(spec) if confirmed else cls.SplashTemplate(spec)),
            # The raw file, collapsed: open it was forty lines of teaching
            # comments burying four lines of trace, and closed it is one click.
            Details(
                Summary(Span(shared.EVAL_FILE.name, cls="muted")),
                Pre(Code(file_source)),
                cls="raw",
            ),
            cls="page",
            id="eval-body",
        )
