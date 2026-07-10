import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_e2b_regression_corpus import INTENTS, build_corpus


class BuildE2BRegressionCorpusTests(unittest.TestCase):
    def test_balances_intents_and_keeps_templates_in_one_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposals = root / "proposals.jsonl"
            rows = []
            for intent in INTENTS:
                for index in range(2):
                    rows.append({
                        "id": f"{intent}-{index}",
                        "task_text": f"Task {intent} {index}",
                        "content_sha256": f"{intent}-{index}",
                        "assessment": {"intent": intent, "scores": {}},
                        "mutation_lineage": f"lineage-{intent}-{index}",
                        "template_family": f"template-{intent}",
                        "mutation_kind": "canonical",
                        "source": "test",
                    })
            proposals.write_text("".join(json.dumps(row) + "\n" for row in rows))
            output = root / "corpus.jsonl"
            manifest = root / "manifest.json"
            report = build_corpus(proposal_paths=[proposals], per_intent=2, output=output, manifest=manifest)
            rendered = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(report["rows"], 16)
        self.assertTrue(all(value == 2 for value in report["intent_counts"].values()))
        by_template = {}
        for row in rendered:
            by_template.setdefault(row["template_family"], set()).add(row["regression_split"])
        self.assertTrue(all(len(values) == 1 for values in by_template.values()))


if __name__ == "__main__":
    unittest.main()
