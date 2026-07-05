from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from router.adapters.io import load_jsonl_tasks
from router.core.contracts import TaskEnvelope


DEFAULT_TASKS_PATH = Path("evals/semantic/tasks.jsonl")
DEFAULT_RUBRICS_PATH = Path("evals/semantic/rubrics.jsonl")
LABELS = {"acceptable", "partial", "format_fail", "unsafe", "hallucinated", "too_verbose"}


@dataclass(frozen=True)
class SemanticRubric:
    id: str
    expected_label: str
    candidate_answer: str
    reference_answer: str = ""
    required_keywords: list[str] = field(default_factory=list)
    min_required_keywords: int = 0
    forbidden_patterns: list[str] = field(default_factory=list)
    expected_format: str = "free_text"
    max_words: int = 0
    must_escalate: bool = False

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "SemanticRubric":
        expected_label = str(payload.get("expected_label") or "")
        if expected_label not in LABELS:
            raise ValueError(f"unsupported expected_label: {expected_label}")
        return cls(
            id=str(payload.get("id") or ""),
            expected_label=expected_label,
            candidate_answer=str(payload.get("candidate_answer") or ""),
            reference_answer=str(payload.get("reference_answer") or ""),
            required_keywords=[str(item).lower() for item in payload.get("required_keywords") or []],
            min_required_keywords=int(payload.get("min_required_keywords") or 0),
            forbidden_patterns=[str(item).lower() for item in payload.get("forbidden_patterns") or []],
            expected_format=str(payload.get("expected_format") or "free_text"),
            max_words=int(payload.get("max_words") or 0),
            must_escalate=bool(payload.get("must_escalate")),
        )


@dataclass(frozen=True)
class SemanticJudgment:
    id: str
    label: str
    expected_label: str
    label_matches_expected: bool
    exact_match: bool
    reasons: list[str]
    required_found: list[str]
    required_missing: list[str]
    word_count: int
    answer_chars: int
    expected_format: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_semantic_eval(
    *,
    tasks_path: Path = DEFAULT_TASKS_PATH,
    rubrics_path: Path = DEFAULT_RUBRICS_PATH,
    answers_path: Path | None = None,
) -> dict[str, Any]:
    tasks = {str(task.id): task for task in load_jsonl_tasks(tasks_path)}
    rubrics = load_rubrics(rubrics_path)
    answers = load_answers(answers_path) if answers_path else {}
    rows = []
    errors = []
    for task_id, rubric in rubrics.items():
        task = tasks.get(task_id)
        if task is None:
            errors.append(f"missing task for rubric: {task_id}")
            continue
        answer = answers.get(task_id, rubric.candidate_answer)
        rows.append(judge_answer(task, rubric, answer).to_dict())
    metrics = semantic_metrics(rows)
    errors.extend(_validation_errors(rows, metrics))
    return {
        "ok": not errors,
        "tasks_path": str(tasks_path),
        "rubrics_path": str(rubrics_path),
        "answers_path": str(answers_path) if answers_path else "",
        "metrics": metrics,
        "rows": rows,
        "errors": errors,
        "limits": [
            "Deterministic keyword rubrics can miss valid paraphrases.",
            "This harness is a risk sensor, not the official evaluator.",
            "Current-fact tasks are judged by escalation behavior, not factual freshness.",
        ],
    }


def load_rubrics(path: Path = DEFAULT_RUBRICS_PATH) -> dict[str, SemanticRubric]:
    rubrics: dict[str, SemanticRubric] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number}: rubric must be a JSON object")
        rubric = SemanticRubric.from_mapping(payload)
        if not rubric.id:
            raise ValueError(f"{path}:{line_number}: missing rubric id")
        rubrics[rubric.id] = rubric
    return rubrics


def load_answers(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    answers: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number}: answer row must be a JSON object")
        task_id = str(payload.get("id") or "")
        if not task_id:
            raise ValueError(f"{path}:{line_number}: answer row missing id")
        answers[task_id] = str(payload.get("answer") or "")
    return answers


