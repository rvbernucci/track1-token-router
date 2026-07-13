from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from router.core.tool_planner import ToolPlan
from router.functiongemma.tooling import _FunctionGemmaValueParser


PLANNER_FUNCTIONS = {"inventory_flow", "recipe_cost", "safe_calculator", "logic_ordering"}
PLANNER_DEVELOPER_INSTRUCTION = (
    "Select exactly one provided function. Never answer the task. Never invent arguments. "
    "Use decline_tool when unsupported, ambiguous, incomplete, or unsafe."
)


def planner_tools() -> list[dict[str, Any]]:
    """Return a fresh copy of the hash-pinned planner function contract."""
    import json

    return json.loads(json.dumps(_PLANNER_TOOLS))


_PLANNER_TOOLS = [
    {"type": "function", "function": {
        "name": "inventory_flow", "description": "Plan explicit ordered inventory sales and restocks.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "initial_stock": {"type": "number", "minimum": 0},
            "operations": {"type": "array", "minItems": 1, "maxItems": 12, "items": {
                "type": "object", "additionalProperties": False, "properties": {
                    "type": {"enum": ["percent_sale", "restock", "sale"]},
                    "value": {"type": "number", "minimum": 0},
                }, "required": ["type", "value"]}},
        }, "required": ["initial_stock", "operations"]},
    }},
    {"type": "function", "function": {
        "name": "recipe_cost", "description": "Plan explicit recipe scaling and per-cup cost.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "amount_numerator": {"type": "integer", "minimum": 0},
            "amount_denominator": {"type": "integer", "minimum": 1},
            "source_count": {"type": "integer", "minimum": 1},
            "target_count": {"type": "integer", "minimum": 0},
            "unit_price": {"type": "number", "minimum": 0},
        }, "required": ["amount_numerator", "amount_denominator", "source_count", "target_count", "unit_price"]},
    }},
    {"type": "function", "function": {
        "name": "safe_calculator", "description": "Plan an explicit bounded arithmetic expression as an AST.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "ast": {"type": "object"},
        }, "required": ["ast"]},
    }},
    {"type": "function", "function": {
        "name": "logic_ordering", "description": "Plan explicit comparative ordering relations and one endpoint query.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "relations": {"type": "array", "minItems": 1, "maxItems": 32, "items": {
                "type": "object", "additionalProperties": False, "properties": {
                    "left": {"type": "string"},
                    "relation": {"enum": ["greater_than", "less_than"]},
                    "right": {"type": "string"},
                }, "required": ["left", "relation", "right"]}},
            "query": {"enum": ["shortest", "tallest", "youngest", "oldest", "lightest", "heaviest"]},
        }, "required": ["relations", "query"]},
    }},
    {"type": "function", "function": {
        "name": "decline_tool", "description": "Decline when no supported deterministic tool is safe.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "reason": {"enum": ["unsupported", "ambiguous", "incomplete", "unsafe"]},
        }, "required": ["reason"]},
    }},
]


def tool_plan_from_function_call(text: str) -> ToolPlan:
    start_token = "<start_function_call>"
    end_token = "<end_function_call>"
    if text.count(start_token) != 1 or text.count(end_token) != 1:
        raise ValueError("Expected exactly one complete planner function call.")
    prefix, remainder = text.split(start_token, 1)
    body, suffix = remainder.split(end_token, 1)
    if prefix.strip() or suffix.strip() not in {"", "<end_of_turn>"}:
        raise ValueError("Planner function call contains additional text.")
    if not body.startswith("call:"):
        raise ValueError("Planner output is missing the native call marker.")
    function_and_args = body[len("call:"):]
    brace = function_and_args.find("{")
    if brace <= 0:
        raise ValueError("Planner function name or arguments are missing.")
    function_name = function_and_args[:brace].strip()
    parser = _FunctionGemmaValueParser(function_and_args[brace:])
    arguments = parser.parse_value()
    parser.require_end()
    if not isinstance(arguments, Mapping):
        raise ValueError("Planner function arguments must be an object.")
    if function_name == "decline_tool":
        if set(arguments) != {"reason"} or arguments["reason"] not in {"unsupported", "ambiguous", "incomplete", "unsafe"}:
            raise ValueError("decline_tool arguments are invalid.")
        return ToolPlan("none", {}, "low")
    if function_name not in PLANNER_FUNCTIONS:
        raise ValueError("Planner selected an unknown function.")
    return ToolPlan(function_name, dict(arguments), "high")


def tool_plan_from_openai_response(payload: Mapping[str, Any]) -> ToolPlan:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise ValueError("Planner response must contain exactly one choice.")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Planner response choice is missing its message.")
    calls = message.get("tool_calls")
    if isinstance(calls, list) and calls:
        if len(calls) != 1 or not isinstance(calls[0], Mapping):
            raise ValueError("Planner response must contain exactly one tool call.")
        function = calls[0].get("function")
        if not isinstance(function, Mapping) or not isinstance(function.get("name"), str):
            raise ValueError("Planner tool call is malformed.")
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            import json

            arguments = json.loads(arguments)
        if not isinstance(arguments, Mapping):
            raise ValueError("Planner tool arguments must be an object.")
        return _plan_from_name_and_arguments(function["name"], arguments)
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Planner response has neither a tool call nor native-call content.")
    if content.startswith("<start_function_call>") and "<end_function_call>" not in content:
        content += "<end_function_call>"
    return tool_plan_from_function_call(content)


def _plan_from_name_and_arguments(function_name: str, arguments: Mapping[str, Any]) -> ToolPlan:
    if function_name == "decline_tool":
        if set(arguments) != {"reason"} or arguments["reason"] not in {"unsupported", "ambiguous", "incomplete", "unsafe"}:
            raise ValueError("decline_tool arguments are invalid.")
        return ToolPlan("none", {}, "low")
    if function_name not in PLANNER_FUNCTIONS:
        raise ValueError("Planner selected an unknown function.")
    return ToolPlan(function_name, dict(arguments), "high")
