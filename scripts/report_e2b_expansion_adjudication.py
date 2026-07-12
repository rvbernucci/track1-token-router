#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    candidates = {}
    labels = {}
    for scope in ("development", "sealed"):
        base = ROOT / f"evals/e2b-expansion-v1/adjudication/{scope}"
        candidates.update({row["task_id"]: row for row in _rows(base / "candidates.jsonl")})
        labels.update({row["task_id"]: row for row in _rows(base / "labels.jsonl")})
    rows = []
    for task_id in sorted(set(candidates) & set(labels)):
        candidate, label = candidates[task_id], labels[task_id]
        votes = label["judge_verdicts"]
        rows.append({
            "task_id": task_id, "category": label["category"], "difficulty": label["difficulty"],
            "evidence_source": label["evidence_source"], "final_label": label["final_label"],
            "judge_pair_present": len(votes) >= 2,
            "judge_pair_agreed": len(votes) >= 2 and votes[0] == votes[1],
            "contract_valid": label["contract_valid"],
            "normalization_changed": candidate["normalization_changed"],
        })
    report = {
        "schema_version": "e2b-expansion-adjudication-report-v1",
        "rows": len(rows),
        "correct": sum(row["final_label"] == "correct" for row in rows),
        "incorrect": sum(row["final_label"] == "incorrect" for row in rows),
        "unresolved": sum(row["final_label"] == "uncertain" for row in rows),
        "evidence_sources": dict(sorted(Counter(row["evidence_source"] for row in rows).items())),
        "judge_pair_agreement_rate": _agreement(rows),
        "by_category": _group(rows, "category"),
        "by_difficulty": _group(rows, "difficulty"),
        "contract_invalid": sum(not row["contract_valid"] for row in rows),
        "format_recoveries": sum(row["normalization_changed"] and row["final_label"] == "correct" for row in rows),
    }
    generated = ROOT / "reports/generated/e2b-expansion-v1/adjudication-report.json"
    generated.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    public = ROOT / "reports/public/e2b-expansion-adjudication.md"
    public.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("rows", "correct", "incorrect", "unresolved", "judge_pair_agreement_rate")}, sort_keys=True))
    return 0


def _agreement(rows: Sequence[Mapping[str, Any]]) -> float | None:
    paired = [row for row in rows if row["judge_pair_present"]]
    return sum(row["judge_pair_agreed"] for row in paired) / len(paired) if paired else None


def _group(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    return {
        key: {
            "rows": len(group), "correct": sum(row["final_label"] == "correct" for row in group),
            "accuracy": sum(row["final_label"] == "correct" for row in group) / len(group),
            "judge_pairs": sum(row["judge_pair_present"] for row in group),
            "judge_pair_agreement_rate": _agreement(group),
        }
        for key, group in sorted(groups.items())
    }


def _markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# E2B Expansion Adjudication", "",
        f"- Rows: `{report['rows']}`",
        f"- Post-contract correct: `{report['correct']}`",
        f"- Post-contract incorrect: `{report['incorrect']}`",
        f"- Unresolved: `{report['unresolved']}`",
        f"- Independent judge-pair agreement: `{_format_rate(report['judge_pair_agreement_rate'])}`",
        f"- Contract-invalid outputs: `{report['contract_invalid']}`",
        f"- Correct answers recovered by safe normalization: `{report['format_recoveries']}`", "",
        "## Categories", "",
    ]
    for category, metrics in report["by_category"].items():
        lines.append(
            f"- `{category}`: `{metrics['correct']}/{metrics['rows']}` correct; "
            f"judge agreement `{_format_rate(metrics['judge_pair_agreement_rate'])}` "
            f"across `{metrics['judge_pairs']}` semantic pairs"
        )
    lines.append("")
    return "\n".join(lines)


def _format_rate(value: float | None) -> str:
    return f"{value:.2%}" if value is not None else "not applicable"


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


if __name__ == "__main__":
    raise SystemExit(main())
