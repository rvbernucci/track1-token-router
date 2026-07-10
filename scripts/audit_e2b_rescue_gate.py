#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import validate_or_safely_repair_final_answer
from router.functiongemma.tooling import jsonl_rows
from scripts.build_engine_outcome_matrix import _consensus, _load_judge_policy


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Audit the conservative post-E2B mechanical rescue gate against teacher consensus."
    )
    root.add_argument("--tasks", type=Path, required=True)
    root.add_argument("--candidates", type=Path, required=True)
    root.add_argument("--judgments", type=Path, required=True)
    root.add_argument("--judge-policy", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    root.add_argument("--report", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = audit_rescue_gate(
        tasks_path=args.tasks,
        candidates_path=args.candidates,
        judgments_path=args.judgments,
        judge_policy_path=args.judge_policy,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


def audit_rescue_gate(
    *,
    tasks_path: Path,
    candidates_path: Path,
    judgments_path: Path,
    judge_policy_path: Path,
) -> dict[str, Any]:
    tasks = {str(row["id"]): row for row in jsonl_rows(tasks_path)}
    candidates = jsonl_rows(candidates_path)
    policy = _load_judge_policy(judge_policy_path)
    judgments: dict[str, list[Mapping[str, Any]]] = {}
    for row in jsonl_rows(judgments_path):
        judgments.setdefault(str(row["candidate_id"]), []).append(row)
    counts = Counter()
    reasons = Counter()
    intents: dict[str, Counter[str]] = {}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate_id = str(candidate["id"])
        if candidate_id in seen:
            raise ValueError(f"Duplicate candidate id {candidate_id!r}.")
        seen.add(candidate_id)
        task_id = str(candidate["task_id"])
        task = tasks.get(task_id)
        if task is None:
            raise ValueError(f"Candidate references unknown task {task_id!r}.")
        policy_key = str(candidate.get("model_id") or candidate["engine"])
        allowed_judges = policy.get(policy_key)
        if allowed_judges is None:
            raise ValueError(f"Judge policy is missing {policy_key!r}.")
        correct, consensus, judge_models, _ = _consensus(
            judgments.get(candidate_id, []),
            allowed_judges=allowed_judges,
        )
        envelope = TaskEnvelope(id=task_id, input_text=_task_text(task))
        validation = validate_or_safely_repair_final_answer(
            envelope, str(candidate.get("answer") or "")
        )
        if validation.valid and validation.repaired_answer:
            action = "repair_release"
        elif validation.valid:
            action = "release"
        else:
            action = "escalate"
        outcome = _outcome(action, correct)
        counts[action] += 1
        counts[outcome] += 1
        if not validation.valid:
            reasons[validation.reason] += 1
        assessment = candidate.get("functiongemma_assessment")
        intent = (
            str(assessment.get("intent"))
            if isinstance(assessment, Mapping) and assessment.get("intent")
            else "unknown"
        )
        intents.setdefault(intent, Counter())[outcome] += 1
        rows.append(
            {
                "task_id": task_id,
                "candidate_id": candidate_id,
                "intent": intent,
                "action": action,
                "mechanical_reason": validation.reason,
                "teacher_consensus": consensus,
                "teacher_correct": correct,
                "judge_models": judge_models,
                "outcome": outcome,
            }
        )
    resolved = counts["release_correct"] + counts["release_incorrect"] + counts["rescue_correct"] + counts["false_rescue"]
    summary = {
        "candidates": len(candidates),
        "released": counts["release"] + counts["repair_release"],
        "released_after_safe_repair": counts["repair_release"],
        "escalated": counts["escalate"],
        "resolved_teacher_consensus": resolved,
        "release_correct": counts["release_correct"],
        "release_incorrect": counts["release_incorrect"],
        "rescue_correct": counts["rescue_correct"],
        "false_rescue": counts["false_rescue"],
        "unresolved": counts["release_unresolved"] + counts["escalate_unresolved"],
        "released_precision": (
            counts["release_correct"] / (counts["release_correct"] + counts["release_incorrect"])
            if counts["release_correct"] + counts["release_incorrect"]
            else 0.0
        ),
        "false_rescue_rate": counts["false_rescue"] / resolved if resolved else 0.0,
    }
    return {
        "schema_version": "e2b-rescue-gate-audit-v1",
        "summary": summary,
        "mechanical_rejection_reasons": dict(sorted(reasons.items())),
        "outcomes_by_intent": {
            intent: dict(sorted(values.items())) for intent, values in sorted(intents.items())
        },
        "rows": rows,
    }


def _outcome(action: str, correct: bool | None) -> str:
    if action != "escalate":
        return "release_correct" if correct is True else "release_incorrect" if correct is False else "release_unresolved"
    return "false_rescue" if correct is True else "rescue_correct" if correct is False else "escalate_unresolved"


def _task_text(task: Mapping[str, Any]) -> str:
    for key in ("input_text", "input", "prompt", "task", "text"):
        value = task.get(key)
        if isinstance(value, str) and value:
            return value
    messages = task.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, Mapping) and message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, str) and content:
                    return content
    raise ValueError("Task row has no supported text field.")


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# E2B Rescue Gate Audit",
        "",
        f"- candidates: `{summary['candidates']}`",
        f"- released: `{summary['released']}`",
        f"- released after safe repair: `{summary['released_after_safe_repair']}`",
        f"- escalated: `{summary['escalated']}`",
        f"- incorrect local answers rescued: `{summary['rescue_correct']}`",
        f"- correct local answers escalated: `{summary['false_rescue']}`",
        f"- released precision: `{summary['released_precision']:.3f}`",
        f"- false rescue rate: `{summary['false_rescue_rate']:.3f}`",
        "",
        "| Mechanical reason | Rows |",
        "| --- | ---: |",
    ]
    for reason, count in report["mechanical_rejection_reasons"].items():
        lines.append(f"| `{reason}` | {count} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
