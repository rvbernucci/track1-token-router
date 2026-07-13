from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from typing import Any, Mapping

from router.core.contracts import TaskEnvelope
from router.core.tool_planner import ToolPlan, parse_tool_plan, validate_tool_plan_provenance
from router.orchestration.final_validator import apply_answer_contract


TOOL_EVIDENCE_SCHEMA_VERSION = "tool-evidence-v1"


@dataclass(frozen=True)
class ToolEvidence:
    tool: str
    normalized_inputs: Mapping[str, Any]
    steps: tuple[str, ...]
    result: str
    proof_hash: str
    schema_version: str = TOOL_EVIDENCE_SCHEMA_VERSION

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool": self.tool,
            "normalized_inputs": self.normalized_inputs,
            "steps": list(self.steps),
            "result": self.result,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.canonical_payload(), "proof_hash": self.proof_hash}


@dataclass(frozen=True)
class ToolRouteDecision:
    accepted: bool
    answer: str = ""
    reason: str = ""
    evidence: ToolEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "answer": self.answer,
            "reason": self.reason,
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


def execute_tool_plan(plan: ToolPlan) -> ToolEvidence:
    if plan.tool == "inventory_flow":
        evidence = _execute_inventory(plan.arguments)
    elif plan.tool == "recipe_cost":
        evidence = _execute_recipe(plan.arguments)
    elif plan.tool == "safe_calculator":
        evidence = _execute_calculator(plan.arguments)
    elif plan.tool == "logic_ordering":
        evidence = _execute_logic(plan.arguments)
    else:
        raise ValueError("The plan does not select an executable deterministic tool.")
    if not verify_tool_evidence(evidence):
        raise ValueError("Tool evidence failed independent recomputation.")
    return evidence


def verify_tool_evidence(evidence: ToolEvidence) -> bool:
    try:
        plan = ToolPlan(evidence.tool, evidence.normalized_inputs, "high")
        if evidence.tool == "inventory_flow":
            recomputed = _execute_inventory(plan.arguments)
        elif evidence.tool == "recipe_cost":
            recomputed = _execute_recipe(plan.arguments)
        elif evidence.tool == "safe_calculator":
            recomputed = _execute_calculator(plan.arguments)
        elif evidence.tool == "logic_ordering":
            recomputed = _execute_logic(plan.arguments)
        else:
            return False
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return False
    return recomputed.to_dict() == evidence.to_dict()


def run_tool_route(task: TaskEnvelope, raw_plan: str) -> ToolRouteDecision:
    try:
        plan = parse_tool_plan(raw_plan)
        return run_validated_tool_plan(task, plan)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        return ToolRouteDecision(False, reason=f"tool_route_rejected:{type(exc).__name__}")


def run_validated_tool_plan(task: TaskEnvelope, plan: ToolPlan) -> ToolRouteDecision:
    try:
        plan = validate_tool_plan_provenance(task.input_text, plan)
        if plan.tool == "none":
            return ToolRouteDecision(False, reason="planner_selected_none")
        evidence = execute_tool_plan(plan)
        contract = apply_answer_contract(task, evidence.result)
        if not contract.valid:
            return ToolRouteDecision(False, reason=f"answer_contract:{contract.reason}", evidence=evidence)
        return ToolRouteDecision(True, contract.answer, "verified_deterministic_tool", evidence)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        return ToolRouteDecision(False, reason=f"tool_route_rejected:{type(exc).__name__}")


def _execute_inventory(arguments: Mapping[str, Any]) -> ToolEvidence:
    current = _fraction(arguments["initial_stock"])
    steps = [f"start={_format_fraction(current)}"]
    if current < 0:
        raise ValueError("Inventory cannot start below zero.")
    for operation in arguments["operations"]:
        value = _fraction(operation["value"])
        if operation["type"] == "percent_sale":
            if not 0 <= value <= 100:
                raise ValueError("Invalid percentage.")
            current *= 1 - value / 100
        elif operation["type"] == "restock":
            current += value
        elif operation["type"] == "sale":
            current -= value
        else:
            raise ValueError("Unknown inventory operation.")
        if current < 0 or abs(current) > 10**15:
            raise ValueError("Inventory state is invalid.")
        steps.append(f"{operation['type']}({_format_fraction(value)})={_format_fraction(current)}")
    result = f"{_format_fraction(current)} units"
    return _evidence("inventory_flow", arguments, steps, result)


