#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.offline_dataset import SECRET_PATTERNS


REPORTS = {
    "battle-report.md": "battle-report.md",
    "fuzz-report.md": "fuzz-report.md",
    "submission-readiness.md": "submission-readiness.md",
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
ENV_SECRET_PATTERN = re.compile(r"(?im)^[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET)[ \t]*=[ \t]*[A-Za-z0-9_\-]{12,}")


@dataclass(frozen=True)
class ExportResult:
    exported: list[str]
    errors: list[str]
    redactions: dict[str, int]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "exported": self.exported,
            "errors": self.errors,
            "redactions": self.redactions,
        }


def export_public_reports(
    *,
    generated_root: Path = Path("reports/generated"),
    public_root: Path = Path("reports/public"),
    demo_root: Path = Path("demo-site"),
) -> ExportResult:
    exported: list[str] = []
    errors: list[str] = []
    redactions: dict[str, int] = {}
    public_root.mkdir(parents=True, exist_ok=True)
    demo_reports_root = demo_root / "public-reports"
    demo_reports_root.mkdir(parents=True, exist_ok=True)

    for source_name, target_name in REPORTS.items():
        source = generated_root / source_name
        target = public_root / target_name
        if not source.exists():
            errors.append(f"missing source report: {source}")
            continue
        raw = source.read_text(encoding="utf-8")
        blocking = _blocking_findings(raw)
        if blocking:
            errors.extend([f"{source}: {finding}" for finding in blocking])
            continue
        sanitized, counts = sanitize_public_text(raw)
        for key, value in counts.items():
            redactions[key] = redactions.get(key, 0) + value
        target.write_text(sanitized, encoding="utf-8")
        (demo_reports_root / target_name).write_text(sanitized, encoding="utf-8")
        exported.append(str(target))

    manifest = {
        "source": str(generated_root),
        "exported": exported,
        "redactions": redactions,
        "safe_to_publish": not errors,
    }
    (public_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (demo_reports_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ExportResult(exported=exported, errors=errors, redactions=redactions)


def sanitize_public_text(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    sanitized, path_count = ABSOLUTE_PATH_PATTERN.subn("[REDACTED_PATH]", text)
    counts["absolute_paths"] = path_count
    sanitized, ip_count = PRIVATE_IP_PATTERN.subn("[REDACTED_PRIVATE_IP]", sanitized)
    counts["private_ips"] = ip_count
    return sanitized, counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Export shareable public reports with safety checks.")
    parser.add_argument("--generated-root", type=Path, default=Path("reports/generated"))
    parser.add_argument("--public-root", type=Path, default=Path("reports/public"))
    parser.add_argument("--demo-root", type=Path, default=Path("demo-site"))
    parser.add_argument("--check", action="store_true", help="Fail if public reports are unsafe or incomplete.")
    args = parser.parse_args()

    result = export_public_reports(
        generated_root=args.generated_root,
        public_root=args.public_root,
        demo_root=args.demo_root,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    if args.check and not result.ok:
        for error in result.errors:
            print(f"public report export error: {error}", file=sys.stderr)
        return 1
    return 0


def _blocking_findings(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(f"secret-like token found: {pattern.pattern}")
    if ENV_SECRET_PATTERN.search(text):
        findings.append("secret-like environment assignment found")
    if PRIVATE_HOST_PATTERN.search(text):
        findings.append("private hostname found")
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