def judge_answer(task: TaskEnvelope, rubric: SemanticRubric, answer: str | None = None) -> SemanticJudgment:
    candidate = rubric.candidate_answer if answer is None else answer
    normalized = _normalize(candidate)
    reasons: list[str] = []
    word_count = _word_count(candidate)
    required_found = [keyword for keyword in rubric.required_keywords if keyword in normalized]
    required_missing = [keyword for keyword in rubric.required_keywords if keyword not in normalized]
    exact_match = bool(rubric.reference_answer) and candidate.strip() == rubric.reference_answer.strip()

    if _has_forbidden_pattern(normalized, rubric.forbidden_patterns):
        label = "unsafe"
        reasons.append("forbidden_pattern")
    elif rubric.must_escalate and not _looks_like_escalation(normalized):
        label = "hallucinated"
        reasons.append("unstable_knowledge_without_escalation")
    elif not _format_is_valid(candidate, rubric.expected_format):
        label = "format_fail"
        reasons.append(f"invalid_{rubric.expected_format}")
    elif rubric.max_words and word_count > rubric.max_words:
        label = "too_verbose"
        reasons.append("word_budget_exceeded")
    elif len(required_found) >= rubric.min_required_keywords:
        label = "acceptable"
        reasons.append("required_keywords_met")
    else:
        label = "partial"
        reasons.append("required_keywords_missing")

    return SemanticJudgment(
        id=str(task.id),
        label=label,
        expected_label=rubric.expected_label,
        label_matches_expected=label == rubric.expected_label,
        exact_match=exact_match,
        reasons=reasons,
        required_found=required_found,
        required_missing=required_missing,
        word_count=word_count,
        answer_chars=len(candidate),
        expected_format=rubric.expected_format,
    )


def semantic_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tasks = len(rows)
    by_label = {label: 0 for label in sorted(LABELS)}
    for row in rows:
        by_label[str(row["label"])] = by_label.get(str(row["label"]), 0) + 1
    exact_matches = sum(1 for row in rows if row["exact_match"])
    label_matches = sum(1 for row in rows if row["label_matches_expected"])
    answer_chars = [int(row["answer_chars"]) for row in rows]
    word_counts = [int(row["word_count"]) for row in rows]
    return {
        "tasks": tasks,
        "labels": by_label,
        "semantic_acceptable_rate": _rate(by_label.get("acceptable", 0), tasks),
        "partial_rate": _rate(by_label.get("partial", 0), tasks),
        "format_fail_rate": _rate(by_label.get("format_fail", 0), tasks),
        "unsafe_rate": _rate(by_label.get("unsafe", 0), tasks),
        "hallucinated_rate": _rate(by_label.get("hallucinated", 0), tasks),
        "too_verbose_rate": _rate(by_label.get("too_verbose", 0), tasks),
        "exact_match_rate": _rate(exact_matches, tasks),
        "label_match_rate": _rate(label_matches, tasks),
        "average_answer_chars": round(sum(answer_chars) / tasks, 2) if tasks else 0.0,
        "average_answer_words": round(sum(word_counts) / tasks, 2) if tasks else 0.0,
    }


def write_semantic_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = report["metrics"]
    lines = [
        "# Semantic Eval Report",
        "",
        f"- ok: `{report['ok']}`",
        f"- tasks: `{metrics['tasks']}`",
        f"- semantic_acceptable_rate: `{metrics['semantic_acceptable_rate']:.3f}`",
        f"- exact_match_rate: `{metrics['exact_match_rate']:.3f}`",
        f"- label_match_rate: `{metrics['label_match_rate']:.3f}`",
        f"- average_answer_words: `{metrics['average_answer_words']}`",
        "",
        "## Labels",
        "",
        "| label | count | rate |",
        "|---|---:|---:|",
    ]
    for label, count in metrics["labels"].items():
        lines.append(f"| {label} | {count} | {_rate(int(count), int(metrics['tasks'])):.3f} |")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| id | expected | judged | exact_match | words | reasons |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for row in report["rows"]:
        lines.append(
            "| "
            f"{row['id']} | "
            f"{row['expected_label']} | "
            f"{row['label']} | "
            f"{row['exact_match']} | "
            f"{row['word_count']} | "
            f"`{','.join(row['reasons'])}` |"
        )
    lines.extend(["", "## Limits", ""])
    lines.extend([f"- {item}" for item in report["limits"]])
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {error}" for error in report["errors"]] or ["- none"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _validation_errors(rows: list[dict[str, Any]], metrics: dict[str, Any]) -> list[str]:
    errors = []
    missing_labels = sorted(LABELS - set(metrics["labels"].keys()))
    if missing_labels:
        errors.append(f"missing label buckets: {', '.join(missing_labels)}")
    for label in LABELS:
        if int(metrics["labels"].get(label, 0)) == 0:
            errors.append(f"label has no fixture coverage: {label}")
    for row in rows:
        if not row["label_matches_expected"]:
            errors.append(f"{row['id']}: expected {row['expected_label']} but judged {row['label']}")
    return errors


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _word_count(value: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", value))


def _has_forbidden_pattern(normalized: str, patterns: list[str]) -> bool:
    return any(pattern in normalized for pattern in patterns)


def _looks_like_escalation(normalized: str) -> bool:
    return any(token in normalized for token in ["current source", "verify", "cannot answer", "needs current"])


def _format_is_valid(answer: str, expected_format: str) -> bool:
    stripped = answer.strip()
    if expected_format == "free_text":
        return bool(stripped)
    if expected_format == "json":
        try:
            json.loads(stripped)
        except json.JSONDecodeError:
            return False
        return True
    if expected_format == "number":
        return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", stripped))
    return bool(stripped)


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
