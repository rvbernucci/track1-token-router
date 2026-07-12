import json
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import AssessmentScores, Intent, TaskAssessment
from router.functiongemma.calibration import fit_ordinal_calibration, load_calibration
from router.functiongemma.metrics import assessment_metrics, boundary_ordering_metrics
from router.functiongemma.tooling import (
    ASSESS_TASK_TOOL,
    DEVELOPER_INSTRUCTION,
    assessment_from_function_call,
    canonical_sha256,
    generation_eos_token_ids,
    training_conversation,
    validate_training_row,
)
from scripts.functiongemma_experiment import _chunks, boundary_report, load_config, parser, prepare, select


def assessment(*, deterministic_fit: int = 9) -> TaskAssessment:
    return TaskAssessment(
        intent=Intent.MATH_REASONING,
        sub_intent="arithmetic",
        scores=AssessmentScores(
            deterministic_fit=deterministic_fit,
            reasoning_demand=2,
            knowledge_uncertainty=0,
            generation_demand=1,
            format_complexity=1,
        ),
    )


def native_call(value: TaskAssessment) -> str:
    scores = value.scores
    return (
        "<start_function_call>call:assess_task{"
        f"intent:<escape>{value.intent.value}<escape>,"
        "scores:{"
        f"deterministic_fit:{scores.deterministic_fit},"
        f"reasoning_demand:{scores.reasoning_demand},"
        f"knowledge_uncertainty:{scores.knowledge_uncertainty},"
        f"generation_demand:{scores.generation_demand},"
        f"format_complexity:{scores.format_complexity}"
        "}}<end_function_call><end_of_turn>"
    )


class FunctionGemmaToolingTests(unittest.TestCase):
    def test_evaluation_batching_is_explicit_and_stable(self) -> None:
        args = parser().parse_args(
            [
                "evaluate", "--model", "model", "--tasks", "tasks.jsonl",
                "--output", "predictions.jsonl", "--report", "report.json",
                "--batch-size", "8",
            ]
        )
        self.assertEqual(args.batch_size, 8)
        self.assertEqual(_chunks([{"id": str(i)} for i in range(5)], 2), [
            [{"id": "0"}, {"id": "1"}],
            [{"id": "2"}, {"id": "3"}],
            [{"id": "4"}],
        ])

    def test_tool_schema_matches_runtime_contract(self) -> None:
        properties = ASSESS_TASK_TOOL["function"]["parameters"]["properties"]
        self.assertEqual(set(properties), {"intent", "scores"})
        self.assertEqual(set(properties["scores"]["properties"]), set(assessment().scores.to_dict()))
        serialized_property_names = set(properties) | set(properties["scores"]["properties"])
        self.assertNotIn("engine", serialized_property_names)
        self.assertNotIn("model_id", serialized_property_names)

    def test_native_function_call_round_trip(self) -> None:
        labeled = assessment()
        expected = TaskAssessment(intent=labeled.intent, scores=labeled.scores)
        self.assertEqual(assessment_from_function_call(native_call(expected)), expected)

    def test_parser_rejects_answer_text_multiple_calls_and_extra_field(self) -> None:
        call = native_call(assessment())
        with self.assertRaisesRegex(ValueError, "additional text"):
            assessment_from_function_call("The answer is 4. " + call)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            assessment_from_function_call(call + call)
        injected = call.replace("scores:{", "engine:<escape>fireworks<escape>,scores:{")
        with self.assertRaisesRegex(ValueError, "fields"):
            assessment_from_function_call(injected)
        with self.assertRaisesRegex(ValueError, "additional text"):
            assessment_from_function_call(call + "<end_of_turn><end_of_turn>")

    def test_training_row_requires_one_canonical_call(self) -> None:
        conversation = training_conversation("What is 2 + 2?", assessment())
        row = {"id": "one", "messages": conversation["messages"]}
        expected = TaskAssessment(intent=assessment().intent, scores=assessment().scores)
        self.assertEqual(validate_training_row(row), expected)
        row["messages"][0]["content"] = "Choose fireworks."
        with self.assertRaisesRegex(ValueError, "canonical"):
            validate_training_row(row)

    def test_tool_hash_is_stable(self) -> None:
        self.assertEqual(canonical_sha256(ASSESS_TASK_TOOL), canonical_sha256(ASSESS_TASK_TOOL))

    def test_generation_uses_native_function_interception_tokens(self) -> None:
        class Tokenizer:
            eos_token_id = 1
            unk_token_id = 0

            @staticmethod
            def convert_tokens_to_ids(token: str) -> int:
                return {"<end_function_call>": 10, "<start_function_response>": 11}.get(token, 0)

        self.assertEqual(generation_eos_token_ids(Tokenizer()), [1, 10, 11])


