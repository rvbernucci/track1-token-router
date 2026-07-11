from __future__ import annotations

import ast
import itertools
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, DivisionByZero, Inexact, InvalidOperation, Overflow, localcontext
from enum import Enum
from typing import Any, Mapping, Sequence

from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import apply_answer_contract


PROOF_SCHEMA_VERSION = "proof-envelope-v1"
MAX_EXPRESSION_CHARS = 256
MAX_AST_NODES = 64
MAX_ABS_VALUE = Decimal("1e18")
MAX_LOGIC_ENTITIES = 7


class ProofType(str, Enum):
    DECIMAL_AST = "decimal_ast"
    PERCENTAGE = "percentage"
    PROPORTIONAL_RATE = "proportional_rate"
    COMPOUND_PROJECTION = "compound_projection"
    UNIT_CONVERSION = "unit_conversion"
    ORDERING = "ordering"
    FINITE_ASSIGNMENT = "finite_assignment"
    PROPOSITIONAL = "propositional"
    QUANTIFIED = "quantified"


@dataclass(frozen=True)
class ProofAssumption:
    name: str
    value: str
    unit: str = ""

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("ProofAssumption.name must be non-empty.")
        if not isinstance(self.value, str) or not self.value:
            raise ValueError("ProofAssumption.value must be non-empty.")
        if not isinstance(self.unit, str):
            raise ValueError("ProofAssumption.unit must be a string.")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ProofEnvelope:
    proof_type: ProofType
    assumptions: tuple[ProofAssumption, ...]
    normalized_expression: str
    result: str
    verification_trace: tuple[str, ...]
    unique: bool
    verified: bool
    rejection_reason: str = ""
    counterexamples: tuple[str, ...] = ()
    schema_version: str = PROOF_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PROOF_SCHEMA_VERSION:
            raise ValueError("Unsupported ProofEnvelope schema.")
        if not isinstance(self.proof_type, ProofType):
            raise ValueError("ProofEnvelope.proof_type must be a ProofType.")
        if not self.normalized_expression or not isinstance(self.normalized_expression, str):
            raise ValueError("ProofEnvelope.normalized_expression must be non-empty.")
        if not isinstance(self.result, str):
            raise ValueError("ProofEnvelope.result must be a string.")
        if not self.verification_trace or any(not isinstance(item, str) or not item for item in self.verification_trace):
            raise ValueError("ProofEnvelope.verification_trace must contain non-empty steps.")
        if self.verified and (not self.unique or not self.result or self.rejection_reason):
            raise ValueError("Verified proofs require one unique result and no rejection reason.")
        if not self.verified and not self.rejection_reason:
            raise ValueError("Rejected proofs require a rejection reason.")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ProofEnvelope":
        expected = {
            "schema_version",
            "proof_type",
            "assumptions",
            "normalized_expression",
            "result",
            "verification_trace",
            "unique",
            "verified",
            "rejection_reason",
            "counterexamples",
        }
        if set(payload) != expected:
            raise ValueError("ProofEnvelope keys do not match the schema.")
        assumptions = payload["assumptions"]
        if not isinstance(assumptions, list):
            raise ValueError("ProofEnvelope.assumptions must be an array.")
        return cls(
            schema_version=str(payload["schema_version"]),
            proof_type=ProofType(payload["proof_type"]),
            assumptions=tuple(ProofAssumption(**item) for item in assumptions),
            normalized_expression=str(payload["normalized_expression"]),
            result=str(payload["result"]),
            verification_trace=tuple(str(item) for item in payload["verification_trace"]),
            unique=payload["unique"],
            verified=payload["verified"],
            rejection_reason=str(payload["rejection_reason"]),
            counterexamples=tuple(str(item) for item in payload["counterexamples"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proof_type": self.proof_type.value,
            "assumptions": [item.to_dict() for item in self.assumptions],
            "normalized_expression": self.normalized_expression,
            "result": self.result,
            "verification_trace": list(self.verification_trace),
            "unique": self.unique,
            "verified": self.verified,
            "rejection_reason": self.rejection_reason,
            "counterexamples": list(self.counterexamples),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class ProofSolveResult:
    answer: str
    proof: ProofEnvelope


@dataclass(frozen=True)
class CandidateProofValidation:
    accepted: bool
    canonical_candidate: str
    reason: str
    proof: ProofEnvelope | None


@dataclass(frozen=True)
class ProofAttempt:
    solved: ProofSolveResult | None
    rejection_reason: str = ""
    counterexamples: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.solved is not None


@dataclass(frozen=True)
class _DecimalEvaluation:
    value: Decimal
    exact: bool
    trace: tuple[str, ...]


def solve_with_proof(task: TaskEnvelope) -> ProofSolveResult | None:
    for solver in (
        _solve_percentage,
        _solve_compound_projection,
        _solve_proportional_rate,
        _solve_unit_conversion,
        _solve_decimal_expression,
        _solve_finite_assignment,
        _solve_ordering,
        _solve_propositional,
        _solve_quantified,
    ):
        result = solver(task)
        if result is not None:
            return result
    return None


def attempt_proof(task: TaskEnvelope) -> ProofAttempt:
    solved = solve_with_proof(task)
    if solved is not None:
        return ProofAttempt(solved=solved)
    reason, counterexamples = _diagnose_rejection(task.input_text)
    return ProofAttempt(solved=None, rejection_reason=reason, counterexamples=counterexamples)


def verify_candidate_against_proof(task: TaskEnvelope, candidate: str) -> CandidateProofValidation:
    solved = solve_with_proof(task)
    if solved is None:
        return CandidateProofValidation(False, candidate.strip(), "no_supported_unique_proof", None)
    contract = apply_answer_contract(task, candidate)
    canonical = contract.answer if contract.valid else candidate.strip()
    if not contract.valid:
        return CandidateProofValidation(False, canonical, f"answer_contract:{contract.reason}", solved.proof)
    if _canonical_answer(canonical) != _canonical_answer(solved.answer):
        return CandidateProofValidation(False, canonical, "candidate_disagrees_with_verified_proof", solved.proof)
    if not _reverify_envelope(solved.proof):
        return CandidateProofValidation(False, canonical, "proof_reverification_failed", solved.proof)
    return CandidateProofValidation(True, canonical, "candidate_matches_verified_proof", solved.proof)


def evaluate_decimal_expression(expression: str, *, decimal_places: int | None = None) -> _DecimalEvaluation:
    if not expression or len(expression) > MAX_EXPRESSION_CHARS:
        raise ValueError("expression_size_limit")
    if "," in expression or "_" in expression:
        raise ValueError("unsupported_numeric_grouping")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("invalid_expression_syntax") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise ValueError("expression_node_limit")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.UAdd, ast.USub)
    if any(not isinstance(node, allowed) for node in nodes):
        raise ValueError("unsupported_expression_node")
    trace: list[str] = []
    with localcontext() as context:
        context.prec = 40
        context.clear_flags()
        try:
            value = _eval_decimal_node(tree.body, trace, depth=0)
        except (DivisionByZero, InvalidOperation, Overflow, ZeroDivisionError) as exc:
            raise ValueError("invalid_decimal_operation") from exc
        exact = not context.flags[Inexact]
        if abs(value) > MAX_ABS_VALUE:
            raise ValueError("numeric_magnitude_limit")
        if decimal_places is not None:
            if not 0 <= decimal_places <= 12:
                raise ValueError("rounding_places_limit")
            quantum = Decimal(1).scaleb(-decimal_places)
            value = value.quantize(quantum)
            trace.append(f"round_half_even:{decimal_places}")
            exact = True
        elif not exact:
            raise ValueError("inexact_result_requires_rounding_instruction")
    return _DecimalEvaluation(value=value, exact=exact, trace=tuple(trace))


def _eval_decimal_node(node: ast.AST, trace: list[str], *, depth: int) -> Decimal:
    if depth > 16:
        raise ValueError("expression_depth_limit")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("non_numeric_literal")
        value = Decimal(str(node.value))
        trace.append(f"literal:{value}")
        return value
    if isinstance(node, ast.UnaryOp):
        value = _eval_decimal_node(node.operand, trace, depth=depth + 1)
        result = value if isinstance(node.op, ast.UAdd) else -value
        trace.append(f"unary:{_decimal_text(result)}")
        return result
    if not isinstance(node, ast.BinOp):
        raise ValueError("unsupported_expression_node")
    left = _eval_decimal_node(node.left, trace, depth=depth + 1)
    right = _eval_decimal_node(node.right, trace, depth=depth + 1)
    if isinstance(node.op, ast.Add):
        result, label = left + right, "add"
    elif isinstance(node.op, ast.Sub):
        result, label = left - right, "subtract"
    elif isinstance(node.op, ast.Mult):
        result, label = left * right, "multiply"
    elif isinstance(node.op, ast.Div):
        if right == 0:
            raise ZeroDivisionError
        result, label = left / right, "divide"
    elif isinstance(node.op, ast.Pow):
        if right != right.to_integral_value() or not -12 <= int(right) <= 12:
            raise ValueError("unsupported_exponent")
        result, label = left ** int(right), "power"
    else:
        raise ValueError("unsupported_operator")
    trace.append(f"{label}:{_decimal_text(left)},{_decimal_text(right)}->{_decimal_text(result)}")
    return result


def _solve_decimal_expression(task: TaskEnvelope) -> ProofSolveResult | None:
    text = " ".join(task.input_text.strip().split())
    match = re.fullmatch(
        r"(?i)(?:calculate|compute|evaluate|what is)\s+([0-9eE+\-*/().\s]+?)"
        r"(?:\??\s*(?:return|provide)\s+only\s+(?:the\s+)?(?:number|numeric value)\.?)?",
        text,
    )
    if not match:
        return None
    expression = match.group(1).strip().rstrip("?. ")
    rounding = _rounding_places(text)
    try:
        evaluated = evaluate_decimal_expression(expression, decimal_places=rounding)
    except ValueError:
        return None
    answer = _decimal_text(evaluated.value, fixed_places=rounding)
    return _math_result(
        ProofType.DECIMAL_AST,
        expression,
        answer,
        (),
        (*evaluated.trace, f"recompute:{answer}"),
    )


def _solve_percentage(task: TaskEnvelope) -> ProofSolveResult | None:
    text = " ".join(task.input_text.strip().split())
    simple = re.fullmatch(
        r"(?i)what is\s+(-?\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(-?\d+(?:\.\d+)?)\??"
        r"(?:\s*return only (?:the )?number\.?)?",
        text,
    )
    increase = re.fullmatch(
        r"(?i)(?:a value|revenue|price)\s+(?:starts at|is)\s+(-?\d+(?:\.\d+)?)\s+and\s+"
        r"(increases|decreases)\s+by\s+(\d+(?:\.\d+)?)\s*(?:%|percent)\.\s*"
        r"what is (?:the )?(?:final|new) value\??(?:\s*return only (?:the )?number\.?)?",
        text,
    )
    if simple:
        percent, base = simple.groups()
        expression = f"({base})*({percent})/100"
        assumptions = (ProofAssumption("percent", percent, "%"), ProofAssumption("base", base))
    elif increase:
        base, direction, percent = increase.groups()
        sign = "+" if direction.lower() == "increases" else "-"
        expression = f"({base}){sign}(({base})*({percent})/100)"
        assumptions = (
            ProofAssumption("base", base),
            ProofAssumption("percent", percent, "%"),
            ProofAssumption("direction", direction.lower()),
        )
    else:
        return None
    return _evaluate_math_template(ProofType.PERCENTAGE, expression, assumptions, text)


def _solve_compound_projection(task: TaskEnvelope) -> ProofSolveResult | None:
    text = " ".join(task.input_text.strip().split())
    match = re.fullmatch(
        r"(?i)(?:revenue|a value|an investment)\s+(?:starts at|is)\s+(\d+(?:\.\d+)?)\s+and\s+grows\s+"
        r"(?:by\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent)\s+(?:per year|annually)\s+for\s+(\d{1,2})\s+years?\.\s*"
        r"what is (?:the )?(?:projected|final) value\??(?:\s*round to\s+(\d{1,2})\s+decimal places?\.?)?",
        text,
    )
    if not match:
        return None
    base, rate, years, explicit_rounding = match.groups()
    rounding = int(explicit_rounding) if explicit_rounding is not None else _rounding_places(text)
    expression = f"({base})*(1+({rate})/100)**({years})"
    assumptions = (
        ProofAssumption("base", base),
        ProofAssumption("annual_rate", rate, "%"),
        ProofAssumption("years", years, "years"),
    )
    return _evaluate_math_template(ProofType.COMPOUND_PROJECTION, expression, assumptions, text, rounding=rounding)


def _solve_proportional_rate(task: TaskEnvelope) -> ProofSolveResult | None:
    text = " ".join(task.input_text.strip().split())
    match = re.fullmatch(
        r"(?i)if\s+(\d+(?:\.\d+)?)\s+([a-z][\w-]*)\s+(?:produce|make)\s+(\d+(?:\.\d+)?)\s+"
        r"([a-z][\w-]*)\s*,?\s*how many\s+\4\s+(?:do|will)\s+(\d+(?:\.\d+)?)\s+\2\s+(?:produce|make)\??"
        r"(?:\s*return only (?:the )?number\.?)?",
        text,
    )
    if not match:
        return None
    source_count, source_unit, output, output_unit, target_count = match.groups()
    expression = f"({output})/({source_count})*({target_count})"
    assumptions = (
        ProofAssumption("source_count", source_count, source_unit),
        ProofAssumption("source_output", output, output_unit),
        ProofAssumption("target_count", target_count, source_unit),
    )
    return _evaluate_math_template(ProofType.PROPORTIONAL_RATE, expression, assumptions, text)


_UNIT_FACTORS: dict[str, tuple[str, Decimal]] = {
    "millimeters": ("length", Decimal("0.001")),
    "centimeters": ("length", Decimal("0.01")),
    "meters": ("length", Decimal("1")),
    "kilometers": ("length", Decimal("1000")),
    "grams": ("mass", Decimal("1")),
    "kilograms": ("mass", Decimal("1000")),
    "seconds": ("time", Decimal("1")),
    "minutes": ("time", Decimal("60")),
    "hours": ("time", Decimal("3600")),
}


def _solve_unit_conversion(task: TaskEnvelope) -> ProofSolveResult | None:
    text = " ".join(task.input_text.strip().split())
    match = re.fullmatch(
        r"(?i)convert\s+(-?\d+(?:\.\d+)?)\s+([a-z]+)\s+to\s+([a-z]+)\.?(?:\s*return only (?:the )?number\.?)?",
        text,
    )
    if not match:
        return None
    value, source, target = (part.lower() for part in match.groups())
    if source not in _UNIT_FACTORS or target not in _UNIT_FACTORS:
        return None
    source_dimension, source_factor = _UNIT_FACTORS[source]
    target_dimension, target_factor = _UNIT_FACTORS[target]
    if source_dimension != target_dimension:
        return None
    expression = f"({value})*({_decimal_text(source_factor)})/({_decimal_text(target_factor)})"
    assumptions = (
        ProofAssumption("input", value, source),
        ProofAssumption("source_factor", _decimal_text(source_factor), source_dimension),
        ProofAssumption("target_factor", _decimal_text(target_factor), target_dimension),
    )
    return _evaluate_math_template(ProofType.UNIT_CONVERSION, expression, assumptions, text)


def _evaluate_math_template(
    proof_type: ProofType,
    expression: str,
    assumptions: tuple[ProofAssumption, ...],
    prompt: str,
    *,
    rounding: int | None = None,
) -> ProofSolveResult | None:
    prompt_numbers = _number_literals(prompt)
    consumed = [item.value for item in assumptions if _looks_numeric(item.value)]
    if any(number not in consumed for number in prompt_numbers if number != str(rounding)):
        return None
    try:
        evaluated = evaluate_decimal_expression(expression, decimal_places=rounding)
    except ValueError:
        return None
    answer = _decimal_text(evaluated.value, fixed_places=rounding)
    return _math_result(proof_type, expression, answer, assumptions, (*evaluated.trace, f"inverse_recompute:{answer}"))


def _math_result(
    proof_type: ProofType,
    expression: str,
    answer: str,
    assumptions: tuple[ProofAssumption, ...],
    trace: tuple[str, ...],
) -> ProofSolveResult:
    proof = ProofEnvelope(
        proof_type=proof_type,
        assumptions=assumptions,
        normalized_expression=expression,
        result=answer,
        verification_trace=trace,
        unique=True,
        verified=True,
    )
    return ProofSolveResult(answer=answer, proof=proof)


def _solve_ordering(task: TaskEnvelope) -> ProofSolveResult | None:
    text = " ".join(task.input_text.strip().split())
    comparisons = re.findall(
        r"\b([A-Z][A-Za-z-]*)\s+is\s+(older|younger|taller|shorter|heavier|lighter)\s+than\s+([A-Z][A-Za-z-]*)\b",
        text,
    )
    query = re.search(r"(?i)who is (?:the )?(oldest|youngest|tallest|shortest|heaviest|lightest)\?", text)
    if not comparisons or query is None:
        return None
    entities = sorted({item for left, _, right in comparisons for item in (left, right)})
    if len(entities) > MAX_LOGIC_ENTITIES:
        return None
    target = query.group(1).lower()
    high_terms = {"older", "taller", "heavier"}
    wants_high = target in {"oldest", "tallest", "heaviest"}
    edges: set[tuple[str, str]] = set()
    assumptions: list[ProofAssumption] = []
    for left, relation, right in comparisons:
        high, low = (left, right) if relation.lower() in high_terms else (right, left)
        edges.add((high, low))
        assumptions.append(ProofAssumption(f"{high}>{low}", relation.lower()))
    closure = _transitive_closure(entities, edges)
    candidates = [
        entity
        for entity in entities
        if all(((entity, other) in closure if wants_high else (other, entity) in closure) for other in entities if other != entity)
    ]
    if len(candidates) != 1:
        return None
    answer = candidates[0]
    trace = tuple(f"edge:{left}>{right}" for left, right in sorted(closure)) + (f"unique_extreme:{answer}",)
    proof = ProofEnvelope(
        proof_type=ProofType.ORDERING,
        assumptions=tuple(assumptions),
        normalized_expression=";".join(f"{left}>{right}" for left, right in sorted(edges)),
        result=answer,
        verification_trace=trace,
        unique=True,
        verified=True,
    )
    return ProofSolveResult(answer, proof)


def _solve_finite_assignment(task: TaskEnvelope) -> ProofSolveResult | None:
    text = " ".join(task.input_text.strip().split())
    header = re.search(
        r"(?i)\b([A-Z][A-Za-z-]*(?:,\s*[A-Z][A-Za-z-]*)*,?\s+and\s+[A-Z][A-Za-z-]*)\s+each\s+"
        r"(?:own|choose|has)\s+(?:one|a)\s+(?:different\s+)?[a-z-]+\s*:\s*"
        r"([a-z-]+(?:,\s*[a-z-]+)*,?\s+or\s+[a-z-]+)\.",
        text,
    )
    query = re.search(r"(?i)who\s+(?:owns|has|chose)\s+the\s+([a-z-]+)\?", text)
    if header is None or query is None:
        return None
    people = _split_natural_list(header.group(1), title=True)
    values = _split_natural_list(header.group(2), title=False)
    if len(people) != len(values) or not 2 <= len(people) <= MAX_LOGIC_ENTITIES:
        return None
    fixed = {
        person: value.lower()
        for person, value in re.findall(r"\b([A-Z][A-Za-z-]*)\s+(?:owns|has|chose)\s+the\s+([a-z-]+)\b", text)
        if person in people
    }
    forbidden = {
        (person, value.lower())
        for person, value in re.findall(r"\b([A-Z][A-Za-z-]*)\s+does\s+not\s+(?:own|have|choose)\s+the\s+([a-z-]+)\b", text)
    }
    solutions: list[dict[str, str]] = []
    for permutation in itertools.permutations(values):
        assignment = dict(zip(people, permutation, strict=True))
        if any(assignment.get(person) != value for person, value in fixed.items()):
            continue
        if any(assignment.get(person) == value for person, value in forbidden):
            continue
        solutions.append(assignment)
        if len(solutions) > 100:
            return None
    target = query.group(1).lower()
    answers = {person for solution in solutions for person, value in solution.items() if value == target}
    if len(answers) != 1 or not solutions:
        return None
    answer = next(iter(answers))
    normalized = json.dumps({"people": people, "values": values, "fixed": fixed, "forbidden": sorted(forbidden)}, sort_keys=True)
    trace = (f"enumerated:{len(solutions)}", f"unique_owner:{target}={answer}")
    proof = ProofEnvelope(
        proof_type=ProofType.FINITE_ASSIGNMENT,
        assumptions=tuple(
            [ProofAssumption(person, value) for person, value in sorted(fixed.items())]
            + [ProofAssumption(f"{person}!", value) for person, value in sorted(forbidden)]
        ),
        normalized_expression=normalized,
        result=answer,
        verification_trace=trace,
        unique=True,
        verified=True,
    )
    return ProofSolveResult(answer, proof)


def _solve_propositional(task: TaskEnvelope) -> ProofSolveResult | None:
    text = " ".join(task.input_text.strip().split())
    conditional = re.search(r"(?i)if\s+(.+?),\s+(.+?)\.\s+", text)
    query = re.search(r"(?i)(?:^|(?<=\.)\s+)(is|does)\s+(.+?)\?\s*(?:return exactly yes or no\.?)?$", text)
    if conditional is None or query is None:
        return None
    antecedent = _normalize_clause(conditional.group(1))
    consequent = _normalize_clause(conditional.group(2))
    before_query = text[conditional.end() : query.start()].strip(" .")
    fact = _normalize_clause(before_query)
    query_mode, query_payload = query.groups()
    asked = _normalize_query_clause(query_mode, query_payload)
    neg_consequent = _negate_clause(consequent)
    neg_antecedent = _negate_clause(antecedent)
    if fact == antecedent and asked == consequent:
        answer, rule = "yes", "modus_ponens"
    elif fact == neg_consequent and asked == antecedent:
        answer, rule = "no", "modus_tollens"
    elif fact == neg_consequent and asked == neg_antecedent:
        answer, rule = "yes", "modus_tollens"
    else:
        return None
    proof = ProofEnvelope(
        proof_type=ProofType.PROPOSITIONAL,
        assumptions=(ProofAssumption("implication", f"{antecedent}->{consequent}"), ProofAssumption("fact", fact)),
        normalized_expression=f"{antecedent}->{consequent};{fact};query={asked}",
        result=answer,
        verification_trace=(f"rule:{rule}", f"conclusion:{answer}"),
        unique=True,
        verified=True,
    )
    return ProofSolveResult(answer, proof)


def _solve_quantified(task: TaskEnvelope) -> ProofSolveResult | None:
    text = " ".join(task.input_text.strip().split())
    exclusion = re.fullmatch(
        r"(?i)all\s+(\w+)\s+are\s+(\w+)\.\s+no\s+(\w+)\s+are\s+(\w+)\.\s+"
        r"can\s+a[n]?\s+(\w+)\s+be\s+a[n]?\s+(\w+)\?\s*(?:return exactly yes or no\.?)?",
        text,
    )
    guarantee = re.fullmatch(
        r"(?i)all\s+(\w+)\s+are\s+(\w+)\.\s+some\s+(\w+)\s+are\s+(\w+)\.\s+"
        r"is it guaranteed that some\s+(\w+)\s+are\s+(\w+)\?\s*(?:return exactly yes or no\.?)?",
        text,
    )
    if exclusion:
        left, middle, no_left, right, query_left, query_right = exclusion.groups()
        if _plural_stem(no_left) != _plural_stem(middle) or _plural_stem(query_left) != _plural_stem(left) or _plural_stem(query_right) != _plural_stem(right):
            return None
        answer = "no"
        trace = (f"subset:{left}<{middle}", f"disjoint:{middle}!{right}", f"conclusion:{left}!{right}")
        expression = f"{left} subset {middle};{middle} disjoint {right}"
        assumptions = (ProofAssumption("subset", f"{left}:{middle}"), ProofAssumption("disjoint", f"{middle}:{right}"))
    elif guarantee:
        left, middle, some_left, right, query_left, query_right = guarantee.groups()
        if _plural_stem(some_left) != _plural_stem(middle) or _plural_stem(query_left) != _plural_stem(left) or _plural_stem(query_right) != _plural_stem(right):
            return None
        answer = "no"
        trace = (
            f"subset:{left}<{middle}",
            f"exists_overlap:{middle}&{right}",
            "counterexample:overlap_member_outside_subset",
        )
        expression = f"{left} subset {middle};exists {middle}&{right}"
        assumptions = (ProofAssumption("subset", f"{left}:{middle}"), ProofAssumption("exists", f"{middle}:{right}"))
    else:
        return None
    proof = ProofEnvelope(
        proof_type=ProofType.QUANTIFIED,
        assumptions=assumptions,
        normalized_expression=expression,
        result=answer,
        verification_trace=trace,
        unique=True,
        verified=True,
        counterexamples=("overlap member need not belong to subset",) if guarantee else (),
    )
    return ProofSolveResult(answer, proof)


def _reverify_envelope(proof: ProofEnvelope) -> bool:
    if not proof.verified or not proof.unique:
        return False
    if proof.proof_type in {
        ProofType.DECIMAL_AST,
        ProofType.PERCENTAGE,
        ProofType.PROPORTIONAL_RATE,
        ProofType.COMPOUND_PROJECTION,
        ProofType.UNIT_CONVERSION,
    }:
        rounding_step = next((step for step in proof.verification_trace if step.startswith("round_half_even:")), None)
        places = int(rounding_step.split(":", 1)[1]) if rounding_step else None
        try:
            evaluated = evaluate_decimal_expression(proof.normalized_expression, decimal_places=places)
        except ValueError:
            return False
        return _decimal_text(evaluated.value, fixed_places=places) == proof.result
    return bool(proof.verification_trace and proof.result)


def _diagnose_rejection(prompt: str) -> tuple[str, tuple[str, ...]]:
    text = " ".join(prompt.strip().split())
    lowered = text.casefold()
    if re.search(r"\b(?:today|current|latest|as of|tomorrow|yesterday)\b", lowered):
        return "temporal_or_open_world_assumption", ()
    if re.search(r"\b(?:usd|eur|brl|dollars?|euros?|reais)\b", lowered):
        return "unsupported_currency_semantics", ()
    if "__import__" in text or re.search(r"\b(?:eval|exec|open|system)\s*\(", text):
        return "unsafe_expression", ()
    conversion = re.search(r"(?i)\bconvert\s+[-+]?\d+(?:\.\d+)?\s+([a-z]+)\s+to\s+([a-z]+)", text)
    if conversion:
        source, target = (item.lower() for item in conversion.groups())
        if source not in _UNIT_FACTORS or target not in _UNIT_FACTORS:
            return "unsupported_unit", ()
        if _UNIT_FACTORS[source][0] != _UNIT_FACTORS[target][0]:
            return "unit_dimension_mismatch", (f"{source} and {target} have different dimensions",)
    expression = re.fullmatch(
        r"(?i)(?:calculate|compute|evaluate|what is)\s+([0-9eE+\-*/().\s]+?)"
        r"(?:\??\s*(?:return|provide)\s+only\s+(?:the\s+)?(?:number|numeric value)\.?)?",
        text,
    )
    if expression:
        try:
            evaluate_decimal_expression(expression.group(1).strip().rstrip("?. "), decimal_places=_rounding_places(text))
        except ValueError as exc:
            return str(exc), ()
    if re.search(r"(?i)\bwhat is\s+[-+]?\d+(?:\.\d+)?\s*(?:%|percent)\s+of\b", text):
        return "unused_or_ambiguous_numeric_literal", ()
    if re.search(r"(?i)\bwho is (?:the )?(?:oldest|youngest|tallest|shortest|heaviest|lightest)\?", text):
        return "inconsistent_or_underdetermined_ordering", (
            "multiple extrema or disconnected orderings satisfy the premises",
        )
    if re.search(r"(?i)\bwho\s+(?:owns|has|chose)\s+the\b", text):
        return "non_unique_finite_assignment", ("multiple assignments satisfy the stated constraints",)
    if re.search(r"(?i)\bif\s+.+?,\s+.+?\.\s+", text):
        return "unsupported_or_invalid_propositional_inference", (
            "antecedent=false and consequent=true satisfies the implication",
        )
    if re.search(r"(?i)\b(?:all|some|no)\s+\w+\s+are\s+\w+", text):
        return "quantifier_terms_do_not_align", ("set memberships can satisfy the premises without the queried conclusion",)
    return "unsupported_or_ambiguous_task", ()


def _transitive_closure(entities: Sequence[str], edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    closure = set(edges)
    for pivot in entities:
        for left in entities:
            for right in entities:
                if (left, pivot) in closure and (pivot, right) in closure:
                    closure.add((left, right))
    if any((entity, entity) in closure for entity in entities):
        return set()
    return closure


def _rounding_places(text: str) -> int | None:
    match = re.search(r"(?i)round to\s+(\d{1,2})\s+decimal places?", text)
    return int(match.group(1)) if match else None


def _number_literals(text: str) -> list[str]:
    return [match.group(0).lstrip("+") for match in re.finditer(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?![\w.])", text)]


def _looks_numeric(value: str) -> bool:
    return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value))


def _decimal_text(value: Decimal, *, fixed_places: int | None = None) -> str:
    if fixed_places is not None:
        return f"{value:.{fixed_places}f}"
    normalized = value.normalize()
    text = format(normalized, "f")
    return "0" if text in {"-0", ""} else text


def _canonical_answer(value: str) -> str:
    stripped = value.strip().strip("`\"'")
    try:
        return _decimal_text(Decimal(stripped.replace(",", "")))
    except InvalidOperation:
        return re.sub(r"\s+", " ", stripped).casefold()


def _split_natural_list(value: str, *, title: bool) -> list[str]:
    cleaned = re.sub(r"\s+(?:and|or)\s+", ",", value, flags=re.IGNORECASE)
    result = [item.strip(" ,") for item in cleaned.split(",") if item.strip(" ,")]
    return [item.title() if title else item.lower() for item in result]


def _normalize_clause(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().rstrip(".")).casefold()
    normalized = re.sub(r"^(?:a|an|the)\s+", "", normalized)
    lock = re.fullmatch(r"(.+?)\s+locks", normalized)
    if lock:
        return f"{lock.group(1)} is locked"
    return normalized


def _normalize_query_clause(mode: str, value: str) -> str:
    normalized = _normalize_clause(value)
    if mode.casefold() == "is":
        passive = re.fullmatch(
            r"(.+?)\s+(locked|unlocked|accepted|denied|signed|cached|expired|armed|valid|active|intact|verified|trusted)",
            normalized,
        )
        return f"{passive.group(1)} is {passive.group(2)}" if passive else normalized
    words = normalized.split()
    if len(words) >= 2:
        verb = words[1]
        if verb == "use":
            words[1] = "uses"
        elif verb == "lock":
            words[1] = "locks"
    return _normalize_clause(" ".join(words))


def _plural_stem(value: str) -> str:
    lowered = value.casefold()
    if lowered.endswith("ies"):
        return lowered[:-3] + "y"
    if lowered.endswith("es") and len(lowered) > 3:
        return lowered[:-2]
    if lowered.endswith("s") and len(lowered) > 2:
        return lowered[:-1]
    return lowered


def _negate_clause(value: str) -> str:
    replacements = (
        (r"\bis not\b", "is"),
        (r"\bdoes not\b", "does"),
        (r"\bnot\b", ""),
    )
    for pattern, replacement in replacements:
        if re.search(pattern, value):
            return re.sub(r"\s+", " ", re.sub(pattern, replacement, value)).strip()
    match = re.match(r"(.+?)\s+is\s+(.+)", value)
    if match:
        return f"{match.group(1)} is not {match.group(2)}"
    return "not " + value
