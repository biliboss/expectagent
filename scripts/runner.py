"""Executing a case against a target, and writing what happened.

Three names, and the split is the contract. `Target` is where the run goes and
knows nothing about asserts. `Match` decides whether a value satisfies an assert
and knows nothing about targets. `Run` walks a case through both and writes the
result to `output/` beside the file.

THE ADAPTER CONTRACT, and it is the whole of what a target must do: take a user
message, return the reply and the tool calls it made, in order.

    {"reply": "pong", "calls": [{"name": "skill", "input": "playbook"}]}

Anything that can produce that JSON is a target — a subprocess, an HTTP endpoint,
a Python callable. Nothing about a specific framework reaches past this line.

An assert this file cannot evaluate FAILS. It never passes quietly: a matcher
that silently succeeds because nobody implemented it is the exact failure this
whole project exists to prevent.
"""

import json
import re
import subprocess
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

RESERVED = {"user", "agent", "tool", "tools", "budget", "judge", "min_score"}


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
