import json
from pathlib import Path
import tempfile
import unittest

from scripts.preflight_functiongemma_tool_planner import audit_corpus, audit_token_lengths
from scripts.train_functiongemma_tool_planner import _reject_sealed_training_path


class _Tokenizer:
    def apply_chat_template(self, messages, tools, tokenize):
        self.last = (messages, tools, tokenize)
        return list(range(12))


class FunctionGemmaPlannerPreflightTests(unittest.TestCase):
    def _corpus(self, root: Path, duplicate: bool = False) -> None:
        for index, split in enumerate(("train", "validation", "calibration", "sealed")):
            row = {
                "id": "same" if duplicate else f"row-{index}",
                "messages": [{"role": "system", "content": "x"}, {"role": "user", "content": f"prompt-{index}"}],
                "tools": [{"name": "calculator"}],
            }
            (root / f"{split}.jsonl").write_text(json.dumps(row) + "\n")

    def test_corpus_requires_unique_lineages_across_every_split(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._corpus(root)
            report = audit_corpus(root)
            self.assertTrue(report["gates"]["unique_ids_and_prompts_across_splits"])
            self._corpus(root, duplicate=True)
            report = audit_corpus(root)
            self.assertFalse(report["gates"]["unique_ids_and_prompts_across_splits"])

    def test_token_gate_reports_context_margin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._corpus(root)
            report = audit_token_lengths(root, "tokenizer", None, 20, True, tokenizer=_Tokenizer())
            self.assertEqual(report["token_lengths"]["maximum"], 12)
            self.assertEqual(report["token_lengths"]["margin"], 8)
            self.assertTrue(report["gates"]["all_examples_fit_context"])

    def test_training_rejects_sealed_data_root(self):
        with self.assertRaisesRegex(ValueError, "sealed split"):
            _reject_sealed_training_path(Path("data/sealed/planner"))
        _reject_sealed_training_path(Path("data/functiongemma-tool-planner-v1"))


if __name__ == "__main__":
    unittest.main()
