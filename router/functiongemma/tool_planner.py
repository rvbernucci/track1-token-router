from __future__ import annotations

from collections.abc import Mapping

from router.core.tool_planner import ToolPlan
from router.functiongemma.tooling import _FunctionGemmaValueParser


PLANNER_FUNCTIONS = {"inventory_flow", "recipe_cost", "safe_calculator", "logic_ordering"}


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
