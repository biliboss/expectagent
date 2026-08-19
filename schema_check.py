# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema", "pyyaml"]
# ///
"""Prova que o schema aceita o que tem que aceitar e RECUSA o que tem que recusar.

    uv run schema_check.py

O que importa aqui sao os controles negativos. Um schema que so tem exemplo bom
passa a ser decoracao no dia em que alguem afrouxa um `additionalProperties`, e
ninguem descobre — porque o exemplo bom continua passando.
"""

import json
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SCHEMA = json.loads((Path(__file__).parent / "expectagent.schema.json").read_text())

# Um turno: entra isso, sai aquilo. A forma mais curta que o formato tem.
UM_TURNO = """
- ping_pong:
  - user: ping
  - agent: pong
"""

# Multiturno: a ordem das tools E a assercao, e a tool roda de verdade.
MULTITURNO = """
- ping_pong_com_conhecimento:
  - user: ping
  - tool: knowledge.search
    args: {q: ping}
    returns:
      contains: runbook
  - tool: whatsapp.send
    times: 1
  - agent:
      contains: {all: [pong], none: ["🏓", "Pong!"]}
"""

# O andaime: a tool ainda esta mocada, e por isso nao afirma nada sobre ela.
MOCADO = """
- ping_pong_mocado:
  - user: ping
  - tool: knowledge.search
    mock: "pong vem do runbook"
  - agent: pong
"""

# A run: mesma forma do spec, mais `happened:` no turno que quebrou. Nada depois dele.
RUNS = """
- run: "2026-08-19T14:02Z"
  verdict: FAILED
  target: haiku-4.5
  cases:
  - ping_pong:
    - user: ping
    - agent: pong
      happened: "veio 'Pong! 🏓'"
"""

# A sequencia de tools, com as primitivas se compondo: ordenado e permissivo,
# allowlist, par ordenado, e posicao — tudo no mesmo caso.
SEQUENCIA = """
- ping_pong_com_ordem:
  - user: ping
  - tools:
      includes: [knowledge.search, whatsapp.send]
      only: [knowledge.search, whatsapp.send, clock.now]
      never: [db.drop]
      before:
      - {first: knowledge.search, then: whatsapp.send}
      nth:
      - {index: -1, tool: whatsapp.send, args: {to: "+100000000"}}
      times: {lte: 4}
  - agent: pong
"""

# Antes de comparar: recorta, normaliza, e so entao afirma. `Pong! 🏓` passa como
# `pong` porque a decisao esta ESCRITA, nao escondida no runner.
PRE_COMPARACAO = """
- resposta_normalizada:
  - user: ping
  - agent:
      prepare: {normalize: [case, emoji, whitespace]}
      equals: pong
- multipla_escolha:
  - user: "qual a capital? A) Lima B) Quito"
  - agent:
      prepare: {extract: "Answer:\\\\s*([A-D])"}
      one_of: [A, B, C, D]
"""

ORCAMENTO = """
- ping_pong_barato:
  - user: ping
  - agent: pong
  - budget:
      max_duration_ms: 1800
      max_cost_usd: 0.02
"""

COMBINADORES = """
- resposta_flexivel:
  - user: ping
  - agent:
      all_of:
      - {contains: {all: [pong]}}
      - {not: {contains: {any: ["🏓"]}}}
      - {length: {lte: 40}}
"""


# O juiz: modelo pinado, e o caso tem assert deterministico junto — juiz sozinho
# nao falseia, e o schema recusa.
JUIZ = """
- resposta_com_juiz:
  - user: "explica o que e um agente"
  - agent:
      length: {lte: 600}
  - judge:
      model: claude-haiku-4-5-20251001
      preset: conciseness
      min_score: 0.7
  - judge:
      model: claude-haiku-4-5-20251001
      rubric: "A resposta explica sem usar jargao de framework?"
      score: boolean
"""

# Parecido por metodo declarado, e validacao de formato com schema.
SIMILAR_E_FORMATO = """
- saida_estruturada:
  - user: "devolve o json do pedido"
  - agent:
      is_valid:
        format: json
        schema: {type: object, required: [preco]}
  - agent:
      similar: {to: "apartamento de 3 quartos", method: rouge_l, min: 0.6}
"""

BONS = {
    "um turno": UM_TURNO,
    "multiturno": MULTITURNO,
    "mocado": MOCADO,
    "runs": RUNS,
    "sequencia de tools": SEQUENCIA,
    "extract e normalize": PRE_COMPARACAO,
    "orcamento": ORCAMENTO,
    "combinadores": COMBINADORES,
    "juiz com trela": JUIZ,
    "similar e formato": SIMILAR_E_FORMATO,
}

