import json
import tempfile
import unittest
from pathlib import Path

from scripts.fit_fireworks_matrix_regression import filter_training_rows, load_all_regression_tasks


class FitFireworksMatrixRegressionScriptTests(unittest.TestCase):
    def test_load_all_regression_tasks_merges_repeated_datasets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.jsonl"
            second = Path(tmp) / "second.jsonl"
            first.write_text(
                json.dumps(
                    {
                        "id": "a",
                        "prompt": "Classify sentiment.",
                        "domain": "classification",
                        "tier": "cheap",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            second.write_text(
                json.dumps(
                    {
                        "id": "b",
                        "prompt": "Return only Python code.",
                        "domain": "code_generation",
                        "tier": "strong",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            tasks = load_all_regression_tasks((first, second))

        self.assertEqual(sorted(tasks), ["a", "b"])
        self.assertEqual(tasks["b"].domain, "code_generation")

    def test_filter_training_rows_uses_allowed_models_tasks_and_completed_calls(self) -> None:
        tasks = {
            "a": object(),
            "b": object(),
        }
        rows = [
            _row("a", "accounts/fireworks/models/minimax-m3", ok=True),
            _row("a", "accounts/fireworks/models/minimax-m3", ok=True),
            _row("a", "accounts/fireworks/models/gemma-4-31b-it", ok=False),
            _row("b", "accounts/fireworks/models/kimi-k2p7-code", ok=True),
            _row("missing", "accounts/fireworks/models/minimax-m3", ok=True),
            _row("a", "accounts/fireworks/models/other", ok=True),
        ]

        filtered = filter_training_rows(
            rows,
            tasks,
            [
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
                "accounts/fireworks/models/gemma-4-31b-it",
            ],
        )

        self.assertEqual(
            [(row["id"], row["model"]) for row in filtered],
            [
                ("a", "accounts/fireworks/models/minimax-m3"),
                ("b", "accounts/fireworks/models/kimi-k2p7-code"),
            ],
        )

    def test_filter_training_rows_can_include_failed_calls_for_access_drills(self) -> None:
        tasks = {"a": object()}
        rows = [_row("a", "accounts/fireworks/models/gemma-4-31b-it", ok=False)]

        filtered = filter_training_rows(
            rows,
            tasks,
            ["accounts/fireworks/models/gemma-4-31b-it"],
            include_failed_calls=True,
        )

        self.assertEqual(len(filtered), 1)


def _row(task_id: str, model: str, *, ok: bool) -> dict[str, object]:
    return {
        "id": task_id,
        "model": model,
        "ok": ok,
        "valid": ok,
        "estimated_cost_usd": 0.0001,
        "latency_ms": 1000,
        "request_options": {"user": "test"},
    }


if __name__ == "__main__":
    unittest.main()
