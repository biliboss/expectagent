---
name: expectagent
description: Write down what an agent must do BEFORE building it, show it to the person to confirm, then check the built agent against it. Use when someone wants an agent and doesn't know where to start, when an agent broke and nobody knows what changed, when swapping models and asking what was lost, or on any 'test/eval/verify my agent' phrasing.
---

Write the expected behaviour before the agent exists, get a human to confirm it, and only then build. A criterion written after the fact describes what your code already outputs; it asserts nothing.

Interview first, and ask only what you are below 95% sure about — one question per round, with options when options exist, and your recommendation stated. Facts are your job: read the repo, the prompt, the tool list. Decisions are the person's. Write each answer into the eval file as it arrives, never at the end.

Then show it and get a yes. Run `uv run scripts/view.py` and let them read the case. They confirm, or they fix one line. Never leave a case they have not seen.

Only then build the agent, or point at one that exists. Run it with `uv run scripts/run.py`. It stops at the first turn that diverges and writes what actually happened under that turn.

**A case that passes on its first run is suspect.** It either describes what the agent already did, or the worry behind it was not real. Say which, then tighten the assert or record that the worry does not hold. Never post-process the agent's reply to turn a run green.

One YAML per behaviour. Spec above the `---`, runs below it, newest first. Past runs are measurements — never rewrite one.

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
      happened: "came back as 'Pong! 🏓'"
```

The position of a turn IS the assertion: a tool called out of order fails even when the final answer is right.

Point the file at the contract and the editor validates as you type:

```yaml
# yaml-language-server: $schema=./expectagent.schema.json
```

Every assert is deterministic except `judge`, and three rules the schema enforces so you cannot get them wrong: `judge.model` must be pinned to a version, a judge without `min_score` is advisory, and a case made only of a judge is refused — it cannot be falsified. The full table of primitives, each named after the library that already named it, is in `references/design.md`.

Nothing here needs a server, an account, or OpenTelemetry. If it ever does, that is a bug in this skill and not a requirement of the format.

You are done when every case in the file has been confirmed by a human and has at least one recorded run that failed before it passed.
