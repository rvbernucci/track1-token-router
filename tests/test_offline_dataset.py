import tempfile
import unittest
from pathlib import Path

from router.evals.offline_dataset import CATEGORIES, build_offline_examples, validate_offline_dataset, write_offline_dataset


class OfflineDatasetTests(unittest.TestCase):
    def test_build_offline_examples_has_all_categories(self) -> None:
        examples = build_offline_examples(per_category=2)
        categories = {example.category for example in examples}

        self.assertEqual(categories, set(CATEGORIES))
        self.assertEqual(len(examples), len(CATEGORIES) * 2)
        self.assertTrue(all(example.expected_route for example in examples))

    def test_write_and_validate_offline_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "offline"

            write_offline_dataset(root, per_category=13)
            errors = validate_offline_dataset(root, min_total=100)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
