import unittest

from scripts.benchmark_e2b_runtime_clusters import _approved_clusters, _selection_metrics
from scripts.benchmark_teacher_gate_ml import _runtime_prediction_rows
from scripts.build_scale789_prediction_union import prediction_union
from tempfile import TemporaryDirectory
from pathlib import Path
import json


class E2BRuntimeClusterTests(unittest.TestCase):
    def test_clusters_require_support_precision_and_wilson(self) -> None:
        rows = [{"target": 1} for _ in range(30)] + [{"target": 0} for _ in range(2)]
        labels = [4] * len(rows)
        self.assertEqual(_approved_clusters(rows, labels), {4})
        metrics = _selection_metrics(rows, labels, {4})
        self.assertEqual(metrics["selected"], 32)
        self.assertEqual(metrics["correct"], 30)

    def test_small_perfect_cluster_is_not_promoted(self) -> None:
        rows = [{"target": 1} for _ in range(10)]
        self.assertEqual(_approved_clusters(rows, [1] * 10), set())

    def test_runtime_predictions_can_cover_a_lineage_safe_ledger_subset(self) -> None:
        ledger = [
            {"task_id": "a", "target": 1},
            {"task_id": "b", "target": 0},
        ]
        predictions = [{
            "id": "a",
            "prediction": {
                "intent": "sentiment",
                "scores": {
                    "deterministic_fit": 1,
                    "reasoning_demand": 1,
                    "knowledge_uncertainty": 1,
                    "generation_demand": 1,
                    "format_complexity": 1,
                },
            },
        }]
        rows = _runtime_prediction_rows(ledger, predictions, allow_subset=True)
        self.assertEqual([row["task_id"] for row in rows], ["a"])

    def test_prediction_union_normalizes_runtime_shapes(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            rows = [
                {"id": "a", "prediction": {"intent": "sentiment", "scores": {"x": 1}}},
                {"task_id": "b", "assessment": {"intent": "ner", "scores": {"x": 2}}},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            union = prediction_union([path])
            self.assertEqual([row["id"] for row in union], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
