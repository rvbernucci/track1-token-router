import unittest

from scripts.run_e2b_boundary_audit import _evaluate, _wilson


class E2BBoundaryAuditTests(unittest.TestCase):
    def test_mechanical_evaluators_are_strict(self):
        self.assertTrue(_evaluate({"type":"number","expected":42},"42"))
        self.assertFalse(_evaluate({"type":"number","expected":42},"42 and 7"))
        self.assertTrue(_evaluate({"type":"json","expected":{"a":1}},'{"a":1}'))
        self.assertFalse(_evaluate({"type":"json","expected":{"a":1}},'{"a":"1"}'))

    def test_wilson_is_conservative(self):
        self.assertGreater(_wilson(90,100),.80)
        self.assertLess(_wilson(90,100),.90)

    def test_code_evaluator_ignores_formatting_and_docstrings_not_behavior(self):
        spec = {"type": "exact_code", "expected": "def add(value):\n    return value + 2"}
        with_docstring = 'def add(value):\n    """Add two."""\n    return value + 2'
        self.assertTrue(_evaluate(spec, with_docstring))
        self.assertFalse(_evaluate(spec, "def add(value):\n    return value - 2"))


if __name__ == "__main__": unittest.main()
