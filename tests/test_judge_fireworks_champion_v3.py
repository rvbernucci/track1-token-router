from __future__ import annotations

from scripts.judge_fireworks_champion_v3 import _mcnemar_exact, _model_metrics, deterministic_verdict, wilson


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


def test_judge_fireworks_champion_v3_model_metrics_count_accuracy_and_tokens():
    rows = [{"task_id": "a", "model": "m", "correct": True}, {"task_id": "b", "model": "m", "correct": False}]
    responses = {
        ("a", "m"): {"usage": {"prompt": 3, "completion": 2, "total": 5}, "latency_ms": 10},
        ("b", "m"): {"usage": {"prompt": 4, "completion": 3, "total": 7}, "latency_ms": 20},
    }
    metrics = _model_metrics(rows, responses)
    assert metrics["accuracy"] == 0.5
    assert metrics["tokens"] == 12
    assert metrics["prompt_tokens"] == 7
    assert _mcnemar_exact(7, 22) < 0.01
    assert _mcnemar_exact(8, 8) == 1.0
