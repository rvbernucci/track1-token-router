import unittest

from router.functiongemma.tool_planner import tool_plan_from_function_call


class FunctionGemmaToolPlannerTests(unittest.TestCase):
    def test_parses_supported_call_with_decimal(self):
        raw = (
            "<start_function_call>call:recipe_cost{amount_numerator:1,amount_denominator:2,"
            "source_count:4,target_count:8,unit_price:2.5}<end_function_call>"
        )
        plan = tool_plan_from_function_call(raw)
        self.assertEqual(plan.tool, "recipe_cost")
        self.assertEqual(plan.arguments["unit_price"], 2.5)

    def test_converts_decline_to_fail_closed_none(self):
        plan = tool_plan_from_function_call(
            "<start_function_call>call:decline_tool{reason:<escape>unsafe<escape>}<end_function_call>"
        )
        self.assertEqual(plan.tool, "none")
        self.assertEqual(plan.confidence, "low")

    def test_rejects_unknown_extra_and_malformed_calls(self):
        invalid = (
            "answer <start_function_call>call:decline_tool{reason:<escape>unsafe<escape>}<end_function_call>",
            "<start_function_call>call:shell{command:<escape>rm<escape>}<end_function_call>",
            "<start_function_call>call:decline_tool{reason:<escape>unsafe<escape>,extra:1}<end_function_call>",
            "<start_function_call>call:recipe_cost{unit_price:2.}<end_function_call>",
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                tool_plan_from_function_call(raw)


if __name__ == "__main__":
    unittest.main()