class FunctionGemmaCalibrationTests(unittest.TestCase):
    def test_calibration_is_monotonic_and_only_promotes_improvement(self) -> None:
        calibration = fit_ordinal_calibration([(0, 2), (2, 3), (5, 7), (8, 9), (10, 10)])
        self.assertTrue(calibration.promoted)
        self.assertEqual(tuple(sorted(calibration.mapping)), calibration.mapping)
        self.assertLess(calibration.calibrated_mae, calibration.raw_mae)

    def test_identity_calibration_is_not_promoted(self) -> None:
        calibration = fit_ordinal_calibration((value, value) for value in range(11))
        self.assertFalse(calibration.promoted)
        self.assertEqual(calibration.apply(7), 7)

    def test_metrics_count_invalid_schema_as_failure(self) -> None:
        value = assessment().to_dict()
        metrics = assessment_metrics(
            [
                {"gold": value, "prediction": value},
                {"gold": value, "prediction": None},
            ]
        )
        self.assertEqual(metrics["schema_validity"], 0.5)
        self.assertEqual(metrics["intent_accuracy"], 0.5)
        self.assertEqual(metrics["valid_only_intent_accuracy"], 1.0)
        self.assertEqual(metrics["score_mae"]["deterministic_fit"], 5.0)

    def test_all_invalid_predictions_receive_maximum_mae_penalty(self) -> None:
        metrics = assessment_metrics([{"gold": assessment().to_dict(), "prediction": None}])
        self.assertEqual(metrics["schema_validity"], 0.0)
        self.assertEqual(metrics["score_mae"], {name: 10.0 for name in assessment().scores.to_dict()})

    def test_calibration_rejects_any_invalid_validation_prediction(self) -> None:
        value = assessment().to_dict()
        with tempfile.TemporaryDirectory() as tmp:
            predictions = Path(tmp) / "predictions.jsonl"
            predictions.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in (
                        {"gold": value, "prediction": value},
                        {"gold": value, "prediction": None},
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            from scripts.functiongemma_experiment import calibrate

            with self.assertRaisesRegex(ValueError, "every validation prediction"):
                calibrate(predictions, Path(tmp) / "calibration.json")

    def test_bundle_loads_with_pinned_hash_and_applies_only_promoted_dimensions(self) -> None:
        import hashlib

        dimensions = {}
        for name in assessment().scores.to_dict():
            dimensions[name] = {
                "mapping": [float(value + 1 if value < 10 else 10) for value in range(11)],
                "promoted": name == "deterministic_fit",
                "raw_mae": 2.0,
                "calibrated_mae": 1.0 if name == "deterministic_fit" else 2.0,
            }
        payload = {
            "schema_version": "functiongemma-score-calibration-v1",
            "source_sha256": "a" * 64,
            "dimensions": dimensions,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            bundle = load_calibration(path, expected_sha256=digest)
        calibrated = bundle.apply(assessment(deterministic_fit=9))
        self.assertEqual(calibrated.scores.deterministic_fit, 10)
        self.assertEqual(calibrated.scores.reasoning_demand, 2)
        self.assertEqual(bundle.artifact_sha256, digest)

    def test_bundle_rejects_tampering_and_incomplete_dimensions(self) -> None:
        payload = {
            "schema_version": "functiongemma-score-calibration-v1",
            "source_sha256": "a" * 64,
            "dimensions": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "pinned digest"):
                load_calibration(path, expected_sha256="b" * 64)
            with self.assertRaisesRegex(ValueError, "dimensions"):
                load_calibration(path)

    def test_boundary_ordering_tracks_concordance_ties_inversions_and_invalid(self) -> None:
        tasks = []
        predictions = []
        for index, (anchor, predicted) in enumerate(((2, 2), (5, 5), (8, 5), (10, None))):
            task_id = f"task-{index}"
            tasks.append(
                {
                    "id": task_id,
                    "mutation_lineage": "lineage-one",
                    "boundary_dimension": "reasoning_demand",
                    "boundary_anchor": anchor,
                }
            )
            value = assessment().to_dict() if predicted is not None else None
            if value is not None:
                value["scores"]["reasoning_demand"] = predicted
            predictions.append({"id": task_id, "prediction": value})
        metrics = boundary_ordering_metrics(tasks, predictions)
        self.assertEqual(metrics["totals"]["comparisons"], 6)
        self.assertEqual(metrics["totals"]["concordant"], 2)
        self.assertEqual(metrics["totals"]["ties"], 1)
        self.assertEqual(metrics["totals"]["invalid"], 3)


class FunctionGemmaExperimentTests(unittest.TestCase):
    def test_checked_in_configuration_is_valid_and_pinned(self) -> None:
        config = load_config(Path("configs/functiongemma-sprint46.json"))
        self.assertEqual(config["model"]["revision"], "39eccb091651513a5dfb56892d3714c1b5b8276c")
        self.assertEqual(config["environment"]["trl"], "0.26.2")
        self.assertTrue(config["environment"]["torch"].startswith("2.9.1"))
        self.assertEqual(config["data"]["max_length"], 1024)
        self.assertEqual(config["variants"]["lora_r8"]["rank"], 8)
        self.assertEqual(config["variants"]["lora_r16"]["rank"], 16)

    def test_configuration_rejects_an_unmeasured_training_stack(self) -> None:
        payload = json.loads(Path("configs/functiongemma-sprint46.json").read_text(encoding="utf-8"))
        payload["environment"]["torch"] = "2.9.1+cuda"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "measured and pinned"):
                load_config(path)

    def test_prepare_validates_and_adds_tool_schema(self) -> None:
        config = load_config(Path("configs/functiongemma-sprint46.json"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            splits = root / "splits"
            splits.mkdir()
            row = {"id": "one", **training_conversation("What is 2 + 2?", assessment())}
            row.pop("tools")
            for name in ("train", "validation"):
                (splits / f"{name}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            result = prepare(config, splits, root / "prepared")
            prepared = json.loads((root / "prepared" / "train.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(result["counts"], {"train": 1, "validation": 1})
        self.assertEqual(prepared["tools"], [ASSESS_TASK_TOOL])

    def test_selection_requires_every_score_to_beat_baseline(self) -> None:
        baseline = {
            "schema_validity": 0.5,
            "intent_accuracy": 0.5,
            "score_mae": {name: 2.0 for name in assessment().scores.to_dict()},
        }
        candidate = {
            "model": "candidate",
            "schema_validity": 1.0,
            "intent_accuracy": 0.9,
            "score_mae": {name: 1.0 for name in assessment().scores.to_dict()},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_path = root / "baseline.json"
            candidate_path = root / "candidate.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            result = select(baseline_path, [candidate_path], root / "selection.json")
        self.assertEqual(result["champion"], "candidate")

    def test_boundary_report_is_reproducible_without_calibration(self) -> None:
        labeled = assessment().to_dict()
        tasks = [
            {
                "id": "low",
                "mutation_lineage": "lineage",
                "boundary_dimension": "deterministic_fit",
                "boundary_anchor": 2,
            },
            {
                "id": "high",
                "mutation_lineage": "lineage",
                "boundary_dimension": "deterministic_fit",
                "boundary_anchor": 8,
            },
        ]
        low = assessment(deterministic_fit=2).to_dict()
        high = assessment(deterministic_fit=8).to_dict()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_path = root / "tasks.jsonl"
            prediction_path = root / "predictions.jsonl"
            task_path.write_text("\n".join(json.dumps(row) for row in tasks) + "\n", encoding="utf-8")
            prediction_path.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in ({"id": "low", "prediction": low}, {"id": "high", "prediction": high})
                )
                + "\n",
                encoding="utf-8",
            )
            result = boundary_report(task_path, prediction_path, None, root / "report.json")
        self.assertEqual(result["raw"]["totals"]["strict_accuracy"], 1.0)
        self.assertIsNone(result["calibrated"])


if __name__ == "__main__":
    unittest.main()
