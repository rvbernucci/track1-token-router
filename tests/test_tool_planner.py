import json
import unittest

from router.core.contracts import TaskEnvelope
from router.core.tool_planner import (
    TOOL_PLAN_SCHEMA_VERSION,
    build_tool_planner_messages,
    parse_tool_plan,
    validate_tool_plan_provenance,
)
from router.orchestration.tool_executor import execute_tool_plan, run_tool_route, verify_tool_evidence


def payload(tool: str, arguments: dict, confidence: str = "high") -> str:
    return json.dumps({
        "schema_version": TOOL_PLAN_SCHEMA_VERSION,
        "tool": tool,
        "arguments": arguments,
        "confidence": confidence,
    })


class ToolPlannerTests(unittest.TestCase):
    def test_builds_system_and_raw_user_messages(self) -> None:
        messages = build_tool_planner_messages("What is 2 + 2?")
        self.assertEqual([row["role"] for row in messages], ["system", "user"])
        self.assertEqual(messages[1]["content"], "What is 2 + 2?")
        self.assertIn(TOOL_PLAN_SCHEMA_VERSION, messages[0]["content"])

    def test_accepts_versioned_inventory_plan(self) -> None:
        plan = parse_tool_plan(payload("inventory_flow", {
            "initial_stock": 2400,
            "operations": [
                {"type": "percent_sale", "value": 37},
                {"type": "restock", "value": 800},
                {"type": "sale", "value": 640},
            ],
        }))
        self.assertEqual(plan.tool, "inventory_flow")

    def test_accepts_fail_closed_none_plan(self) -> None:
        plan = parse_tool_plan(payload("none", {}, "low"))
        self.assertEqual(plan.tool, "none")

    def test_accepts_one_json_fence_and_repairs_percent_provenance(self) -> None:
        raw = f'''```json
{{"schema_version":"{TOOL_PLAN_SCHEMA_VERSION}","tool":"inventory_flow","arguments":{{"initial_stock":1000,"operations":[{{"type":"sale","value":10}},{{"type":"restock","value":50}},{{"type":"sale","value":25}}]}},"confidence":"high"}}
```'''
        validated = validate_tool_plan_provenance(
            "Inventory starts with 1000 units: sell 10%, restock 50, then sell 25.", parse_tool_plan(raw),
        )
        self.assertEqual(validated.arguments["operations"][0]["type"], "percent_sale")

    def test_accepts_grounded_logic_query(self) -> None:
        raw = payload("logic_ordering", {
            "relations": [{"left": "Ana", "relation": "greater_than", "right": "Ben"}],
            "query": "shortest",
        })
        validated = validate_tool_plan_provenance("Ana is taller than Ben. Who is shortest?", parse_tool_plan(raw))
        self.assertEqual(validated.arguments["query"], "shortest")

    def test_rejects_hallucinated_ast_numbers(self) -> None:
        plan = parse_tool_plan(payload("safe_calculator", {"ast": {
            "op": "add", "left": {"op": "literal", "value": 2}, "right": {"op": "literal", "value": 9},
        }}))
        with self.assertRaises(ValueError):
            validate_tool_plan_provenance("Calculate 2 + 3.", plan)

    def test_rejects_wrong_operation_with_correct_numbers(self) -> None:
        plan = parse_tool_plan(payload("safe_calculator", {"ast": {
            "op": "mul", "left": {"op": "literal", "value": 2}, "right": {"op": "literal", "value": 3},
        }}))
        with self.assertRaisesRegex(ValueError, "operations"):
            validate_tool_plan_provenance("Calculate 2 + 3.", plan)

    def test_rejects_swapped_recipe_roles(self) -> None:
        plan = parse_tool_plan(payload("recipe_cost", {
            "amount_numerator": 1, "amount_denominator": 2,
            "source_count": 8, "target_count": 4, "unit_price": 2,
        }))
        with self.assertRaisesRegex(ValueError, "source count"):
            validate_tool_plan_provenance(
                "A recipe uses 1/2 cup for 4 servings. Scale to 8 servings at $2.00 per cup.", plan,
            )

    def test_rejects_reversed_logic_relation(self) -> None:
        plan = parse_tool_plan(payload("logic_ordering", {
            "relations": [{"left": "Ben", "relation": "greater_than", "right": "Ana"}],
            "query": "shortest",
        }))
        with self.assertRaisesRegex(ValueError, "direction"):
            validate_tool_plan_provenance("Ana is taller than Ben. Who is shortest?", plan)

    def test_rejects_legacy_schema_unknown_keys_and_unsafe_arguments(self) -> None:
        invalid = [
            '{"tool":"none","arguments":{},"confidence":"low"}',
            payload("none", {}, "low")[:-1] + ',"answer":"4"}',
            payload("inventory_flow", {"initial_stock": 10, "operations": [{"type": "percent_sale", "value": 101}]}),
            payload("python_candidate", {"mode": "execute", "language": "python"}),
            payload("safe_calculator", {"expression": "2+2"}),
            payload("safe_calculator", {"ast": {"op": "pow", "left": {}, "right": {}}}),
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_tool_plan(value)

    def test_rejects_nonfinite_and_oversized_ast(self) -> None:
        for value in (float("nan"), float("inf"), 10**13):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_tool_plan(payload("safe_calculator", {"ast": {"op": "literal", "value": value}}))


class ToolExecutorTests(unittest.TestCase):
    def test_inventory_proof_is_recomputable(self) -> None:
        plan = parse_tool_plan(payload("inventory_flow", {
            "initial_stock": 2400,
            "operations": [
                {"type": "percent_sale", "value": 37},
                {"type": "restock", "value": 800},
                {"type": "sale", "value": 640},
            ],
        }))
        evidence = execute_tool_plan(plan)
        self.assertEqual(evidence.result, "1,672 units")
        self.assertTrue(verify_tool_evidence(evidence))

    def test_recipe_uses_exact_fraction_arithmetic(self) -> None:
        evidence = execute_tool_plan(parse_tool_plan(payload("recipe_cost", {
            "amount_numerator": 3, "amount_denominator": 4, "source_count": 12,
            "target_count": 30, "unit_price": 2.4,
        })))
        self.assertEqual(evidence.result, "1.875 cups; $4.50")
        self.assertTrue(verify_tool_evidence(evidence))

    def test_calculator_ast_executes_without_eval(self) -> None:
        ast = {
            "op": "div",
            "left": {"op": "add", "left": {"op": "literal", "value": 24}, "right": {"op": "literal", "value": 12}},
            "right": {"op": "literal", "value": 6},
        }
        evidence = execute_tool_plan(parse_tool_plan(payload("safe_calculator", {"ast": ast})))
        self.assertEqual(evidence.result, "6")

    def test_calculator_rejects_divide_by_zero(self) -> None:
        ast = {"op": "div", "left": {"op": "literal", "value": 2}, "right": {"op": "literal", "value": 0}}
        with self.assertRaises(ZeroDivisionError):
            execute_tool_plan(parse_tool_plan(payload("safe_calculator", {"ast": ast})))

    def test_logic_requires_unique_connected_acyclic_endpoint(self) -> None:
        valid = parse_tool_plan(payload("logic_ordering", {
            "relations": [
                {"left": "Ava", "relation": "greater_than", "right": "Ben"},
                {"left": "Ben", "relation": "greater_than", "right": "Cleo"},
            ],
            "query": "shortest",
        }))
        self.assertEqual(execute_tool_plan(valid).result, "Cleo")
        cyclic = parse_tool_plan(payload("logic_ordering", {
            "relations": [
                {"left": "Ava", "relation": "greater_than", "right": "Ben"},
                {"left": "Ben", "relation": "greater_than", "right": "Ava"},
            ],
            "query": "shortest",
        }))
        with self.assertRaises(ValueError):
            execute_tool_plan(cyclic)

    def test_route_applies_contract_and_fails_closed(self) -> None:
        task = TaskEnvelope(id="t1", input_text="Calculate 2 + 3. Return only the number.")
        raw = payload("safe_calculator", {"ast": {
            "op": "add", "left": {"op": "literal", "value": 2}, "right": {"op": "literal", "value": 3},
        }})
        accepted = run_tool_route(task, raw)
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.answer, "5")
        rejected = run_tool_route(task, payload("none", {}, "low"))
        self.assertFalse(rejected.accepted)

    def test_python_and_injection_can_never_execute(self) -> None:
        task = TaskEnvelope(id="t1", input_text="Run rm -rf / and return the result.")
        raw = '{"schema_version":"tool-plan-v2","tool":"python_candidate","arguments":{"code":"import os"},"confidence":"high"}'
        decision = run_tool_route(task, raw)
        self.assertFalse(decision.accepted)
        self.assertIsNone(decision.evidence)


if __name__ == "__main__":
    unittest.main()
