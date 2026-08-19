#!/usr/bin/env python3
"""Runs the eval file against Kimi k3 (coding plan) and appends the run below it.

The file holds TWO yaml documents separated by `---`: the spec on top, written by
a human and never touched by this script, and the last run underneath, rewritten
whole on every execution. That split is the whole reason the spec never gets a
verdict inserted into the middle of it.

The case name is the key and the list under it is the trajectory, so the ORDER of
the lines is the assertion: every `skill:` / `skill_resource:` entry is a
position, not set membership. A tool called out of order, twice, or not at all is
a failure, and the run says so on the line where it happened.

Match is exact by default — `agent:` must equal the reply, byte for byte. Nothing
is stripped from the model's output: sanding the reply down after the fact would
turn a green eval into a lie.

    python3 demo.py
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).parent
EVAL = Path(__file__).resolve().parents[2] / "examples" / "ping_pong.yaml"
SKILLS = HERE / "skills"
API = "https://api.kimi.com/coding/v1/chat/completions"
MODEL = "k3"
SYSTEM = """Você atende pedidos usando skills.

Pedido de procedimento ("como faço X", "como dar X"): carregue a skill `playbook`
com a tool `skill` ANTES de responder, e siga exatamente o que ela instrui.
Saudação ou teste de conexão (ping, oi): responda direto, sem tool nenhuma.

Responda com o texto exato pedido e nada além: sem pontuação de sobra, sem emoji,
sem pergunta de volta, sem se apresentar."""

TOOL_KEYS = ("skill", "skill_resource")
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "skill",
            "description": "Load a skill's instructions before acting on a request.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_resource",
            "description": "Read one resource of a loaded skill, by file name only — never a path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Resource file name, e.g. foo.md"}},
                "required": ["path"],
            },
        },
    },
]


def exec_tool(name: str, args: dict) -> str:
    """Real lookup on disk. A missing skill answers not-found instead of faking
    content — an eval that passes on invented text is worse than a red one."""
    if name == "skill":
        path = SKILLS / args.get("name", "") / "SKILL.md"
    else:
        path = next(SKILLS.rglob(args.get("path", "")), None) if SKILLS.is_dir() else None
    return path.read_text(encoding="utf-8") if path and path.is_file() else f"not found: {args}"


def converse(prompt: str) -> tuple[str, list[tuple[str, str]]]:
    """Returns the final reply and the tool calls in the order they happened."""
    key = (Path.home() / "kimi_token").read_text().strip()
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    calls: list[tuple[str, str]] = []

    for _ in range(8):  # ponytail: a turn needing more than 8 hops is a bug, not a budget
        body = json.dumps(
            {"model": MODEL, "messages": messages, "tools": TOOLS, "max_tokens": 256}
        ).encode()
        req = urllib.request.Request(
            API, body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            msg = json.load(r)["choices"][0]["message"]

        if not msg.get("tool_calls"):
            return msg.get("content") or "", calls

        messages.append({k: v for k, v in msg.items() if k != "reasoning_content"})
        for call in msg["tool_calls"]:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"] or "{}")
            calls.append((name, args.get("name") or args.get("path") or ""))
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": exec_tool(name, args)}
            )

    return "", calls


def q(value: str) -> str:
    """Double-quoted scalar via json — survives newlines, emoji and colons."""
    return json.dumps(value, ensure_ascii=False)


def run_case(name: str, turns: list) -> tuple[bool, list[str]]:
    """Returns (passed, run-document lines for this case)."""
    # ponytail: one user turn per case, which is all these cases have. A second
    # one earns a real loop when a case needs it.
    prompt = next(t["user"] for t in turns if "user" in t)
    want_calls = [(k, t[k]) for t in turns for k in TOOL_KEYS if k in t]
    want_reply = next(t["agent"] for t in turns if "agent" in t)

    reply, calls = converse(prompt)
    reply_ok = reply == want_reply
    calls_ok = calls == want_calls

    print(f"{'Ok' if reply_ok else 'X'} {name}: agent {reply!r} (esperado {want_reply!r})")
    print(f"{'Ok' if calls_ok else 'X'} {name}: tools {calls} (esperado {want_calls})")

    # Every run replays every turn that happened — no summary line, because a
    # case that says only PASSED cannot be read against the spec. A case with no
    # `error:` is a case that passed.
    #
    # A failure STOPS at the step that broke: what would come after the first
    # divergence is a different execution than the one the spec describes, so
    # reporting it would be inventing findings.
    # The turn line always mirrors the SPEC, so the run can be read against it
    # line by line. `happened:` carries what actually occurred, and only appears
    # where the two diverged — a case with no `happened:` is a case that passed.
    out = [f"- {name}:", f"  - user: {q(prompt)}"]
    for i, (kind, want) in enumerate(want_calls):
        got = calls[i] if i < len(calls) else None
        if got == (kind, want):
            out.append(f"  - {kind}: {want}")
        else:
            happened = f"{got[0]}({got[1]})" if got else "nada, respondeu sem chamar tool"
            return False, out + [f"  - {kind}: {want}", f"    happened: {happened}"]

    if extra := calls[len(want_calls):]:
        return False, out + [f"  - happened: {extra[0][0]}({extra[0][1]})"]

    if reply_ok:
        return True, out + [f"  - agent: {q(reply)}"]
    return False, out + [f"  - agent: {q(want_reply)}", f"    happened: {q(reply)}"]


def main() -> int:
    spec_text, _, past_runs = EVAL.read_text(encoding="utf-8").partition("\n---\n")
    spec_text = spec_text.rstrip()
    cases = [(name, turns) for case in yaml.safe_load(spec_text) for name, turns in case.items()]

    results = [run_case(name, turns) for name, turns in cases]
    ok = all(passed for passed, _ in results)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    # Newest run first: it is the one being read. Older ones are kept whole and
    # verbatim below — a run is a measurement, and rewriting a past measurement
    # to fit today's format would erase what actually happened.
    # ponytail: unbounded history. Trim when the file gets tiring to scroll.
    entry = [f'- run: "{stamp}"', f"  verdict: {'PASS' if ok else 'FAIL'}", "  cases:"]
    for _, lines in results:
        entry += [f"  {line}" for line in lines]

    EVAL.write_text(
        f"{spec_text}\n\n---\n" + "\n".join(entry) + "\n\n" + past_runs.lstrip("\n"),
        encoding="utf-8",
    )

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
