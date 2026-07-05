#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.analytics.traces import load_trace_records, summarize_traces, write_trace_summary_report
from router.evals.offline_dataset import SECRET_PATTERNS


DEFAULT_LOGS = ["fixtures/logs/sample-run.jsonl"]
LONG_TEXT_KEYS = {
    "prompt",
    "input_text",
    "model_1_candidate_raw",
    "model_2_alternative_raw",
    "fireworks_raw",
    "m2a_raw",
    "candidate",
    "answer",
}
PRIVATE_IP_PATTERN = re.compile(
    r"\b(?:"
    r"10\.(?:\d{1,3}\.){2}\d{1,3}|"
    r"127\.(?:\d{1,3}\.){2}\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")\b"
)
ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![\w:])/(?:Users|home|tmp|private|var|opt)/[^\s)`'\"]+")
PRIVATE_HOST_PATTERN = re.compile(r"\b[\w.-]+\.(?:internal|local|lan|corp|private)\b", re.IGNORECASE)
ENV_SECRET_PATTERN = re.compile(r"(?im)\b[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET)[ \t]*=[ \t]*[A-Za-z0-9_\-]{12,}")


@dataclass
class RedactionStats:
    long_texts: int = 0
    absolute_paths: int = 0
    private_ips: int = 0
    private_hosts: int = 0
    env_secrets: int = 0
    secret_tokens: int = 0
    records: int = 0
    files: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "records": self.records,
            "files": self.files,
            "redactions": {
                "long_texts": self.long_texts,
                "absolute_paths": self.absolute_paths,
                "private_ips": self.private_ips,
                "private_hosts": self.private_hosts,
                "env_secrets": self.env_secrets,
                "secret_tokens": self.secret_tokens,
            },
            "errors": self.errors,
        }


def redact_logs(
    *,
    logs: list[str] | None = None,
    public_root: Path = Path("reports/public/traces"),
    report_path: Path = Path("reports/generated/redaction-report.md"),
    trace_summary_path: Path = Path("reports/public/trace-summary.md"),
    max_text_chars: int = 240,
) -> dict[str, Any]:
    source_paths = _expand_logs(logs or DEFAULT_LOGS)
    stats = RedactionStats(files=len(source_paths))
    public_root.mkdir(parents=True, exist_ok=True)
    redacted_records: list[dict[str, Any]] = []
    output_files: list[str] = []

    for source in source_paths:
        records, errors = load_trace_records([source])
        stats.errors.extend(errors)
        target = public_root / f"{source.stem}.redacted.jsonl"
        with target.open("w", encoding="utf-8") as handle:
            for record in records:
                redacted = _redact_value(record, key="", stats=stats, max_text_chars=max_text_chars)
                findings = _blocking_findings(json.dumps(redacted, ensure_ascii=False, sort_keys=True))
                if findings:
                    stats.errors.extend([f"{source}: {finding}" for finding in findings])
                handle.write(json.dumps(redacted, ensure_ascii=False, sort_keys=True) + "\n")
                redacted_records.append(redacted)
                stats.records += 1
        output_files.append(str(target))

    summary = summarize_traces(redacted_records, source_files=[Path(path) for path in output_files], ingestion_errors=[])
    write_trace_summary_report(trace_summary_path, summary)
    result = {
        **stats.to_dict(),
        "logs": [str(path) for path in source_paths],
        "public_files": output_files,
        "trace_summary": str(trace_summary_path),
        "report": str(report_path),
    }
    write_redaction_report(report_path, result)
    return result


def write_redaction_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Redaction Report",
        "",
        f"- ok: `{result['ok']}`",
        f"- files: `{result['files']}`",
        f"- records: `{result['records']}`",
        f"- public_files: `{len(result['public_files'])}`",
        f"- trace_summary: `{result['trace_summary']}`",
        "",
        "## Redactions",
        "",
    ]
    for key, value in result["redactions"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Public Files", ""])
    lines.extend([f"- {path}" for path in result["public_files"]] or ["- none"])
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {error}" for error in result["errors"]] or ["- none"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Redact router JSONL logs into safe public traces.")
    parser.add_argument("--logs", nargs="*", default=DEFAULT_LOGS)
    parser.add_argument("--public-root", type=Path, default=Path("reports/public/traces"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/redaction-report.md"))
    parser.add_argument("--trace-summary", type=Path, default=Path("reports/public/trace-summary.md"))
    parser.add_argument("--max-text-chars", type=int, default=240)
    parser.add_argument("--check", action="store_true", help="Fail if redacted logs still contain sensitive content.")
    args = parser.parse_args()

    result = redact_logs(
        logs=args.logs,
        public_root=args.public_root,
        report_path=args.report,
        trace_summary_path=args.trace_summary,
        max_text_chars=args.max_text_chars,
    )
    print(json.dumps({"ok": result["ok"], "redactions": result["redactions"], "errors": result["errors"]}, sort_keys=True))
    return 0 if result["ok"] or not args.check else 1


def _expand_logs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = sorted(Path(".").glob(pattern)) if any(token in pattern for token in "*?[]") else []
        if matches:
            paths.extend(matches)
            continue
        path = Path(pattern)
        if path.exists():
            paths.append(path)
    return sorted(set(paths))


def _redact_value(value: Any, *, key: str, stats: RedactionStats, max_text_chars: int) -> Any:
    if isinstance(value, dict):
        return {
            item_key: _redact_value(item_value, key=str(item_key), stats=stats, max_text_chars=max_text_chars)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, key=key, stats=stats, max_text_chars=max_text_chars) for item in value]
    if isinstance(value, str):
        return _redact_text(value, key=key, stats=stats, max_text_chars=max_text_chars)
    return value


def _redact_text(value: str, *, key: str, stats: RedactionStats, max_text_chars: int) -> str:
    sanitized = value
    sanitized, count = ABSOLUTE_PATH_PATTERN.subn("[REDACTED_PATH]", sanitized)
    stats.absolute_paths += count
    sanitized, count = PRIVATE_IP_PATTERN.subn("[REDACTED_PRIVATE_IP]", sanitized)
    stats.private_ips += count
    sanitized, count = PRIVATE_HOST_PATTERN.subn("[REDACTED_PRIVATE_HOST]", sanitized)
    stats.private_hosts += count
    sanitized, count = ENV_SECRET_PATTERN.subn("[REDACTED_ENV_SECRET]", sanitized)
    stats.env_secrets += count
    for pattern in SECRET_PATTERNS:
        sanitized, count = pattern.subn("[REDACTED_SECRET_TOKEN]", sanitized)
        stats.secret_tokens += count
    if _is_long_text_key(key) and len(sanitized) > max_text_chars:
        stats.long_texts += 1
        digest = hashlib.sha256(sanitized.encode("utf-8")).hexdigest()[:12]
        return f"[REDACTED_LONG_TEXT chars={len(sanitized)} sha256={digest}]"
    return sanitized


def _blocking_findings(text: str) -> list[str]:
    findings = []
    if ABSOLUTE_PATH_PATTERN.search(text):
        findings.append("local absolute path found after redaction")
    if PRIVATE_IP_PATTERN.search(text):
        findings.append("private IP found after redaction")
    if PRIVATE_HOST_PATTERN.search(text):
        findings.append("private hostname found after redaction")
    if ENV_SECRET_PATTERN.search(text):
        findings.append("environment secret assignment found after redaction")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(f"secret-like token found after redaction: {pattern.pattern}")
    return findings


def _is_long_text_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in LONG_TEXT_KEYS)


if __name__ == "__main__":
    raise SystemExit(main())
