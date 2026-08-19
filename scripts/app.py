"""The whole app: every screen it can show, under one name.

`App` is the only module-level name, and it does one thing — pick the screen the
state deserves. Each screen is a template under it; each template's widgets and
atoms nest under the screen they belong to. Every class is named like a component
because `__new__` returns the element: `App.EvalsTemplate.RunViewWidget.Turn(t)`,
never an instance to render later.

Only MonsterUI components, no custom CSS or HTML. The screen is grey on purpose:
a divergence is the only coloured thing on it, so the eye lands there before
reading a word.

Reading the file, and the git behind it, lives in `core.py`.
"""

import shared
from shared import Eval
from fasthtml.common import FT, Div, Thead, Tr
from monsterui.all import (
    Button,
    ButtonT,
    Card,
    CodeBlock,
    CodeSpan,
    Container,
    Details,
    DivCentered,
    DivFullySpaced,
    DivLAligned,
    DivVStacked,
    H1,
    H3,
    H4,
    Label,
    LabelT,
    Small,
    Strong,
    Subtitle,
    Summary,
    Table,
    Tbody,
    Td,
    TextPresets,
    Th,
)


class App:
    """Every screen, and the choice between them."""

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
                return DivFullySpaced(
                    Small("nada é construído antes daqui"),
                    Button(
                        "confirmar",
                        Small("⌘⏎", cls="ml-2"),
                        cls=ButtonT.primary,
                        hx_post="/confirm",
                        hx_target="#eval-body",
                        hx_swap="outerHTML",
                        hx_trigger="click, keydown[(metaKey||ctrlKey)&&key==\'Enter\'] from:body",
                    ),
                    # Sticky, because a case is as long as the behaviour is: this one
                    # runs past the viewport, and in the card's footer the ask sat
                    # below the fold — a confirmation screen whose confirmation you
                    # have to go looking for. It rides the bottom edge instead, over
                    # an opaque bar so the trace scrolls under it and stays legible.
                    cls="sticky bottom-0 bg-background border-t border-border py-4 px-2",
                )

        def __new__(cls, spec: list) -> FT:
            # The confirm is a SIBLING of the card, not its footer: a sticky element
            # cannot leave its parent's box, and the footer's box is the bar itself.
            # Sharing a parent with the whole trace is what gives it room to ride.
            return Div(
                Card(
                    App.EvalsTemplate.RunViewWidget.Cases(spec),
                    header=DivCentered(
                        H1("é isso que ele tem que fazer?"),
                        Subtitle("confirme, e o agente é construído contra isto"),
                    ),
                ),
                cls.Confirm(),
            )

    class ConfirmedTemplate:
        """After the yes: what was agreed, and that the window is done.

        It repeats the cases instead of collapsing to a checkmark, because the
        last thing on screen should be the thing that was agreed to.
        """

        def __new__(cls, spec: list) -> FT:
            return Card(
                App.EvalsTemplate.RunViewWidget.Cases(spec),
                header=DivCentered(
                    H1("confirmado"),
                    Subtitle("agora o agente pode ser construído contra isto"),
                ),
                footer=Small(CodeSpan("expectagent run")),
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
            return Card(
                DivVStacked(
                    Small(why, cls=TextPresets.muted_sm),
                    CodeBlock(content[:2000]),
                    cls="items-start gap-3 w-full",
                ),
                header=DivCentered(
                    H1("não deu pra ler este arquivo"),
                    Subtitle("nada é confirmado a partir daqui"),
                ),
            )

    class FileSourceNotSetTemplate:
        """No file was pointed at, so there is nothing to show and nothing to guess.

        Opening a default example here would put someone else's data on screen and
        let them mistake it for their own — the worst failure a tool about trusting
        output can have. So it asks, and shows the shape of the answer.
        """

        def __new__(cls) -> FT:
            return Card(
                DivVStacked(
                    Subtitle("aponte para um arquivo de eval:"),
                    CodeSpan("expectagent view caminho/do/eval.yaml"),
                    Small("ou comece pelo exemplo:"),
                    CodeSpan("expectagent view examples/ping_pong.yaml"),
                ),
                header=DivCentered(
                    H1("nenhum arquivo"),
                    Subtitle("o comando rodou sem dizer o que abrir"),
                ),
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

                A turn that diverged trades its number for `✗` and is the one element
                on the screen with colour; `happened:` sits under it, in the runner's
                own words.
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
                            for leaf in App.EvalsTemplate.RunViewWidget.Turn.Rules.leaves(
                                inner, f"{path} {key}".strip()
                            )
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
                                    Small(f"{verb} {path}".strip(), cls=TextPresets.muted_sm),
                                    CodeSpan(text, cls="justify-self-start"),
                                )
                            ],
                            cls="grid grid-cols-[10rem_1fr] gap-x-4 gap-y-1 items-baseline w-full",
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
                            Label("✗", cls=LabelT.destructive) if broke else Small(str(position)),
                            cls="align-top w-10 pt-1",
                        ),
                        Td(
                            cls.Rules(verb, value)
                            if isinstance(value, dict)
                            else CodeSpan(f"{verb}: {value}"),
                            *[cls.Rules(name, held) for name, held in fields.items()],
                            Small(f"happened: {turn['happened']}", cls=TextPresets.muted_sm)
                            if broke
                            else "",
                            cls="align-top space-y-1",
                        ),
                    )

            class Trace:
                """Molecule — the turns of one case, in order.

                Numbered rows because the sequence is real: in this format the ORDER
                of the lines IS the assertion.

                A table and not `Steps`: the stepper equalised its items and opened
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
                        cls="uk-table-small w-full",
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
                    return Card(
                        *[
                            App.EvalsTemplate.RunViewWidget.Turn.Rules(
                                Eval.turn_verb(a), a[Eval.turn_verb(a)]
                            )
                            for a in asserts
                        ],
                        header=Small("vale para o caso inteiro", cls=TextPresets.muted_sm),
                        cls="mt-4 w-full",
                    )

            class Cases:
                """Molecule — every case, name then trace. Also renders a bare spec.

                A case whose value is a STRING is a run from the earlier format, when
                a passing case collapsed to `demo: PASSED`. Old runs are kept verbatim
                because a run is a measurement, so this reads them instead of raising:
                the shape came from outside, and outside shapes get a fallback.
                """

                # The reserved entry is SETTINGS, not a case: it declares the
                # vocabulary and where the run goes. Rendered as a case it got the
                # same weight as the behaviour being confirmed, which is the one
                # thing on screen the person is actually agreeing to.
                SETTINGS = "expectagent"

                class Case:
                    """Molecule — one case: its name, its ordered trace, its guardrails."""

                    def __new__(cls, name: str, turns) -> FT:
                        if not isinstance(turns, list):
                            return Div(H4(name), Small(str(turns)), cls="w-full space-y-2")
                        widget = App.EvalsTemplate.RunViewWidget
                        steps = [t for t in turns if Eval.turn_verb(t) not in widget.Guardrails.KINDS]
                        rules = [t for t in turns if Eval.turn_verb(t) in widget.Guardrails.KINDS]
                        # A plain block, not `DivVStacked`: that one carries
                        # `items-center`, and an `items-start` beside it does not win —
                        # same Tailwind family, so the stylesheet's order decides, not
                        # the attribute's. The case name drifted to the middle while
                        # its own trace sat left.
                        return Div(
                            H4(name),
                            widget.Trace(steps),
                            widget.Guardrails(rules) if rules else "",
                            cls="w-full space-y-2",
                        )

                def __new__(cls, cases: list) -> FT:
                    return Div(
                        *[
                            cls.Case(name, turns)
                            for case in cases
                            for name, turns in case.items()
                            if name != cls.SETTINGS
                        ],
                        cls="w-full space-y-8",
                    )

            def __new__(cls, run: dict) -> FT:
                return Card(
                    cls.Cases(run.get("cases", [])),
                    header=DivFullySpaced(
                        H3(run.get("run", "run")),
                        Label(
                            run.get("verdict", "?"),
                            cls=LabelT.secondary
                            if run.get("verdict") == "PASS"
                            else LabelT.destructive,
                        ),
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
                    return Tr(
                        Td(Strong(when) if selected else when),
                        Td(
                            Label(run["verdict"], cls=LabelT.destructive)
                            if run.get("verdict") != "PASS"
                            else ""
                        ),
                        Td(Small(App.EvalsTemplate.RunsWidget.Broke(run))),
                        cls="cursor-pointer",
                        hx_get=f"/?run={index}",
                        hx_target="#eval-body",
                        hx_swap="outerHTML",
                        hx_push_url="true",
                    )

            def __new__(cls, runs: list, selected_run: dict) -> FT:
                return Card(
                    Table(
                        Thead(Tr(Th("quando"), Th(""), Th("onde quebrou"))),
                        Tbody(*[cls.Row(r, i, r is selected_run) for i, r in enumerate(runs)]),
                    ),
                    header=H3(f"{len(runs)} runs"),
                )

        def __new__(cls, runs: list, selected: int) -> FT:
            # A block, for the same reason the case list is one: `DivVStacked` centres
            # its children, and the run card came out narrow in the middle of a wide
            # window with the trace crammed into half of it.
            return Div(
                cls.RunViewWidget(runs[selected]),
                cls.RunsWidget(runs, runs[selected]),
                cls="w-full space-y-4",
            )

    def __new__(cls, file_source: str | None, selected: int = 0, confirmed: bool = False) -> FT:
        """Pick the screen the state deserves, and wrap it in the shell.

        Four states, and each has a screen: no file, a file with no runs, that
        same file once someone confirmed it, and a file with runs. The shell — the name, the origin, the raw source — only
        makes sense once a file exists, so the first state renders bare.

        The whole body carries the htmx id, so selecting a run swaps the view AND
        the list in one exchange — two targets would let the selection drift out
        of step with what is on screen.
        """
        if file_source is None:
            return Container(cls.FileSourceNotSetTemplate(), id="eval-body")

        try:
            spec, runs = Eval.read(file_source)
        except Exception as unreadable:
            return Container(
                cls.UnreadableTemplate(file_source, str(unreadable)), id="eval-body"
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
        return Container(
            DivFullySpaced(
                DivLAligned(
                    H3(shared.EVAL_FILE.name),
                    Small(" · ".join(verbs), cls=TextPresets.muted_sm) if verbs else "",
                    cls="gap-3 items-baseline",
                ),
                Subtitle(Eval.origin()),
            ),
            cls.EvalsTemplate(runs, selected)
            if runs
            else (cls.ConfirmedTemplate(spec) if confirmed else cls.SplashTemplate(spec)),
            # The raw file, collapsed: open it was forty lines of teaching
            # comments burying four lines of trace, and closed it is one click.
            Details(
                Summary(Small(shared.EVAL_FILE.name)),
                CodeBlock(file_source, code_cls="language-yaml"),
            ),
            id="eval-body",
        )
