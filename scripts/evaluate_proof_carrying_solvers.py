#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics
import sys
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.proof_engine import ProofEnvelope, attempt_proof, verify_candidate_against_proof


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate proof-carrying math and logic solvers.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/proof-carrying/math-logic-holdout.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/generated/math-logic-proof-coverage.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/proof-carrying-math-logic.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    result = evaluate(_absolute(args.dataset))
    _write_json(_absolute(args.output), result)
    report = _absolute(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_markdown(result), encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0 if result["gate"]["passed"] or not args.check else 1


def evaluate(dataset: Path) -> dict[str, Any]:
    rows = _jsonl(dataset)
    counts: Counter[str] = Counter()
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    failures: list[dict[str, str]] = []
    math_ms: list[float] = []
    logic_ms: list[float] = []
    for row in rows:
        task = TaskEnvelope(id=str(row["id"]), input_text=str(row["prompt"]))
        started = perf_counter()
        attempt = attempt_proof(task)
        solved = attempt.solved
        elapsed_ms = (perf_counter() - started) * 1000
        expected_accept = bool(row["expected_accept"])
        family = str(row["family"])
        latency_bucket = logic_ms if family in {"ordering", "propositional", "quantified", "finite_assignment", "ordering_cycle", "ordering_disconnected", "assignment_underdetermined", "invalid_converse", "quantifier_mismatch"} else math_ms
        latency_bucket.append(elapsed_ms)
        counts["rows"] += 1
        by_family[family]["rows"] += 1
        if solved is None:
            counts["refused"] += 1
            by_family[family]["refused"] += 1
            if expected_accept:
                counts["false_negative"] += 1
                failures.append({"id": str(row["id"]), "reason": "expected_accept_but_refused"})
            else:
                counts["true_negative"] += 1
                by_family[family][f"rejection:{attempt.rejection_reason}"] += 1
            continue
        counts["released"] += 1
        by_family[family]["released"] += 1
        roundtrip = ProofEnvelope.from_mapping(json.loads(solved.proof.to_json())) == solved.proof
        expected_answer = str(row.get("expected_answer") or "")
        correct = expected_accept and solved.answer == expected_answer and solved.proof.verified and roundtrip
        validation = verify_candidate_against_proof(task, solved.answer)
        wrong_validation = verify_candidate_against_proof(task, _wrong_answer(solved.answer))
        correct = correct and validation.accepted and not wrong_validation.accepted
        if correct:
            counts["true_positive"] += 1
            by_family[family]["true_positive"] += 1
        else:
            counts["false_positive"] += 1
            by_family[family]["false_positive"] += 1
            failures.append(
                {
                    "id": str(row["id"]),
                    "reason": "unexpected_or_unverified_release",
                    "answer": solved.answer,
                    "expected": expected_answer,
                }
            )
    released = counts["released"]
    precision = counts["true_positive"] / released if released else 0.0
    wilson = _wilson_lower(counts["true_positive"], released)
    static_security = _static_security_check(ROOT / "router/orchestration/proof_engine.py")
    math_p95 = _percentile(math_ms, 95)
    logic_p95 = _percentile(logic_ms, 95)
    gate = {
        "zero_false_positive": counts["false_positive"] == 0,
        "precision_at_least_95": precision >= 0.95,
        "wilson_lower_above_90": wilson > 0.90,
        "math_p95_below_100_ms": math_p95 < 100,
        "logic_p95_below_500_ms": logic_p95 < 500,
        "static_security": static_security["passed"],
    }
    gate["passed"] = all(gate.values())
    return {
        "schema_version": "proof-carrying-evaluation-v1",
        "dataset": str(dataset),
        "summary": {
            **dict(sorted(counts.items())),
            "released_precision": precision,
            "released_wilson_lower_95": wilson,
            "math_latency_p50_ms": _percentile(math_ms, 50),
            "math_latency_p95_ms": math_p95,
            "logic_latency_p50_ms": _percentile(logic_ms, 50),
            "logic_latency_p95_ms": logic_p95,
        },
        "by_family": {name: dict(sorted(values.items())) for name, values in sorted(by_family.items())},
        "static_security": static_security,
        "gate": gate,
        "failures": failures,
    }


def _static_security_check(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_calls = {"eval", "exec", "compile", "open", "__import__"}
    forbidden_imports = {"os", "subprocess", "socket", "requests", "urllib"}
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
            findings.append(f"forbidden_call:{node.func.id}:{node.lineno}")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [str(node.module or "").split(".")[0]]
            findings.extend(f"forbidden_import:{name}:{node.lineno}" for name in names if name in forbidden_imports)
    return {"passed": not findings, "findings": findings}


def _wrong_answer(answer: str) -> str:
    if answer.casefold() == "yes":
        return "no"
    if answer.casefold() == "no":
        return "yes"
    try:
        value = Decimal(answer)
    except InvalidOperation:
        return "WrongCandidate"
    return format(value + Decimal(1), "f")


def _wilson_lower(successes: int, total: int, z: float = 1.959963984540054) -> float:
    if total == 0:
        return 0.0
    proportion = successes / total
    denominator = 1 + z * z / total
    center = proportion + z * z / (2 * total)
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
    return (center - margin) / denominator


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile / 100 * len(ordered)) - 1)
    return ordered[index]


def _markdown(result: Mapping[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Proof-Carrying Math And Logic",
        "",
        f"- gate: `{result['gate']['passed']}`",
        f"- rows: `{summary['rows']}`",
        f"- released: `{summary['released']}`",
        f"- false positives: `{summary.get('false_positive', 0)}`",
        f"- false negatives: `{summary.get('false_negative', 0)}`",
        f"- released precision: `{summary['released_precision']:.3%}`",
        f"- Wilson lower 95%: `{summary['released_wilson_lower_95']:.3%}`",
        f"- math p95: `{summary['math_latency_p95_ms']:.3f} ms`",
        f"- logic p95: `{summary['logic_latency_p95_ms']:.3f} ms`",
        "",
        "## Families",
        "",
        "| Family | Rows | Released | Correct releases | False positives | Refused |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for family, row in result["by_family"].items():
        lines.append(
            f"| {family} | {row.get('rows', 0)} | {row.get('released', 0)} | "
            f"{row.get('true_positive', 0)} | {row.get('false_positive', 0)} | {row.get('refused', 0)} |"
        )
    lines.extend(["", "## Gate", ""])
    lines.extend(f"- [{ 'x' if passed else ' ' }] `{name}`" for name, passed in result["gate"].items() if name != "passed")
    if result["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{row['id']}`: {row['reason']}" for row in result["failures"])
    lines.append("")
    return "\n".join(lines)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
