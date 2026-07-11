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
from router.orchestration.grounded_verifier import verify_grounded_candidate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate grounded local extraction and classification verifiers.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/grounded-verifier/grounded-holdout.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/generated/grounded-verifier-evaluation.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/grounded-extraction-classification.md"))
    parser.add_argument("--public-report", type=Path, default=Path("reports/public/grounded-extraction-classification.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    result = evaluate(_absolute(args.dataset))
    _write_json(_absolute(args.output), result)
    markdown = _markdown(result)
    for relative in (args.report, args.public_report):
        path = _absolute(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0 if result["gate"]["passed"] or not args.check else 1


def evaluate(dataset: Path) -> dict[str, Any]:
    rows = _jsonl(dataset)
    counts: Counter[str] = Counter()
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    by_language: dict[str, Counter[str]] = defaultdict(Counter)
    sentiment_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    by_subtype: dict[str, Counter[str]] = defaultdict(Counter)
    rejection_reasons: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    latencies: list[float] = []
    started = perf_counter()

    for row in rows:
        task = TaskEnvelope(id=str(row["id"]), input_text=str(row["prompt"]))
        before = perf_counter()
        report = verify_grounded_candidate(task, str(row["candidate"]))
        latencies.append((perf_counter() - before) * 1000)
        expected = bool(row["expected_accept"])
        family = str(row["family"])
        language = str(row["language"])
        subtype = str(row["subtype"])
        outcome = _outcome(expected, report.accepted)

        counts["rows"] += 1
        counts["expected_accept"] += int(expected)
        counts["accepted"] += int(report.accepted)
        counts[outcome] += 1
        for bucket in (by_family[family], by_language[language], by_subtype[subtype]):
            bucket["rows"] += 1
            bucket["accepted"] += int(report.accepted)
            bucket[outcome] += 1
        if family == "sentiment":
            sentiment_by_language[language]["rows"] += 1
            sentiment_by_language[language]["accepted"] += int(report.accepted)
            sentiment_by_language[language][outcome] += 1
        if not report.accepted:
            rejection_reasons[report.reason] += 1

        for span in report.spans:
            counts["released_spans"] += 1
            exact = task.input_text[span.start : span.end] == span.evidence_text and bool(span.normalized_value)
            counts["exact_spans"] += int(exact)
            if not exact:
                failures.append({"id": row["id"], "reason": "invalid_source_span", "span": span.to_dict()})

        expected_evidence = {_normalize(item) for item in row.get("expected_evidence", [])}
        if expected and expected_evidence:
            released_evidence = {_normalize(span.evidence_text) for span in report.spans}
            counts["expected_evidence"] += len(expected_evidence)
            counts["recalled_evidence"] += len(expected_evidence & released_evidence)

        if report.accepted:
            counts["estimated_fireworks_calls_avoided"] += 1
            counts["estimated_fireworks_tokens_avoided"] += math.ceil(
                (len(task.input_text) + len(report.candidate)) / 4
            )
        if family == "ner" and subtype == "hallucinated_entity" and report.accepted:
            counts["hallucinated_entity_releases"] += 1
        if family == "context_qa" and subtype in {"conflicting_support", "non_unique_support"} and report.accepted:
            counts["context_contradiction_releases"] += 1
        if subtype == "open_world_temporal" and report.accepted:
            counts["open_world_releases"] += 1
        if family == "summary" and not expected and report.accepted:
            counts["summary_factual_violations"] += 1
        if outcome in {"false_positive", "false_negative"}:
            failures.append(
                {
                    "id": row["id"],
                    "family": family,
                    "subtype": subtype,
                    "outcome": outcome,
                    "reason": report.reason,
                }
            )

    elapsed_ms = (perf_counter() - started) * 1000
    family_metrics = {name: _metrics(values) for name, values in sorted(by_family.items())}
    language_metrics = {name: _metrics(values) for name, values in sorted(by_language.items())}
    sentiment_language_metrics = {
        name: _metrics(values) for name, values in sorted(sentiment_by_language.items())
    }
    span_precision = counts["exact_spans"] / counts["released_spans"] if counts["released_spans"] else 0.0
    span_recall = counts["recalled_evidence"] / counts["expected_evidence"] if counts["expected_evidence"] else 0.0
    p95 = _percentile(latencies, 95)
    gate = {
        "fresh_holdout_at_least_120_rows": counts["rows"] >= 120,
        "zero_false_releases": counts["false_positive"] == 0,
        "all_promoted_references_released": counts["false_negative"] == 0,
        "every_family_precision_at_least_90_percent": all(item["precision"] >= 0.90 for item in family_metrics.values()),
        "every_family_has_at_least_eight_verified_releases": all(item["true_positive"] >= 8 for item in family_metrics.values()),
        "source_span_precision_100_percent": span_precision == 1.0,
        "expected_evidence_recall_100_percent": span_recall == 1.0,
        "zero_hallucinated_entity_releases": counts["hallucinated_entity_releases"] == 0,
        "zero_context_contradiction_releases": counts["context_contradiction_releases"] == 0,
        "zero_open_world_releases": counts["open_world_releases"] == 0,
        "zero_summary_factual_violations": counts["summary_factual_violations"] == 0,
        "sentiment_en_pt_precision_at_least_90_percent": all(
            sentiment_language_metrics.get(language, {}).get("precision", 0.0) >= 0.90
            and sentiment_language_metrics.get(language, {}).get("true_positive", 0) >= 5
            for language in ("en", "pt")
        ),
        "p95_below_10_ms": p95 < 10.0,
        "batch_below_ten_minutes": elapsed_ms < 600_000,
    }
    gate["passed"] = all(gate.values())
    summary = {
        **dict(sorted(counts.items())),
        "local_coverage": counts["accepted"] / counts["rows"] if counts["rows"] else 0.0,
        "source_span_precision": span_precision,
        "expected_evidence_recall": span_recall,
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": p95,
        "latency_mean_ms": statistics.fmean(latencies) if latencies else 0.0,
        "batch_runtime_ms": elapsed_ms,
    }
    return {
        "schema_version": "grounded-verifier-evaluation-v1",
        "dataset": str(dataset),
        "summary": summary,
        "by_family": family_metrics,
        "by_language": language_metrics,
        "sentiment_by_language": sentiment_language_metrics,
        "by_subtype": {name: _metrics(values) for name, values in sorted(by_subtype.items())},
        "rejection_reasons": dict(rejection_reasons.most_common()),
        "gate": gate,
        "failures": failures,
    }


def _metrics(counts: Mapping[str, int]) -> dict[str, Any]:
    true_positive = int(counts.get("true_positive", 0))
    false_positive = int(counts.get("false_positive", 0))
    false_negative = int(counts.get("false_negative", 0))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 1.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 1.0
    return {**dict(sorted(counts.items())), "precision": precision, "recall": recall}


def _outcome(expected: bool, accepted: bool) -> str:
    if expected and accepted:
        return "true_positive"
    if expected:
        return "false_negative"
    if accepted:
        return "false_positive"
    return "true_negative"


def _normalize(value: object) -> str:
    return " ".join(str(value).casefold().split()).strip(" .,:;!?\"'")


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile / 100 * len(ordered)) - 1)]


