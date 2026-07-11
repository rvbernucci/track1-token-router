#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


JUDGE_FILES = {
    "codex": "judgments-contract-v2-codex-smoke.jsonl",
    "gemini": "judgments-contract-v2-agy.jsonl",
    "kimi": "judgments-contract-v2-fireworks-kimi.jsonl",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consolidate all post-contract E2B outcomes.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--verdict-dir", type=Path)
    parser.add_argument("--matrix-output", type=Path)
    args = parser.parse_args(argv)

    result = consolidate(_absolute(args.root))
    _write_jsonl(_absolute(args.ledger), result["ledger"])
    _write_json(_absolute(args.summary), result["summary"])
    if args.verdict_dir:
        verdict_dir = _absolute(args.verdict_dir)
        for verdict in ("correct", "incorrect", "uncertain"):
            _write_jsonl(
                verdict_dir / f"e2b-post-contract-{verdict}.jsonl",
                [row for row in result["ledger"] if row["final_verdict"] == verdict],
            )
    if args.matrix_output:
        _write_jsonl(_absolute(args.matrix_output), result["matrix"])
    report = _absolute(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_markdown(result["summary"]), encoding="utf-8")
    print(json.dumps(result["summary"]["totals"], sort_keys=True))
    return 0


def consolidate(root: Path) -> dict[str, Any]:
    candidates = _index(_jsonl(root / "e2b-candidates-96-contract-v2.jsonl"), "id")
    matrix = _index(_jsonl(root / "e2b-outcome-matrix.jsonl"), "candidate_id")
    judges = {
        name: _index(_jsonl(root / filename), "candidate_id")
        for name, filename in JUDGE_FILES.items()
    }
    if set(candidates) != set(matrix):
        raise ValueError("Post-contract candidates and original matrix IDs must match exactly.")

    ledger: list[dict[str, Any]] = []
    updated_matrix: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()
    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    by_action: dict[str, Counter[str]] = defaultdict(Counter)
    for candidate_id, candidate in candidates.items():
        changed = bool(candidate.get("answer_contract_changed"))
        if changed:
            evidence = {name: rows.get(candidate_id) for name, rows in judges.items()}
            if any(row is None for row in evidence.values()):
                raise ValueError(f"Changed candidate {candidate_id} is missing a post-contract judge.")
            verdict = _majority([str(row["verdict"]) for row in evidence.values() if row])
            format_valid = _majority_bool([bool(row["format_valid"]) for row in evidence.values() if row])
            judge_evidence = {
                name: {
                    "verdict": row["verdict"],
                    "format_valid": row["format_valid"],
                    "confidence": row["confidence"],
                    "rationale": row["rationale"],
                }
                for name, row in evidence.items()
                if row
            }
            policy = "post_contract_three_judge_majority"
        else:
            original = matrix[candidate_id]
            verdict = _matrix_verdict(original)
            format_valid = bool(original.get("format_valid"))
            judge_evidence = {
                "inherited_original_consensus": {
                    "consensus": original.get("consensus"),
                    "judge_models": original.get("judge_models", []),
                    "reason": "answer_bytes_unchanged",
                }
            }
            policy = "inherited_two_judge_unanimity"

        category = str((candidate.get("functiongemma_assessment") or {}).get("intent") or "unknown")
        actions = list((candidate.get("answer_contract") or {}).get("actions") or [])
        row = {
            "schema_version": "e2b-post-contract-ledger-v1",
            "candidate_id": candidate_id,
            "task_id": candidate["task_id"],
            "category": category,
            "answer_contract_changed": changed,
            "answer_contract_valid": bool(candidate.get("answer_contract_valid")),
            "answer_contract_actions": actions,
            "final_verdict": verdict,
            "format_valid": format_valid,
            "consensus_policy": policy,
            "judge_evidence": judge_evidence,
            "task_text": candidate["task_text"],
            "answer_before_contract": candidate["answer_before_contract"],
            "answer_after_contract": candidate["answer"],
        }
        ledger.append(row)
        matrix_row = dict(matrix[candidate_id])
        matrix_row.update(
            {
                "correct": True if verdict == "correct" else False if verdict == "incorrect" else None,
                "consensus": f"post_contract_{verdict}",
                "format_valid": format_valid,
                "missing_reason": "post_contract_uncertain" if verdict == "uncertain" else None,
                "answer_contract_changed": changed,
                "answer_contract_actions": actions,
                "answer_contract_schema_version": "answer-contract-v2",
                "label_policy": policy,
            }
        )
        updated_matrix.append(matrix_row)
        totals[verdict] += 1
        totals["format_valid"] += int(format_valid)
        totals["format_invalid"] += int(not format_valid)
        totals["changed"] += int(changed)
        totals["unchanged"] += int(not changed)
        by_category[category][verdict] += 1
        by_category[category]["total"] += 1
        for action in actions:
            by_action[action][verdict] += 1
            by_action[action]["total"] += 1

    totals["rows"] = len(ledger)
    return {
        "ledger": ledger,
        "matrix": updated_matrix,
        "summary": {
            "schema_version": "e2b-post-contract-summary-v1",
            "consensus_policy": {
                "unchanged": "inherit original Gemini+Kimi unanimity because answer bytes are unchanged",
                "changed": "majority of Codex, Gemini and Kimi post-contract judgments",
                "uncertain": "preserved when no reliable binary consensus exists",
            },
            "totals": dict(sorted(totals.items())),
            "by_category": {key: dict(sorted(value.items())) for key, value in sorted(by_category.items())},
            "by_action": {key: dict(sorted(value.items())) for key, value in sorted(by_action.items())},
        },
    }


def _matrix_verdict(row: Mapping[str, Any]) -> str:
    if row.get("consensus") == "unanimous_correct" and row.get("correct") is True:
        return "correct"
    if row.get("consensus") == "unanimous_incorrect" and row.get("correct") is False:
        return "incorrect"
    return "uncertain"


def _majority(values: list[str]) -> str:
    counts = Counter(values)
    verdict, count = counts.most_common(1)[0]
    return verdict if count >= 2 else "uncertain"


def _majority_bool(values: list[bool]) -> bool:
    return sum(values) >= 2


def _markdown(summary: Mapping[str, Any]) -> str:
    totals = summary["totals"]
    lines = [
        "# E2B Post-Contract Ledger",
        "",
        "All 1,991 E2B answers were passed through Answer Contract Engine v2 and assigned a conservative final verdict.",
        "",
        "## Totals",
        "",
        "| Verdict | Rows | Rate |",
        "|---|---:|---:|",
    ]
    rows = int(totals["rows"])
    for verdict in ("correct", "incorrect", "uncertain"):
        count = int(totals.get(verdict, 0))
        lines.append(f"| {verdict} | {count} | {count / rows:.1%} |")
    lines.extend(
        [
            "",
            f"Format valid: {totals['format_valid']}/{rows} ({int(totals['format_valid']) / rows:.1%}).",
            "",
            "## By Category",
            "",
            "| Category | Correct | Incorrect | Uncertain | Total |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for category, metrics in summary["by_category"].items():
        lines.append(
            f"| {category} | {metrics.get('correct', 0)} | {metrics.get('incorrect', 0)} | "
            f"{metrics.get('uncertain', 0)} | {metrics['total']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Unchanged answers inherit their original Gemini+Kimi judgment because their bytes did not change. "
            "Changed answers use a fresh majority of Codex, Gemini and Kimi. `uncertain` is not counted as correct. "
            "This ledger measures the current frozen E2B candidate set; it is not a hidden-hackathon accuracy estimate.",
            "",
        ]
    )
    return "\n".join(lines)


def _index(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row[key])
        if value in result:
            raise ValueError(f"Duplicate {key}: {value}")
        result[value] = row
    return result


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
