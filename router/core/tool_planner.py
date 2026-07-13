from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any, Iterator, Mapping


TOOL_PLAN_SCHEMA_VERSION = "tool-plan-v2"
TOOL_PLANNER_PROMPT_VERSION = "e2b-tool-planner-v2"
TOOL_PLANNER_SYSTEM_PROMPT = f"""You are a local tool planner. Do not solve the task.
Select exactly one supported tool only when every argument is explicit in the user task.
Never invent a number, unit, operation, relation, identifier, or programming language.
If the task is ambiguous or unsupported, select none.

Supported tools:
- inventory_flow: {{"initial_stock":number,"operations":[{{"type":"percent_sale|restock|sale","value":number}}]}}.
- recipe_cost: {{"amount_numerator":integer,"amount_denominator":integer,"source_count":integer,"target_count":integer,"unit_price":number}}.
- safe_calculator: {{"ast": arithmetic AST}}. AST nodes are {{"op":"literal","value":number}} or {{"op":"add|sub|mul|div","left":AST,"right":AST}}.
- logic_ordering: {{"relations":[{{"left":"name","relation":"greater_than|less_than","right":"name"}}],"query":"shortest|tallest|youngest|oldest|lightest|heaviest"}}.
- none: no supported tool is safe.

Python and arbitrary code execution are not supported.
Return only compact JSON with exactly these keys:
{{"schema_version":"{TOOL_PLAN_SCHEMA_VERSION}","tool":"inventory_flow|recipe_cost|safe_calculator|logic_ordering|none","arguments":{{}},"confidence":"high|low"}}
Use high confidence only when every required argument is explicit. Otherwise return none with low confidence."""


@dataclass(frozen=True)
class ToolPlan:
    tool: str
    arguments: Mapping[str, Any]
    confidence: str
    schema_version: str = TOOL_PLAN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool": self.tool,
            "arguments": json.loads(json.dumps(self.arguments)),
            "confidence": self.confidence,
        }


def build_tool_planner_messages(task_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": TOOL_PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": task_text},
    ]


