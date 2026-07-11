import json
from pathlib import Path
import tempfile
import unittest

from scripts.run_e2b_regression_v2_inference import _balanced_pilot, _exclusive_run, _load_tasks, _request_e2b, _run, _verify
from tests.fake_openai_server import FakeOpenAIServer


class E2BRegressionV2InferenceTests(unittest.TestCase):
    def test_e2b_receives_only_raw_user_prompt_and_hard_cap(self) -> None:
        with FakeOpenAIServer(response_text="4") as server:
            self.assertEqual(_request_e2b(server.url, "e2b", "What is 2+2?", 2), "4")
        payload = server.requests[0]["payload"]
        self.assertEqual(payload["messages"], [{"role": "user", "content": "What is 2+2?"}])
        self.assertEqual(payload["max_completion_tokens"], 96)
        self.assertNotIn("task_id", json.dumps(payload))

    def test_loader_rejects_reference_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inputs").mkdir()
            for split in ("train", "validation", "final_holdout"):
                row = {"schema_version": "x", "task_id": split, "prompt": "hello"}
                if split == "validation":
                    row["reference_answer"] = "secret"
                (root / "inputs" / f"{split}.jsonl").write_text(json.dumps(row) + "\n")
            with self.assertRaisesRegex(ValueError, "non-contract"):
                _load_tasks(root)

    def test_pilot_is_category_balanced(self) -> None:
        tasks = [{"task_id": f"{category}-{i}", "prompt": "p"} for category in range(8) for i in range(20)]
        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / "metadata.jsonl"
            metadata.write_text("".join(
                json.dumps({"task_id": task["task_id"], "category": task["task_id"].split("-")[0]}) + "\n"
                for task in tasks
            ))
            pilot = _balanced_pilot(tasks, metadata, 80)
        counts = {}
        for row in pilot:
            category = row["task_id"].split("-")[0]
            counts[category] = counts.get(category, 0) + 1
        self.assertEqual(set(counts.values()), {10})

    def test_hundred_row_pilot_differs_by_at_most_one_per_category(self) -> None:
        tasks = [{"task_id": f"{category}-{i}", "prompt": "p"} for category in range(8) for i in range(20)]
        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / "metadata.jsonl"
            metadata.write_text("".join(json.dumps({"task_id": row["task_id"], "category": row["task_id"].split("-")[0]}) + "\n" for row in tasks))
            pilot = _balanced_pilot(tasks, metadata, 100)
        counts = {}
        for row in pilot:
            key = row["task_id"].split("-")[0]
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(len(pilot), 100)
        self.assertEqual(set(counts.values()), {12, 13})

    def test_only_functiongemma_does_not_create_e2b_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with FakeOpenAIServer(
                response_text='<start_function_call>call:assess_task{intent:<escape>math_reasoning<escape>,scores:{deterministic_fit:2,reasoning_demand:2,knowledge_uncertainty:0,generation_demand:2,format_complexity:2}}'
            ) as server:
                _run(
                    [{"task_id": "t1", "prompt": "What is 2+2?"}], output,
                    server.url, "fg", server.url, "e2b", 2, False, "functiongemma",
                )
            self.assertTrue((output / "functiongemma.jsonl").is_file())
            self.assertFalse((output / "e2b.jsonl").exists())

    def test_exclusive_lock_rejects_second_writer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with _exclusive_run(output):
                with self.assertRaisesRegex(RuntimeError, "already running"):
                    with _exclusive_run(output):
                        pass

    def test_verifier_counts_explicit_quarantine_as_outcome_not_valid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            tasks = [{"task_id": f"t{i}", "prompt": f"prompt {i}"} for i in range(100)]
            for engine in ("functiongemma", "e2b"):
                valid = []
                for task in tasks[:-1] if engine == "functiongemma" else tasks:
                    valid.append({
                        "task_id": task["task_id"], "prompt_sha256": __import__("hashlib").sha256(task["prompt"].encode()).hexdigest(),
                        "latency_ms": 1, "assessment": {} if engine == "functiongemma" else None,
                    })
                (output / f"{engine}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in valid))
            failed = tasks[-1]
            (output / "functiongemma-failures.jsonl").write_text(json.dumps({
                "task_id": failed["task_id"], "prompt_sha256": __import__("hashlib").sha256(failed["prompt"].encode()).hexdigest(),
                "latency_ms": 1, "error": "invalid",
            }) + "\n")
            result = _verify(tasks, output, require_full=False)
        self.assertTrue(result["checks"]["functiongemma_outcome_coverage"])
        self.assertTrue(result["checks"]["functiongemma_schema_validity"])


if __name__ == "__main__":
    unittest.main()
