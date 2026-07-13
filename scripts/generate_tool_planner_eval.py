#!/usr/bin/env python3
from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path

from router.core.tool_planner import TOOL_PLAN_SCHEMA_VERSION, ToolPlan
from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import apply_answer_contract
from router.orchestration.tool_executor import execute_tool_plan


def main() -> int:
    output = Path("evals/tool-planner-v2/corpus.jsonl")
    rows = [*_inventory_rows(), *_recipe_rows(), *_calculator_rows(), *_logic_rows(), *_none_rows()]
    if len(rows) != 500 or len({row["id"] for row in rows}) != len(rows):
        raise RuntimeError("Tool planner corpus must contain exactly 500 unique tasks.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows))
    print(json.dumps({
        "output": str(output), "tasks": len(rows),
        "development": sum(row["split"] == "development" for row in rows),
        "sealed": sum(row["split"] == "sealed" for row in rows),
    }, sort_keys=True))
    return 0


def _inventory_rows() -> list[dict]:
    rows = []
    templates = (
        "A warehouse starts with {initial:,} units. It sells {percent}% of stock, restocks {restock} units, then sells {sale} units. How many units remain?",
        "Inventory begins at {initial:,}. Sell {percent} percent, add {restock}, and sell another {sale} units. Return the final unit count.",
        "A depot has {initial:,} items; {percent}% are sold, {restock} arrive, and {sale} more are sold. Determine ending inventory.",
    )
    for index in range(100):
        initial = 500 + index * 37
        percent = (index % 9 + 1) * 5
        restock = 40 + index * 3
        sale = 10 + index * 2
        arguments = {
            "initial_stock": initial,
            "operations": [
                {"type": "percent_sale", "value": percent},
                {"type": "restock", "value": restock},
                {"type": "sale", "value": sale},
            ],
        }
        rows.append(_row("inventory", index, templates[index % len(templates)].format(
            initial=initial, percent=percent, restock=restock, sale=sale,
        ), "inventory_flow", arguments))
    return rows


def _recipe_rows() -> list[dict]:
    rows = []
    templates = (
        "A recipe uses {n}/{d} cup of flour for {source} servings. Scale it to {target} servings and calculate the cost at ${price:.2f} per cup.",
        "For {source} portions, a dish needs {n}/{d} cup of rice. How many cups and what cost for {target} portions if rice costs ${price:.2f} per cup?",
        "A batch serving {source} uses {n}/{d} cup of sugar. Find the amount and total cost for {target} servings at ${price:.2f} per cup.",
    )
    for index in range(100):
        denominator = (2, 3, 4, 5, 8)[index % 5]
        numerator = index % denominator + 1
        source = 4 + index % 13
        target = source + 2 + index % 19
        price = round(1.25 + (index % 17) * 0.25, 2)
        arguments = {
            "amount_numerator": numerator, "amount_denominator": denominator,
            "source_count": source, "target_count": target, "unit_price": price,
        }
        rows.append(_row("recipe", index, templates[index % len(templates)].format(
            n=numerator, d=denominator, source=source, target=target, price=price,
        ), "recipe_cost", arguments))
    return rows


def _calculator_rows() -> list[dict]:
    rows = []
    symbols = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
    for index in range(100):
        a = 10 + index
        b = 2 + index % 11
        c = 1 + index % 7
        first = ("add", "sub", "mul")[index % 3]
        second = ("mul", "add", "div")[index % 3]
        left = {"op": first, "left": _literal(a), "right": _literal(b)}
        ast = {"op": second, "left": left, "right": _literal(c)}
        expression = f"({a} {symbols[first]} {b}) {symbols[second]} {c}"
        prompt = f"Evaluate the explicit arithmetic expression {expression}. Return only the number."
        rows.append(_row("calculator", index, prompt, "safe_calculator", {"ast": ast}))
    return rows


def _logic_rows() -> list[dict]:
    rows = []
    for index in range(100):
        names = [f"Person{index}{suffix}" for suffix in ("A", "B", "C", "D")]
        relations = [
            {"left": names[0], "relation": "greater_than", "right": names[1]},
            {"left": names[1], "relation": "greater_than", "right": names[2]},
            {"left": names[2], "relation": "greater_than", "right": names[3]},
        ]
        query = "shortest" if index % 2 == 0 else "tallest"
        prompt = (
            f"{names[0]} is taller than {names[1]}. {names[1]} is taller than {names[2]}. "
            f"{names[2]} is taller than {names[3]}. Who is {query}?"
        )
        rows.append(_row("logic", index, prompt, "logic_ordering", {"relations": relations, "query": query}))
    return rows


def _none_rows() -> list[dict]:
    templates = (
        "Who is the current president of country {i}?",
        "Summarize document {i}, which was not provided.",
        "Calculate the final inventory for warehouse {i}; no quantities are supplied.",
        "Order group {i} by age, but no ages or relations are supplied.",
        "Write and execute arbitrary Python that opens file {i} and calls the network.",
        "A recipe serves group {i}. Calculate its cost using a missing regional price.",
        "Solve the equation in missing image {i}.",
        "Recommend the best live traffic route for trip {i}.",
    )
    return [_row("none", index, templates[index % len(templates)].format(i=index), "none", {}) for index in range(100)]


def _literal(value: int) -> dict:
    return {"op": "literal", "value": value}


def _row(family: str, index: int, prompt: str, tool: str, arguments: dict) -> dict:
    expected_plan = {
        "schema_version": TOOL_PLAN_SCHEMA_VERSION,
        "tool": tool,
        "arguments": arguments,
        "confidence": "low" if tool == "none" else "high",
    }
    expected_answer = ""
    if tool != "none":
        raw_answer = execute_tool_plan(ToolPlan(tool, arguments, "high")).result
        contract = apply_answer_contract(TaskEnvelope(id=f"{family}_{index:03d}", input_text=prompt), raw_answer)
        if not contract.valid:
            raise RuntimeError(f"Generated expected answer violates its contract: {family}_{index:03d}")
        expected_answer = contract.answer
    return {
        "id": f"{family}_{index:03d}",
        "lineage": f"{family}-lineage-{index:03d}",
        "family": family,
        "difficulty": ("easy", "moderate", "difficult")[index % 3],
        "split": "sealed" if index % 5 == 0 else "development",
        "prompt": prompt,
        "expected": expected_plan,
        "expected_answer": expected_answer,
    }


if __name__ == "__main__":
    raise SystemExit(main())
