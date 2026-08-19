#!/usr/bin/env python3
"""A stand-in target, so the runner is proven end to end without a real agent.

It exists to exercise the ADAPTER CONTRACT, not to be an agent: it reads
`{"input": ...}` on stdin and prints `{"reply": ..., "calls": [...]}`. Any real
agent that can print that shape is a target.

It answers differently per input so one file can drive the cases that must pass
and the ones that must fail.
"""

import json
import sys

ANSWERS = {
    # Right answer, right order.
    "ping": {"reply": "pong", "calls": [{"name": "knowledge.search", "input": "ping"}]},
    # Right final answer, WRONG order: it sends before it looks anything up.
    "ping out of order": {
        "reply": "pong",
        "calls": [
            {"name": "whatsapp.send", "input": "pong"},
            {"name": "knowledge.search", "input": "ping"},
        ],
    },
    # Right shape, forbidden words in the reply.
    "ping with flourish": {
        "reply": "Pong! 🏓",
        "calls": [{"name": "knowledge.search", "input": "ping"}],
    },
}

REQUEST = json.load(sys.stdin)
print(json.dumps(ANSWERS.get(REQUEST["input"], {"reply": "", "calls": []})))
