from __future__ import annotations

from scripts.judge_fireworks_champion_v3 import deterministic_verdict, wilson


def test_judge_fireworks_champion_v3_exact_mechanical_precedes_semantic_judge():
    task = {"evidence_mode": "mechanical", "output_shape": "number"}
    reference = {"answer_mode": "exact", "reference_answer": "-40"}
    good = {"ok": True, "answer": "-40", "finish_reason": "stop"}
    bad = {"ok": True, "answer": "-39", "finish_reason": "stop"}
    assert deterministic_verdict(task, good, reference) == {"verdict": "correct", "hard": True, "reason": "normalized_exact"}
    assert deterministic_verdict(task, bad, reference)["verdict"] == "incorrect"


def test_judge_fireworks_champion_v3_semantic_rows_are_queued_blind():
    task = {"evidence_mode": "semantic", "output_shape": "free_text"}
    response = {"ok": True, "answer": "A supported explanation.", "finish_reason": "stop"}
    result = deterministic_verdict(task, response, {"reference_answer": "Reference"})
    assert result == {"verdict": "uncertain", "hard": False, "reason": "semantic_or_complex_contract"}
    assert 0 < wilson(90, 100) < 0.9

