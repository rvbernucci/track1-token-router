from __future__ import annotations

import unittest

from scripts.build_engine_outcome_matrix import _consensus, validate_matrix_row


def judgment(model: str, verdict: str, format_valid: bool = True) -> dict[str, object]:
    return {"judge_model": model, "verdict": verdict, "format_valid": format_valid}


class EngineOutcomeMatrixTests(unittest.TestCase):
    def test_consensus_requires_two_distinct_judges(self) -> None:
        self.assertEqual(_consensus([judgment("one", "correct")])[:2], (None, "insufficient_judges"))
        self.assertEqual(
            _consensus([judgment("one", "correct"), judgment("two", "correct")])[:2],
            (True, "unanimous_correct"),
        )
        self.assertEqual(
            _consensus([judgment("one", "correct"), judgment("two", "incorrect")])[:2],
            (None, "disagree"),
        )

    def test_consensus_filters_judges_using_the_pinned_policy(self) -> None:
        rows = [
            judgment("selected-one", "correct"),
            judgment("selected-two", "correct"),
            judgment("quarantined", "incorrect"),
        ]
        result = _consensus(rows, allowed_judges=("selected-one", "selected-two"))
        self.assertEqual(result[:3], (True, "unanimous_correct", ["selected-one", "selected-two"]))

    def test_matrix_schema_keeps_refusal_distinct_from_failure(self) -> None:
        row = {
            "schema_version": "engine-outcome-matrix-row-v1",
            "task_id": "task",
            "candidate_id": "candidate",
            "engine": "deterministic",
            "engine_version": "v1",
            "model_id": None,
            "status": "refused",
            "correct": None,
            "consensus": "refused",
            "judge_models": [],
            "format_valid": None,
            "latency_ms": 0.1,
            "fireworks_prompt_tokens": 0,
            "fireworks_completion_tokens": 0,
            "runtime_failure": False,
            "peak_memory_mb": 0.0,
            "memory_observed": True,
            "token_ceiling": 0,
            "assessment": {},
            "features": {},
            "regression_split": None,
            "mutation_lineage": None,
            "source": None,
            "missing_reason": "refused",
        }
        validate_matrix_row(row)
        failed = {**row, "status": "runtime_failure", "consensus": "runtime_failure", "runtime_failure": True}
        validate_matrix_row(failed)


if __name__ == "__main__":
    unittest.main()
