from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any, Iterable


LATENCY_KEYS = (
    "latency_m1_ms",
    "latency_m2a_ms",
    "latency_m2b_ms",
    "latency_fireworks_ms",
)

LEGACY_LATENCY_MAP = {
    "model_1_ms": "latency_m1_ms",
    "model_2a_ms": "latency_m2a_ms",
    "model_2b_ms": "latency_m2b_ms",
    "remote_ms": "latency_fireworks_ms",
}


def expand_log_paths(patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = [Path(match) for match in glob.glob(pattern)]
        if matches:
            paths.extend(matches)
            continue
        path = Path(pattern)
        if path.exists():
            paths.append(path)
    return sorted(set(paths))


def load_trace_records(paths: Iterable[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            continue
        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_number}: invalid json: {exc}")
                continue
            if not isinstance(payload, dict):
                errors.append(f"{path}:{line_number}: record must be an object")
                continue
            records.append(payload)
    return records, errors


def summarize_traces(
    records: list[dict[str, Any]],
    *,
    source_files: Iterable[Path] = (),
    ingestion_errors: Iterable[str] = (),
) -> dict[str, Any]:
    route_counts: dict[str, int] = {}
    latency_ms = {key: 0 for key in LATENCY_KEYS}
    remote_tokens = {"prompt": 0, "completion": 0, "total": 0}
    parse_failures = 0
    error_count = 0
    answer_chars = 0

    for record in records:
        route = str(record.get("route") or "unknown")
        route_counts[route] = route_counts.get(route, 0) + 1
        answer_chars += _int(record.get("answer_chars"))
        _sum_tokens(remote_tokens, record.get("remote_tokens"))
        _sum_latency(latency_ms, record)
        if _is_parse_failure(record):
            parse_failures += 1
        if _is_error_record(record):
            error_count += 1

    return {
        "source_files": [str(path) for path in source_files],
        "records": len(records),
        "empty_run": len(records) == 0,
        "routes": route_counts,
        "remote_tokens": remote_tokens,
        "latency_ms": latency_ms,
        "parse_failures": parse_failures,
        "errors": error_count,
        "ingestion_errors": list(ingestion_errors),
        "answer_chars": answer_chars,
    }


def write_trace_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_trace_summary_report(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Trace Summary",
        "",
        f"- records: {summary.get('records')}",
        f"- empty_run: `{summary.get('empty_run')}`",
        f"- errors: {summary.get('errors')}",
        f"- parse_failures: {summary.get('parse_failures')}",
        f"- remote_tokens: `{json.dumps(summary.get('remote_tokens'), sort_keys=True)}`",
        f"- latency_ms: `{json.dumps(summary.get('latency_ms'), sort_keys=True)}`",
        "",
        "## Routes",
        "",
        "| route | count |",
        "|---|---:|",
    ]
    routes = summary.get("routes") or {}
    for route, count in sorted(routes.items()):
        lines.append(f"| {route} | {count} |")

    ingestion_errors = summary.get("ingestion_errors") or []
    if ingestion_errors:
        lines.extend(["", "## Ingestion Errors", ""])
        for error in ingestion_errors:
            lines.append(f"- {error}")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Route distribution shows whether policy is drifting toward local or remote paths.",
            "- Remote token totals show budget pressure before real Fireworks calibration.",
            "- Parse failures and error routes are release blockers if they grow in offline runs.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _sum_tokens(target: dict[str, int], payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    for key in target:
        target[key] += _int(payload.get(key))


def _sum_latency(target: dict[str, int], record: dict[str, Any]) -> None:
    extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
    for key in LATENCY_KEYS:
        target[key] += _int(record.get(key)) + _int(extra.get(key))
    for legacy_key, normalized_key in LEGACY_LATENCY_MAP.items():
        target[normalized_key] += _int(record.get(legacy_key)) + _int(extra.get(legacy_key))


def _is_parse_failure(record: dict[str, Any]) -> bool:
    extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
    fireworks_decision = extra.get("fireworks_decision") if isinstance(extra.get("fireworks_decision"), dict) else {}
    return any(
        [
            bool(record.get("fireworks_parse_failed")),
            bool(extra.get("fireworks_parse_failed")),
            bool(fireworks_decision.get("parse_failed")),
        ]
    )


def _is_error_record(record: dict[str, Any]) -> bool:
    route = str(record.get("route") or "")
    extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
    return any(
        [
            "error" in route,
            bool(record.get("error")),
            bool(extra.get("error")),
            any(str(key).endswith("_error") for key in extra),
        ]
    )


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
