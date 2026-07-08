import subprocess
import sys
import unittest
from pathlib import Path

from scripts.list_test_coverage import load_matrix, validate_matrix


class TestingCultureTests(unittest.TestCase):
    def test_test_matrix_has_critical_domains(self) -> None:
        domains = {row.domain for row in load_matrix()}

        self.assertEqual(
            domains,
            {
                "contracts",
                "adapters",
                "policies",
                "fireworks_model_router",
                "matrix_regression_selector",
                "prompts",
                "cascade",
                "fake_provider",
                "evals",
                "operational_envelope",
                "cli",
            },
        )

    def test_test_matrix_is_valid(self) -> None:
        self.assertEqual(validate_matrix(), [])

    def test_playground_examples_run_without_credits(self) -> None:
        for playground in [
            Path("playground/test_policy_logic.py"),
            Path("playground/test_adapter_logic.py"),
            Path("playground/test_prompt_packets.py"),
        ]:
            completed = subprocess.run(
                [sys.executable, str(playground)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(completed.stdout.strip(), playground)

    def test_list_test_coverage_check_command(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/list_test_coverage.py", "--check"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("contracts:", completed.stdout)


if __name__ == "__main__":
    unittest.main()
