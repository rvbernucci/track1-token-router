import unittest

from scripts.fireworks_microbench import _validate


class FireworksMicrobenchValidatorTests(unittest.TestCase):
    def test_python_function_cases_execute_safe_function(self) -> None:
        validator = {
            "type": "python_function_cases",
            "function_name": "clamp",
            "cases": [
                {"args": [5, 1, 10], "expected": 5},
                {"args": [-3, 0, 10], "expected": 0},
                {"args": [22, 0, 10], "expected": 10},
            ],
        }

        result = _validate(
            validator,
            "def clamp(value, low, high):\n    return max(low, min(value, high))\n",
        )

        self.assertTrue(result["valid"])

    def test_python_function_cases_block_imports(self) -> None:
        validator = {
            "type": "python_function_cases",
            "function_name": "clamp",
            "cases": [{"args": [5, 1, 10], "expected": 5}],
        }

        result = _validate(
            validator,
            "import os\ndef clamp(value, low, high):\n    return value\n",
        )

        self.assertFalse(result["valid"])
        self.assertIn("blocked Python construct", result["reason"])

    def test_python_function_cases_report_behavior_failures(self) -> None:
        validator = {
            "type": "python_function_cases",
            "function_name": "clamp",
            "cases": [{"args": [-3, 0, 10], "expected": 0}],
        }

        result = _validate(
            validator,
            "def clamp(value, low, high):\n    return value\n",
        )

        self.assertFalse(result["valid"])
        self.assertIn("expected", result["reason"])

    def test_contains_all_lower_validator_checks_terms_and_length(self) -> None:
        validator = {
            "type": "contains_all_lower",
            "terms": ["local", "tokens"],
            "max_words": 5,
        }

        self.assertTrue(_validate(validator, "Local checks save tokens.")["valid"])
        self.assertFalse(_validate(validator, "Local checks are helpful.")["valid"])
        self.assertFalse(_validate(validator, "Local checks save remote model tokens today.")["valid"])


if __name__ == "__main__":
    unittest.main()
