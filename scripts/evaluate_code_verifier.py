#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics
import sys
from time import perf_counter
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.code_verifier import verify_code_candidate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate sandboxed Python code verification.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/code-verifier/code-verifier-holdout.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/generated/code-verifier-evaluation.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/sandboxed-code-verification.md"))
    parser.add_argument("--public-report", type=Path, default=Path("reports/public/sandboxed-code-verification.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    result = evaluate(_absolute(args.dataset))
    _write_json(_absolute(args.output), result)
    markdown = _markdown(result)
    for report_path in (args.report, args.public_report):
        path = _absolute(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0 if result["gate"]["passed"] or not args.check else 1


def evaluate(dataset: Path) -> dict[str, Any]:
    rows = _jsonl(dataset)
    counts: Counter[str] = Counter()
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    by_kind: dict[str, Counter[str]] = defaultdict(Counter)
    rejection_reasons: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    latencies: list[float] = []
    peak_rss_kib = 0
    deterministic_checks = deterministic_passes = 0
    started = perf_counter()

    for row in rows:
        task = TaskEnvelope(id=str(row["id"]), input_text=str(row["prompt"]))
        report = verify_code_candidate(task, str(row["candidate"]))
        expected = bool(row["expected_accept"])
        family = str(row["family"])
        kind = str(row["kind"])
        latencies.append(report.latency_ms)
        peak_rss_kib = max(peak_rss_kib, report.peak_rss_kib)
        deterministic_checks += report.repeatability_checks_run
        deterministic_passes += report.repeatability_checks_passed

        counts["rows"] += 1
        counts["expected_accept"] += int(expected)
        counts["accepted"] += int(report.accepted)
        by_family[family]["rows"] += 1
        by_kind[kind]["rows"] += 1
        by_family[family]["accepted"] += int(report.accepted)
        by_kind[kind]["accepted"] += int(report.accepted)
        for reason in report.rejection_reasons:
            rejection_reasons[reason] += 1

        outcome = _outcome(expected, report.accepted)
        counts[outcome] += 1
        by_family[family][outcome] += 1
        by_kind[kind][outcome] += 1
        if kind in {"mutant", "debug_mutant"}:
            counts["mutants"] += 1
            counts["mutants_killed"] += int(not report.accepted)
        if kind == "adversarial":
            counts["adversarial"] += 1
            counts["adversarial_contained"] += int(not report.accepted)
        if outcome in {"false_positive", "false_negative"}:
            failures.append(
                {
                    "id": str(row["id"]),
                    "family": family,
                    "kind": kind,
                    "outcome": outcome,
                    "rejection_reasons": list(report.rejection_reasons),
                }
            )

    elapsed_ms = (perf_counter() - started) * 1000
    mutation_score = counts["mutants_killed"] / counts["mutants"] if counts["mutants"] else 0.0
    containment_rate = (
        counts["adversarial_contained"] / counts["adversarial"] if counts["adversarial"] else 0.0
    )
    repeatability_rate = deterministic_passes / deterministic_checks if deterministic_checks else 0.0
    p95_ms = _percentile(latencies, 95)
    gate = {
        "all_reference_candidates_accepted": counts["false_negative"] == 0,
        "zero_false_accepts": counts["false_positive"] == 0,
        "mutation_score_at_least_90_percent": mutation_score >= 0.90,
        "all_adversarial_programs_contained": containment_rate == 1.0,
        "deterministic_repeatability": repeatability_rate == 1.0,
        "p95_below_250_ms": p95_ms < 250.0,
        "peak_rss_below_256_mib": peak_rss_kib < 256 * 1024,
        "batch_below_ten_minutes": elapsed_ms < 600_000,
    }
    gate["passed"] = all(gate.values())
    summary = {
        **dict(sorted(counts.items())),
        "mutation_score": mutation_score,
        "adversarial_containment_rate": containment_rate,
        "repeatability_rate": repeatability_rate,
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": p95_ms,
        "latency_mean_ms": statistics.fmean(latencies) if latencies else 0.0,
        "batch_runtime_ms": elapsed_ms,
        "peak_rss_kib": peak_rss_kib,
        "estimated_fireworks_calls_avoided": counts["accepted"],
    }
    return {
        "schema_version": "code-verifier-evaluation-v1",
        "dataset": str(dataset),
        "summary": summary,
        "by_family": {name: dict(sorted(value.items())) for name, value in sorted(by_family.items())},
        "by_kind": {name: dict(sorted(value.items())) for name, value in sorted(by_kind.items())},
        "rejection_reasons": dict(rejection_reasons.most_common()),
        "gate": gate,
        "failures": failures,
    }


def _outcome(expected: bool, accepted: bool) -> str:
    if expected and accepted:
        return "true_positive"
    if expected:
        return "false_negative"
    if accepted:
        return "false_positive"
    return "true_negative"


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile / 100 * len(ordered)) - 1)
    return ordered[index]


def _markdown(result: Mapping[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Sandboxed Code Verification",
        "",
        f"- gate: `{result['gate']['passed']}`",
        f"- holdout rows: `{summary['rows']}`",
        f"- verified local releases: `{summary['accepted']}`",
        f"- mutation score: `{summary['mutation_score']:.2%}`",
        f"- adversarial containment: `{summary['adversarial_containment_rate']:.2%}`",
        f"- false accepts: `{summary.get('false_positive', 0)}`",
        f"- false rejects: `{summary.get('false_negative', 0)}`",
        f"- repeatability: `{summary['repeatability_rate']:.2%}`",
        f"- latency p95: `{summary['latency_p95_ms']:.2f} ms`",
        f"- peak verifier worker RSS: `{summary['peak_rss_kib'] / 1024:.2f} MiB`",
        "",
        "## Families",
        "",
        "| Family | Rows | Accepted | Correct accept | Correct reject | False accept | False reject |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for family, row in result["by_family"].items():
        lines.append(
            f"| {family} | {row.get('rows', 0)} | {row.get('accepted', 0)} | "
            f"{row.get('true_positive', 0)} | {row.get('true_negative', 0)} | "
            f"{row.get('false_positive', 0)} | {row.get('false_negative', 0)} |"
        )
    lines.extend(["", "## Promotion Gate", ""])
    lines.extend(
        f"- [{'x' if passed else ' '}] `{name}`"
        for name, passed in result["gate"].items()
        if name != "passed"
    )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Promote only the seven explicitly supported Python families. Unknown behavior, ambiguous contracts, "
            "unsupported languages and any static or dynamic failure remain Fireworks-only. An LLM review can "
            "add evidence but cannot override a failed executable gate.",
            "",
        ]
    )
    if result["failures"]:
        lines.extend(["## Failures", ""])
        lines.extend(f"- `{row['id']}`: `{row['outcome']}`" for row in result["failures"])
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