def _markdown(result: Mapping[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Grounded Extraction And Classification",
        "",
        f"- gate: `{result['gate']['passed']}`",
        f"- fresh holdout rows: `{summary['rows']}`",
        f"- verified zero-token releases: `{summary['accepted']}` ({summary['local_coverage']:.2%})",
        f"- false releases: `{summary.get('false_positive', 0)}`",
        f"- false refusals: `{summary.get('false_negative', 0)}`",
        f"- source-span precision: `{summary['source_span_precision']:.2%}`",
        f"- expected-evidence recall: `{summary['expected_evidence_recall']:.2%}`",
        f"- estimated Fireworks calls avoided: `{summary['estimated_fireworks_calls_avoided']}`",
        f"- estimated Fireworks tokens avoided: `{summary['estimated_fireworks_tokens_avoided']}`",
        f"- verifier p95: `{summary['latency_p95_ms']:.3f} ms`",
        "",
        "## Cohorts",
        "",
        "| Cohort | Rows | Released | Correct releases | Correct refusals | Precision | Recall |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for family, row in result["by_family"].items():
        lines.append(
            f"| {family} | {row.get('rows', 0)} | {row.get('accepted', 0)} | "
            f"{row.get('true_positive', 0)} | {row.get('true_negative', 0)} | "
            f"{row['precision']:.2%} | {row['recall']:.2%} |"
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
            "Promote only typed/source-grounded NER, uniquely supported context QA, high-margin EN/PT sentiment "
            "with local-candidate agreement, and extractive summaries satisfying Answer Contract v2. Mixed or sarcastic "
            "sentiment, conflicting context, open-world facts, overlapping entities and abstractive summaries escalate.",
            "",
        ]
    )
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