def _execute_recipe(arguments: Mapping[str, Any]) -> ToolEvidence:
    amount = Fraction(arguments["amount_numerator"], arguments["amount_denominator"])
    amount *= Fraction(arguments["target_count"], arguments["source_count"])
    cost = amount * _fraction(arguments["unit_price"])
    if amount < 0 or cost < 0 or abs(cost) > 10**15:
        raise ValueError("Recipe result is invalid.")
    result = f"{_format_fraction(amount)} cups; ${float(cost):.2f}"
    steps = (
        f"base={arguments['amount_numerator']}/{arguments['amount_denominator']}",
        f"scale={arguments['target_count']}/{arguments['source_count']}",
        f"amount={_format_fraction(amount)}",
        f"cost={_format_fraction(cost)}",
    )
    return _evidence("recipe_cost", arguments, steps, result)


def _execute_calculator(arguments: Mapping[str, Any]) -> ToolEvidence:
    value, steps = _evaluate_ast(arguments["ast"])
    return _evidence("safe_calculator", arguments, steps, _format_fraction(value))


def _evaluate_ast(node: Mapping[str, Any], *, depth: int = 0) -> tuple[Fraction, tuple[str, ...]]:
    if depth > 16:
        raise ValueError("Arithmetic AST is too deep.")
    op = node["op"]
    if op == "literal":
        value = _fraction(node["value"])
        return value, (f"literal={_format_fraction(value)}",)
    left, left_steps = _evaluate_ast(node["left"], depth=depth + 1)
    right, right_steps = _evaluate_ast(node["right"], depth=depth + 1)
    if op == "add":
        value = left + right
    elif op == "sub":
        value = left - right
    elif op == "mul":
        value = left * right
    elif op == "div":
        if right == 0:
            raise ZeroDivisionError("Division by zero.")
        value = left / right
    else:
        raise ValueError("Unsupported arithmetic operation.")
    if abs(value) > 10**15 or value.denominator > 10**12:
        raise OverflowError("Arithmetic result exceeds its bound.")
    step = f"{op}({_format_fraction(left)},{_format_fraction(right)})={_format_fraction(value)}"
    return value, (*left_steps, *right_steps, step)


def _execute_logic(arguments: Mapping[str, Any]) -> ToolEvidence:
    outgoing: dict[str, set[str]] = {}
    display: dict[str, str] = {}
    for relation in arguments["relations"]:
        left = relation["left"].casefold()
        right = relation["right"].casefold()
        display.setdefault(left, relation["left"])
        display.setdefault(right, relation["right"])
        greater, lesser = (left, right) if relation["relation"] == "greater_than" else (right, left)
        outgoing.setdefault(greater, set()).add(lesser)
        outgoing.setdefault(lesser, set())
    if _has_cycle(outgoing):
        raise ValueError("Logic relations contain a cycle.")
    query = arguments["query"]
    seek_greatest = query in {"tallest", "oldest", "heaviest"}
    incoming = {node: set() for node in outgoing}
    for greater, lesser_nodes in outgoing.items():
        for lesser in lesser_nodes:
            incoming[lesser].add(greater)
    candidates = [node for node in outgoing if not (incoming[node] if seek_greatest else outgoing[node])]
    if len(candidates) != 1 or not _is_connected(outgoing):
        raise ValueError("Logic endpoint is not unique or graph is disconnected.")
    result = display[candidates[0]]
    steps = tuple(
        f"{display[greater]}>{display[lesser]}"
        for greater in sorted(outgoing)
        for lesser in sorted(outgoing[greater])
    ) + (f"{query}={result}",)
    return _evidence("logic_ordering", arguments, steps, result)


def _has_cycle(graph: Mapping[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in graph[node]):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def _is_connected(graph: Mapping[str, set[str]]) -> bool:
    if not graph:
        return False
    undirected = {node: set(children) for node, children in graph.items()}
    for node, children in graph.items():
        for child in children:
            undirected[child].add(node)
    seen: set[str] = set()
    stack = [next(iter(graph))]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(undirected[node] - seen)
    return seen == set(graph)


def _evidence(tool: str, inputs: Mapping[str, Any], steps: tuple[str, ...] | list[str], result: str) -> ToolEvidence:
    normalized = json.loads(json.dumps(inputs, sort_keys=True, separators=(",", ":")))
    payload = {
        "schema_version": TOOL_EVIDENCE_SCHEMA_VERSION,
        "tool": tool,
        "normalized_inputs": normalized,
        "steps": list(steps),
        "result": result,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ToolEvidence(tool, normalized, tuple(steps), result, digest)


def _fraction(value: Any) -> Fraction:
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(str(value))
    raise TypeError("Expected a JSON number.")


def _format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return f"{value.numerator:,}"
    decimal = float(value)
    if len(str(value.denominator)) <= 3:
        return f"{decimal:.10f}".rstrip("0").rstrip(".")
    return f"{value.numerator}/{value.denominator}"
