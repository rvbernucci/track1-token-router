import json
import tempfile
import unittest
from pathlib import Path

from scripts.filter_valid_assessments import filter_valid


class FilterValidAssessmentsTests(unittest.TestCase):
    def test_excludes_invalid_calls_without_relabeling_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = [
                {"id": "ok", "regression_split": "train"},
                {"id": "bad", "regression_split": "test"},
            ]
            assessments = [
                {
                    "id": "ok",
                    "parse_error": None,
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
                },
                {"id": "bad", "parse_error": "unknown intent", "prediction": None},
            ]
            for name, rows in (("tasks", tasks), ("assessments", assessments)):
                (root / f"{name}.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
                )
            report = filter_valid(
                tasks_path=root / "tasks.jsonl",
                assessments_path=root / "assessments.jsonl",
                valid_tasks_path=root / "valid-tasks.jsonl",
                valid_assessments_path=root / "valid-assessments.jsonl",
                report_path=root / "report.json",
            )
            self.assertEqual((report["valid"], report["excluded"]), (1, 1))
            self.assertEqual(report["exclusions"][0]["id"], "bad")
            self.assertEqual(len((root / "valid-tasks.jsonl").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