RUINS = {
    "verbo que nao existe": "- x:\n  - usuario: ping\n",
    "turno com dois verbos": "- x:\n  - user: ping\n    agent: pong\n",
    "mock e returns juntos (tautologia)": (
        "- x:\n  - user: ping\n  - tool: t\n    mock: a\n    returns: a\n"
    ),
    "matcher inventado": "- x:\n  - user: ping\n  - agent: {contem: pong}\n",
    "matcher vazio": "- x:\n  - user: ping\n  - agent: {}\n",
    "caso com dois nomes": "- a:\n  - user: ping\n  b:\n  - user: ping\n",
    "caso sem turno": "- x: []\n",
    "close_to sem delta": "- x:\n  - user: ping\n  - agent: {close_to: {value: 1}}\n",
    "veredito que nao existe": (
        '- run: "2026-08-19T14:02Z"\n  verdict: MAYBE\n  cases: []\n'
    ),
    "campo a mais na run": (
        '- run: "2026-08-19T14:02Z"\n  verdict: PASS\n  cases: []\n  nota: oi\n'
    ),
    "primitiva de ordem inventada": (
        "- x:\n  - user: ping\n  - tools: {in_order: [a, b]}\n"
    ),
    "tools vazio": "- x:\n  - user: ping\n  - tools: {}\n",
    "before sem o par": "- x:\n  - user: ping\n  - tools: {before: [{first: a}]}\n",
    "nth sem tool": "- x:\n  - user: ping\n  - tools: {nth: [{index: 1}]}\n",
    "only com objeto em vez de nome": (
        "- x:\n  - user: ping\n  - tools: {only: [{tool: a}]}\n"
    ),
    "normalize com passo que nao existe": (
        "- x:\n  - user: ping\n  - agent: {normalize: [lowercase]}\n"
    ),
    "is_type com tipo inventado": (
        "- x:\n  - user: ping\n  - agent: {is_type: dict}\n"
    ),
    "all_of com um item so": (
        "- x:\n  - user: ping\n  - agent: {all_of: [{contains: pong}]}\n"
    ),
    "budget com chave desconhecida": (
        "- x:\n  - user: ping\n  - budget: {max_ms: 10}\n"
    ),
    "budget zerado": "- x:\n  - user: ping\n  - budget: {max_duration_ms: 0}\n",
    "juiz sem modelo pinado": (
        "- x:\n  - user: ping\n  - agent: pong\n  - judge: {preset: factuality}\n"
    ),
    "juiz sem criterio nenhum": (
        "- x:\n  - user: ping\n  - agent: pong\n  - judge: {model: claude-haiku-4-5-20251001}\n"
    ),
    "juiz com preset inventado": (
        "- x:\n  - user: ping\n  - agent: pong\n"
        "  - judge: {model: claude-haiku-4-5-20251001, preset: vibes}\n"
    ),
    "caso SO com juiz (nao falseia)": (
        "- x:\n  - user: ping\n  - judge: {model: claude-haiku-4-5-20251001, preset: correctness}\n"
    ),
    "min_score fora de 0..1": (
        "- x:\n  - user: ping\n  - agent: pong\n"
        "  - judge: {model: claude-haiku-4-5-20251001, preset: correctness, min_score: 7}\n"
    ),
    "contains vazio": "- x:\n  - user: ping\n  - agent: {contains: {}}\n",
    "similar sem piso": (
        "- x:\n  - user: ping\n  - agent: {similar: {to: pong, method: bleu}}\n"
    ),
    "similar com metodo inventado": (
        "- x:\n  - user: ping\n  - agent: {similar: {to: pong, method: vibes, min: 0.5}}\n"
    ),
    "is_valid com formato inventado": (
        "- x:\n  - user: ping\n  - agent: {is_valid: {format: toml}}\n"
    ),
    "not_contains, que virou contains.none": (
        "- x:\n  - user: ping\n  - agent: {not_contains: pong}\n"
    ),
    "peso zero": "- x:\n  - user: ping\n  - agent: {equals: pong, weight: 0}\n",
}


def check_doc_table() -> None:
    """Toda primitiva citada na tabela do docs/design.md existe no schema.

    Sem isto, a tabela vira folheto: ela promete `tools.after`, ninguem roda nada,
    e o primeiro usuario descobre que o campo nunca existiu. Linha ~~riscada~~ e
    exclusao declarada, e por isso nao entra na cobranca.
    """
    d = SCHEMA["$defs"]
    have = (
        set(d["matcher"]["properties"])
        | {f"tools.{k}" for k in d["toolsAssert"]["properties"]["tools"]["properties"]}
        | {f"budget.{k}" for k in d["budgetAssert"]["properties"]["budget"]["properties"]}
        | set(d["scoreAssert"]["properties"])
        | {f"judge.{k}" for k in d["judgeAssert"]["properties"]["judge"]["properties"]}
        | {f"prepare.{k}" for k in d["prepare"]["properties"]}
        | set(d["toolTurn"]["properties"])
    )

    table = (Path(__file__).parent / "docs" / "design.md").read_text()
    table = table.split("## O contrato de asserts")[1].split("\n## ")[0]

    promised: set[str] = set()
    for row in table.splitlines():
        cell = row.split("|")[1] if row.count("|") > 2 else ""
        if "~~" in cell:  # exclusao declarada
            continue
        promised |= set(re.findall(r"`([a-z_.]+)`", cell))

    missing = sorted(p for p in promised if p not in have)
    assert not missing, f"a tabela promete o que o schema nao tem: {missing}"
    print(f"OK: as {len(promised)} primitivas da tabela existem no schema")


def main() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    v = Draft202012Validator(SCHEMA)
    print("OK: o schema e um JSON Schema 2020-12 valido")

    for nome, doc in BONS.items():
        errs = sorted(v.iter_errors(yaml.safe_load(doc)), key=str)
        assert not errs, f"aceitava e recusou — {nome}: {errs[0].message}"
        print(f"OK: aceita {nome}")

    for nome, doc in RUINS.items():
        # list(), nao o gerador: `iter_errors` devolve um generator, e generator e
        # SEMPRE truthy. Escrito como `assert v.iter_errors(...)` isto passou a vazio
        # por dezenas de rodadas, verde e medindo nada — o proprio bug que este
        # projeto existe pra pegar.
        assert list(v.iter_errors(yaml.safe_load(doc))), f"CONTROLE NEGATIVO FUROU — {nome}"
        print(f"OK: recusa {nome}")

    check_doc_table()
    print(f"\n{len(BONS)} aceitos, {len(RUINS)} recusados.")


if __name__ == "__main__":
    main()
