---
name: expectagent
description: "Write down what an agent must do BEFORE building it, show it to the person to confirm, then check the built agent against it — deterministic asserts plus a pinned-model judge, in one readable file that also stores every run. Use when someone wants to build an agent and does not know where to start, when an agent broke and nobody knows what changed, when swapping models and asking what was lost, or when asked to test/eval/verify an agent, a prompt or an LLM flow. Triggers on: build me an agent, does it still work, it worked yesterday, check my agent, eval, test the agent, swap the model, what did I lose."
---

# expectagent

Someone wants an agent and does not know where to start. You write down what it
must do, show it to them, and only then build it — so the criterion is never a
description of what your code already happens to output.

## The loop

1. **Interview, do not guess.** Ask only what you are below 95% sure about. One
   question at a time, with options when options exist. Write every answer into
   the eval file as you go.
2. **Show it, get a yes.** Run `scripts/web.py` and let the person read the case.
   They confirm, or they fix one line. Never move on from a case they have not
   seen.
3. **Then build or plug.** Write the agent, or point at one that exists. The
   framework is a detail — the criterion is already written.
4. **Run it.** `scripts/run.py`. It stops at the first turn that diverges and
   writes what actually happened under that turn.
5. **A case that passes on its first run is suspect.** It either describes what
   the agent already did, or the worry behind it was not real. Say so, and either
   tighten the assert or record that the worry does not hold. Never post-process
   the agent's reply to make a run green.

## The file

One YAML, two documents. The spec above `---`, the runs below it, newest first.
Past runs are measurements: never rewrite one.

```yaml
- ping_pong:
  - user: ping
  - tool: knowledge.search
    returns: {contains: runbook}
  - agent: pong
---
- run: "2026-08-19T14:02Z"
  verdict: FAILED
  target: haiku-4.5
  cases:
  - ping_pong:
    - user: ping
    - agent: pong
      happened: "veio 'Pong! 🏓'"
```

The position of a turn IS the assertion: turn 2 happening before turn 1 fails,
even when the final answer is right.

## The asserts

Every assert is deterministic — same input, same verdict — except `judge`, and
`judge` wears a leash. `../expectagent.schema.json` is the contract: point your
editor at it and the file validates as you type.

    # yaml-language-server: $schema=../expectagent.schema.json

The full table, with where each primitive came from, is in
`../docs/design.md`. Three rules the schema enforces so you cannot get them
wrong:

- **`judge.model` is required**, with a version. A verdict that does not
  reproduce does not measure.
- **Without `judge.min_score` a judge is advisory** — it reports, it does not
  fail anyone.
- **A case cannot consist only of a judge.** A judge alone is an eval that cannot
  be falsified, so the schema refuses it.

## Scripts

| script | what it does |
|---|---|
| `scripts/run.py` | runs the cases against a target, appends the run |
| `scripts/web.py` | serves the view — what was asked, and where it broke |
| `../schema_check.py` | proves the contract accepts and REFUSES; 31 negative controls |

Nothing here needs a server, an account, or OpenTelemetry. If it ever does, that
is a bug in this skill and not a requirement of the format.
