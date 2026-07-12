from __future__ import annotations

import json

from scripts.run_fireworks_champion_v3 import AtomicLedger, Budget, DOMAIN, MODELS


def test_run_fireworks_champion_v3_budget_cost_and_reserve_are_explicit():
    budget = Budget(18.0, 10.0, 30.0, {MODELS[0]: (0.95, 4.0), MODELS[1]: (0.3, 1.2)})
    assert budget.cost(MODELS[0], 1_000_000, 1_000_000) == 4.95
    assert budget.cost(MODELS[1], 1_000_000, 1_000_000) == 1.5
    assert budget.available_usd - budget.reserve_usd >= budget.hard_usd


def test_run_fireworks_champion_v3_atomic_ledger_is_valid_resumable_jsonl(tmp_path):
    path = tmp_path / "responses.jsonl"
    ledger = AtomicLedger(path)
    ledger.append({"task_id": "t1", "model": MODELS[0], "ok": True})
    ledger.append({"task_id": "t1", "model": MODELS[1], "ok": True})
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert {(row["task_id"], row["model"]) for row in rows} == {("t1", MODELS[0]), ("t1", MODELS[1])}
    assert set(DOMAIN) == {"factual_qa", "math_reasoning", "sentiment", "summarization", "ner", "code_debugging", "logic_puzzle", "code_generation"}
