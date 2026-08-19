# expectagent

**Your agent will tell you it's working. It has no way of knowing.**

You wrote the test after you saw the output, so the test agrees with whatever came
out. Then someone swaps the model to save money, and nobody can say what stopped
working.

expectagent writes down what the agent must do **before** the agent exists, gets a
human to confirm it, and then checks the built agent against it. This repo *is* the
skill — clone it into your agent's skills folder and it starts using it.

```bash
git clone https://github.com/biliboss/expectagent ~/.claude/skills/expectagent
```

## One file per behaviour

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

Spec above the `---`, every run below it, newest first. **The position of a turn is
the assertion** — a tool called out of order fails even when the final answer is
right — and a run stops at the first divergence, writing what happened under that
exact turn. Past runs are never rewritten; they are measurements.

```bash
uv run scripts/run.py             # run the cases, append the run
uv run scripts/view.py            # the view: what was asked, where it broke
uv run scripts/schema_check.py    # 10 documents accepted, 31 refused
```

## The judge is on a leash

Everything is deterministic except `judge`, and the leash is the part worth
copying. The schema — not a README rule — refuses all three of these:

| refused | why |
|---|---|
| `judge` without `model` | a verdict pinned to no version doesn't reproduce |
| `judge` gating without `min_score` | a judge that can fail you silently is a coin flip |
| a case made only of `judge` | an eval nobody can falsify |

## Why this exists

Tool-call order, trace viewers and matcher libraries already exist and are good —
[agentevals](https://github.com/langchain-ai/agentevals),
[inspect_ai](https://inspect.aisi.org.uk/),
[promptfoo](https://www.promptfoo.dev/),
[autoevals](https://github.com/braintrustdata/autoevals). Three things didn't:

- **The run lives inside the spec file.** Solid prior art — expect tests
  (`ppx_expect`, Rust `expect-test`, cram) — never brought to agent evals.
- **The eval is written before the agent**, so the criterion can't be a description
  of what the agent already outputs.
- **The judge can't pass alone.**

40 deterministic primitives, each named after the library that already named it:
`equals`, `contains: {all, any, none}`, `matches`, `subset`, `similar: {method}`,
`range`, `is_valid`, plus `tools.includes / any_order / exactly / only / must /
never / before / nth` for call order, and `budget` for time and cost. Reusing the
existing name is the rule, not a courtesy — the origin of every one is a column in
[`references/design.md`](references/design.md).

The negative controls in `schema_check.py` are the half that matters. A schema with
only good examples becomes decoration the day someone loosens an
`additionalProperties`, and the good example keeps passing. This is not
hypothetical: the check that proves the schema refuses things was itself written as
`assert v.iter_errors(...)`, and `iter_errors` returns a generator, which is always
truthy. Every negative control passed vacuously for days.

## Honest status

The format, the schema and the checks are real and run today. The interview, the
production sampling and the desktop app are **designed and not built** — the three
candidate first slices are in
[`references/01_system_design_options.md`](references/01_system_design_options.md),
and what is deliberately out of scope is in
[`references/design.md`](references/design.md).

`scripts/run.py` currently talks to one provider (Kimi k3, key read from
`~/kimi_token` at call time). The adapter boundary is designed for in-process, HTTP
and subprocess targets; only the first exists.

Design docs are in Portuguese. Code, schema and this README are in English.

MIT.
