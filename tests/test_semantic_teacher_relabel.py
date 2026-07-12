import unittest

from scripts.benchmark_teacher_gate_ml import _ridge_artifact, _runtime_prediction_rows
from scripts.build_functiongemma_teacher_consensus import _consensus, _format_complexity
from scripts.relabel_semantic_teachers import _validated_item


class SemanticTeacherRelabelTests(unittest.TestCase):
    def test_runtime_predictions_preserve_roles_and_drop_invalid_schema(self) -> None:
        ledger = [
            {"task_id": "a", "role": "fit", "mechanical_features": {}},
            {"task_id": "b", "role": "protected_holdout", "mechanical_features": {}},
        ]
        scores = {
            "deterministic_fit": 1, "reasoning_demand": 2, "knowledge_uncertainty": 3,
            "generation_demand": 4, "format_complexity": 5,
        }
        rows = _runtime_prediction_rows(ledger, [
            {"id": "a", "prediction": {"intent": "sentiment", "scores": scores}},
            {"id": "b", "prediction": None},
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["role"], "fit")
        self.assertEqual(rows[0]["teacher_intent"], "sentiment")

    def test_ridge_artifact_preserves_runtime_parameters(self) -> None:
        class Row:
            def tolist(self):
                return [0.25, -0.75]

        class Matrix:
            def __getitem__(self, _index):
                return Row()

        class Scaler:
            mean_ = [1.0, 2.0]
            scale_ = [3.0, 4.0]

        class Classifier:
            intercept_ = [0.5]
            coef_ = Matrix()

        class Pipeline:
            named_steps = {"standardscaler": Scaler(), "logisticregression": Classifier()}

        artifact = _ridge_artifact(Pipeline(), 0.8)
        self.assertEqual(artifact["coefficients"], [0.5, 0.25, -0.75])
        self.assertEqual(artifact["normalization"]["scale"], [3.0, 4.0])
        self.assertEqual(artifact["threshold"], 0.8)

    def test_teacher_item_normalizes_auxiliary_sub_intent_from_another_intent(self) -> None:
        row = self._teacher(intent="sentiment", sub_intent="python_debug")
        self.assertIsNone(_validated_item(row)["sub_intent"])

    def test_consensus_blends_semantics_but_engine_owns_format(self) -> None:
        left = self._teacher()
        right = self._teacher()
        left.update({"reasoning_demand": 2, "difficulty": 1, "knowledge_requirement": 2})
        right.update({"reasoning_demand": 6, "difficulty": 3, "knowledge_requirement": 6})
        assessment = _consensus(left, right, self._mechanical(strict=1.0, json_requested=1.0))
        self.assertEqual(assessment.intent.value, "code_debugging")
        self.assertEqual(assessment.scores.reasoning_demand, 4)
        self.assertEqual(assessment.scores.knowledge_uncertainty, 3)
        self.assertEqual(assessment.scores.format_complexity, 5)

    def test_format_complexity_is_bounded(self) -> None:
        features = self._mechanical(strict=1.0, json_requested=1.0)
        for name in (
            "mechanical.shape.code", "mechanical.shape.json", "mechanical.shape.list",
            "mechanical.verifier.code_syntax", "mechanical.verifier.json_structure",
        ):
            features[name] = 1.0
        features["mechanical.sentence_limit"] = 1.0
        features["mechanical.word_limit"] = 1.0
        self.assertEqual(_format_complexity(features), 10)

    @staticmethod
    def _teacher(*, intent: str = "code_debugging", sub_intent: str = "python_debug") -> dict:
        return {
            "task_id": "task-1", "intent": intent, "sub_intent": sub_intent,
            "difficulty": 1, "reasoning_demand": 2, "generation_demand": 3,
            "knowledge_requirement": 2, "ambiguity": 0, "deterministic_fit": 8,
            "confidence": 90,
        }

    @staticmethod
    def _mechanical(*, strict: float, json_requested: float) -> dict:
        return {
            "mechanical.strict_format": strict,
            "mechanical.json_requested": json_requested,
            "mechanical.shape.code": 1.0,
            "mechanical.shape.json": 0.0,
            "mechanical.shape.list": 0.0,
            "mechanical.sentence_limit": 0.0,
            "mechanical.word_limit": 0.0,
            "mechanical.verifier.code_syntax": 0.0,
            "mechanical.verifier.json_structure": 0.0,
        }


if __name__ == "__main__":
    unittest.main()