def parse_tool_plan(value: str) -> ToolPlan:
    stripped = value.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, flags=re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("Tool plan must be one JSON object without wrappers.") from exc
    expected = {"schema_version", "tool", "arguments", "confidence"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("Tool plan has an invalid top-level schema.")
    if payload["schema_version"] != TOOL_PLAN_SCHEMA_VERSION:
        raise ValueError("Tool plan schema version is not supported.")
    tool = payload["tool"]
    arguments = payload["arguments"]
    confidence = payload["confidence"]
    if tool not in {"inventory_flow", "recipe_cost", "safe_calculator", "logic_ordering", "none"}:
        raise ValueError("Tool plan selected an unknown tool.")
    if not isinstance(arguments, dict) or confidence not in {"high", "low"}:
        raise ValueError("Tool plan arguments or confidence are invalid.")
    if tool == "none":
        if arguments or confidence != "low":
            raise ValueError("The none route must contain empty arguments and low confidence.")
        return ToolPlan(tool, arguments, confidence)
    if confidence != "high":
        raise ValueError("Executable tool plans require high confidence.")
    _validate_arguments(tool, arguments)
    return ToolPlan(tool, arguments, confidence)


def validate_tool_plan_provenance(task_text: str, plan: ToolPlan) -> ToolPlan:
    if plan.tool == "none":
        return plan
    arguments = json.loads(json.dumps(plan.arguments))
    prompt_numbers = {
        _normalize_number(value)
        for value in re.findall(r"(?<![\w.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", task_text)
    }
    for value in _numeric_arguments(arguments):
        if _normalize_number(value) not in prompt_numbers:
            raise ValueError("Tool plan contains a number that is absent from the task.")
    if plan.tool == "inventory_flow":
        for operation in arguments["operations"]:
            number = re.escape(_normalize_number(operation["value"]))
            if operation["type"] == "sale" and re.search(rf"\b{number}(?:\.0+)?\s*(?:%|percent\b)", task_text, re.I):
                operation["type"] = "percent_sale"
        _validate_inventory_order(task_text, arguments["operations"])
    elif plan.tool == "recipe_cost":
        _validate_recipe_roles(task_text, arguments)
    elif plan.tool == "logic_ordering":
        for relation in arguments["relations"]:
            if relation["left"].casefold() not in task_text.casefold() or relation["right"].casefold() not in task_text.casefold():
                raise ValueError("Logic relation contains an endpoint absent from the task.")
            if not _logic_relation_is_grounded(task_text, relation):
                raise ValueError("Logic relation direction is not grounded in the task.")
        explicit_queries = [
            word for word in ("shortest", "tallest", "youngest", "oldest", "lightest", "heaviest")
            if re.search(rf"\b{word}\b", task_text, re.I)
        ]
        if len(explicit_queries) != 1 or arguments["query"] != explicit_queries[0]:
            raise ValueError("Logic query is missing, ambiguous, or not copied exactly.")
    elif plan.tool == "safe_calculator":
        if re.search(r"\b(?:recipe|inventory|stock|total\s+cost)\b|\bcosts?\s+\$", task_text, re.I):
            raise ValueError("Structured word problems require a specialized tool.")
        rendered = _render_arithmetic_ast(arguments["ast"])
        compact_prompt = re.sub(r"\s+", "", task_text)
        if rendered not in compact_prompt and rendered.strip("()") not in compact_prompt:
            raise ValueError("Arithmetic operations are not copied exactly from the task.")
    validated = ToolPlan(plan.tool, arguments, plan.confidence)
    _validate_arguments(validated.tool, validated.arguments)
    return validated


def _validate_arguments(tool: str, arguments: Mapping[str, Any]) -> None:
    if tool == "inventory_flow":
        _require_keys(arguments, {"initial_stock", "operations"})
        if not _is_nonnegative_number(arguments["initial_stock"]):
            raise ValueError("initial_stock must be non-negative.")
        operations = arguments["operations"]
        if not isinstance(operations, list) or not 1 <= len(operations) <= 12:
            raise ValueError("inventory_flow requires one to twelve operations.")
        for operation in operations:
            if not isinstance(operation, dict) or set(operation) != {"type", "value"}:
                raise ValueError("Inventory operation schema is invalid.")
            if operation["type"] not in {"percent_sale", "restock", "sale"}:
                raise ValueError("Inventory operation type is invalid.")
            if not _is_nonnegative_number(operation["value"]):
                raise ValueError("Inventory operation value must be non-negative.")
            if operation["type"] == "percent_sale" and float(operation["value"]) > 100:
                raise ValueError("Percent sale cannot exceed 100.")
        return
    if tool == "recipe_cost":
        _require_keys(arguments, {"amount_numerator", "amount_denominator", "source_count", "target_count", "unit_price"})
        for key in ("amount_numerator", "source_count", "target_count", "unit_price"):
            if not _is_nonnegative_number(arguments[key]):
                raise ValueError(f"{key} must be non-negative.")
        for key in ("amount_numerator", "amount_denominator", "source_count", "target_count"):
            if not isinstance(arguments[key], int):
                raise ValueError(f"{key} must be an integer.")
        if arguments["amount_denominator"] <= 0 or arguments["source_count"] <= 0:
            raise ValueError("Recipe denominators must be positive.")
        return
    if tool == "safe_calculator":
        _require_keys(arguments, {"ast"})
        _validate_arithmetic_ast(arguments["ast"])
        return
    if tool == "logic_ordering":
        _require_keys(arguments, {"relations", "query"})
        if not isinstance(arguments["relations"], list) or not 1 <= len(arguments["relations"]) <= 32:
            raise ValueError("logic_ordering requires one to thirty-two relations.")
        for relation in arguments["relations"]:
            if not isinstance(relation, dict) or set(relation) != {"left", "relation", "right"}:
                raise ValueError("Logic relation schema is invalid.")
            if relation["relation"] not in {"greater_than", "less_than"}:
                raise ValueError("Logic relation type is invalid.")
            if not all(isinstance(relation[key], str) and re.fullmatch(r"[\w -]{1,64}", relation[key]) for key in ("left", "right")):
                raise ValueError("Logic relation endpoints are invalid.")
            if relation["left"].casefold() == relation["right"].casefold():
                raise ValueError("Self relations are invalid.")
        if arguments["query"] not in {"shortest", "tallest", "youngest", "oldest", "lightest", "heaviest"}:
            raise ValueError("Logic query is invalid.")
        return
    raise ValueError("Unknown tool schema.")


def _validate_arithmetic_ast(node: object, *, depth: int = 0, count: list[int] | None = None) -> None:
    if count is None:
        count = [0]
    count[0] += 1
    if depth > 16 or count[0] > 63 or not isinstance(node, dict):
        raise ValueError("Arithmetic AST exceeds its safety bounds.")
    op = node.get("op")
    if op == "literal":
        if set(node) != {"op", "value"} or not _is_finite_number(node["value"]):
            raise ValueError("Arithmetic literal is invalid.")
        if abs(float(node["value"])) > 1e12:
            raise ValueError("Arithmetic literal exceeds its bound.")
        return
    if op not in {"add", "sub", "mul", "div"} or set(node) != {"op", "left", "right"}:
        raise ValueError("Arithmetic operation is invalid.")
    _validate_arithmetic_ast(node["left"], depth=depth + 1, count=count)
    _validate_arithmetic_ast(node["right"], depth=depth + 1, count=count)


def _validate_inventory_order(task_text: str, operations: list[dict[str, Any]]) -> None:
    positions: list[int] = []
    cursor = 0
    for operation in operations:
        value = re.escape(_normalize_number(operation["value"]))
        if operation["type"] == "restock":
            pattern = rf"(?:\b(?:restock(?:s|ed)?|add(?:s|ed)?)\D{{0,24}}{value}(?:\.0+)?\b|\b{value}(?:\.0+)?\D{{0,12}}\barrive(?:s|d)?\b)"
        elif operation["type"] == "percent_sale":
            pattern = rf"(?:\b(?:sell(?:s|ing)?|sold)\D{{0,24}}{value}(?:\.0+)?\s*(?:%|percent\b)|\b{value}(?:\.0+)?\s*(?:%|percent)\D{{0,24}}\b(?:are\s+)?sold\b)"
        else:
            pattern = rf"(?:\b(?:sell(?:s|ing)?|sold)\D{{0,24}}{value}(?:\.0+)?\b(?!\s*(?:%|percent))|\b{value}(?:\.0+)?\D{{0,12}}\b(?:are\s+)?sold\b)"
        match = re.search(pattern, task_text[cursor:], re.I)
        if match is None:
            raise ValueError("Inventory operation is not explicitly grounded in order.")
        cursor += match.end()
        positions.append(cursor)
    if len(positions) != len(operations):
        raise ValueError("Inventory operation order is ambiguous.")


def _validate_recipe_roles(task_text: str, arguments: Mapping[str, Any]) -> None:
    numerator = re.escape(str(arguments["amount_numerator"]))
    denominator = re.escape(str(arguments["amount_denominator"]))
    source = re.escape(str(arguments["source_count"]))
    target = re.escape(str(arguments["target_count"]))
    price = re.escape(_normalize_number(arguments["unit_price"]))
    if not re.search(rf"\b{numerator}\s*/\s*{denominator}\b", task_text):
        raise ValueError("Recipe fraction roles are not grounded.")
    source_patterns = (
        rf"\bfor\s+{source}\s+(?:servings?|portions?)\b",
        rf"\bserving\s+{source}\b",
    )
    target_patterns = (
        rf"\b(?:to|for)\s+{target}\s+(?:servings?|portions?)\b",
        rf"\bfor\s+{target}\s+(?:servings?|portions?)\b",
    )
    if not any(re.search(pattern, task_text, re.I) for pattern in source_patterns):
        raise ValueError("Recipe source count role is not grounded.")
    if not any(re.search(pattern, task_text, re.I) for pattern in target_patterns):
        raise ValueError("Recipe target count role is not grounded.")
    if arguments["source_count"] == arguments["target_count"]:
        raise ValueError("Recipe source and target roles are ambiguous.")
    decimal_suffix = r"(?:\.0+)?" if "." not in _normalize_number(arguments["unit_price"]) else r"(?:0+)?"
    if not re.search(rf"\${price}{decimal_suffix}\s+per\s+cup\b", task_text, re.I):
        raise ValueError("Recipe unit price role is not grounded.")


def _logic_relation_is_grounded(task_text: str, relation: Mapping[str, Any]) -> bool:
    left = re.escape(relation["left"])
    right = re.escape(relation["right"])
    greater_words = r"(?:taller|older|heavier|greater|larger|longer)"
    lesser_words = r"(?:shorter|younger|lighter|less|smaller)"
    if relation["relation"] == "greater_than":
        patterns = (
            rf"\b{left}\s+is\s+{greater_words}\s+than\s+{right}\b",
            rf"\b{right}\s+is\s+{lesser_words}\s+than\s+{left}\b",
        )
    else:
        patterns = (
            rf"\b{left}\s+is\s+{lesser_words}\s+than\s+{right}\b",
            rf"\b{right}\s+is\s+{greater_words}\s+than\s+{left}\b",
        )
    return any(re.search(pattern, task_text, re.I) for pattern in patterns)


def _render_arithmetic_ast(node: Mapping[str, Any]) -> str:
    if node["op"] == "literal":
        return _normalize_number(node["value"])
    symbol = {"add": "+", "sub": "-", "mul": "*", "div": "/"}[node["op"]]
    return f"({_render_arithmetic_ast(node['left'])}{symbol}{_render_arithmetic_ast(node['right'])})"


def _require_keys(arguments: Mapping[str, Any], expected: set[str]) -> None:
    if set(arguments) != expected:
        raise ValueError("Tool arguments do not match the required schema.")


def _is_finite_number(value: object) -> bool:
    return type(value) in {int, float} and math.isfinite(float(value))


def _is_nonnegative_number(value: object) -> bool:
    return _is_finite_number(value) and float(value) >= 0


def _numeric_arguments(value: object) -> Iterator[int | float]:
    if type(value) in {int, float}:
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _numeric_arguments(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _numeric_arguments(item)


def _normalize_number(value: object) -> str:
    number = float(value.replace(",", "") if isinstance(value, str) else value)
    return str(int(number)) if number.is_integer() else format(number, ".15g")
