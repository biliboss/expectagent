# expectagent

**Write what the agent must do before you build the agent.**

Not a CLI, not a platform: a skill your coding agent loads, plus one readable file
per behaviour. Install by copying `skill/` into your agent's skills folder.

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

Spec above the `---`, every run below it, newest first. The position of a turn IS
the assertion — a tool called out of order fails even when the final answer is
right — and a run stops at the first divergence and writes what happened under
that exact turn.

## Why this exists

Tool-call order, trace viewers and matcher libraries already exist and are good:
[agentevals](https://github.com/langchain-ai/agentevals),
[inspect_ai](https://inspect.aisi.org.uk/),
[promptfoo](https://www.promptfoo.dev/),
[autoevals](https://github.com/braintrustdata/autoevals). Three things did not
exist, and they are the point:

- **The run lives inside the spec file.** The prior art is expect tests
  (`ppx_expect`, Rust `expect-test`, cram) — solid, and never brought to agent
  evals.
- **The eval is written before the agent.** So the criterion cannot be a
  description of what the agent already outputs.
- **The judge cannot pass alone.** `judge.model` must be pinned to a version,
  a judge without `min_score` is advisory, and a case made only of a judge is
  refused by the schema — because it cannot be falsified.

## The assert contract

40 deterministic primitives in one schema, each named after the library that
already named it — `equals`, `contains: {all, any, none}`, `matches`, `subset`,
`similar: {method}`, `range`, `is_valid`, plus `tools.includes / any_order /
exactly / only / must / never / before / nth` for call order, `budget` for time
and cost, and `judge` for what only a model can weigh.

Point your editor at it and the file validates as you type:

```yaml
# yaml-language-server: $schema=./expectagent.schema.json
```

```bash
uv run schema_check.py    # 10 documents accepted, 31 negative controls refused
```

The negative controls are the part that matters. A schema with only good examples
becomes decoration the day someone loosens an `additionalProperties`, and the good
example keeps passing.

## Layout

```
skill/           SKILL.md + scripts — this is what you copy
expectagent.schema.json   the contract
schema_check.py  proves the contract accepts AND refuses
examples/        a working eval, and the toy skill it exercises
docs/            the design: the journey, the assert table, the boundaries
```

## Status

Early. The format, the schema and the checks are real and run; the interview, the
production sampling and the desktop app are designed and not built — see
[`docs/01_system_design_options.md`](docs/01_system_design_options.md) for the
three candidate first slices, and
[`docs/design.md`](docs/design.md) for what is deliberately out of scope.

The design docs are in Portuguese; the code, the schema and this README are in
English.

MIT.
