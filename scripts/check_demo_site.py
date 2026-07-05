#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.offline_dataset import SECRET_PATTERNS


REQUIRED_PUBLIC_REPORTS = {
    "public-reports/battle-report.md",
    "public-reports/fuzz-report.md",
    "public-reports/submission-readiness.md",
    "public-reports/manifest.json",
}
REQUIRED_GITHUB_LINKS = {
    "https://github.com/rvbernucci/track1-token-router/blob/main/README.md",
    "https://github.com/rvbernucci/track1-token-router/blob/main/SUBMISSION.md",
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
class DemoSiteCheck:
    ok: bool
    errors: list[str]
    warnings: list[str]
    metrics: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics,
        }


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs if value}
        if tag == "a" and values.get("href"):
            self.links.append(str(values["href"]))
        if tag in {"img", "script", "link"}:
            ref = values.get("src") or values.get("href")
            if ref:
                self.assets.append(str(ref))


def check_demo_site(root: Path = Path("."), *, expected_url: str | None = None) -> DemoSiteCheck:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, object] = {}
    demo_root = root / "demo-site"
    index_path = demo_root / "index.html"
    if not index_path.exists():
        return DemoSiteCheck(False, [f"missing {index_path}"], warnings, metrics)

    html = index_path.read_text(encoding="utf-8")
    parser = LinkParser()
    parser.feed(html)
    all_refs = parser.links + parser.assets

    metrics["link_count"] = len(parser.links)
    metrics["asset_count"] = len(parser.assets)
    metrics["demo_size_bytes"] = _directory_size(demo_root)
    metrics["expected_url"] = expected_url or ""

    _check_static_boundary(all_refs, errors)
    _check_internal_refs(demo_root, all_refs, errors)
    _check_required_reports(demo_root, errors, metrics)
    _check_required_github_links(parser.links, errors)
    _check_safety(demo_root, errors, metrics)

    if expected_url and not expected_url.startswith("https://"):
        errors.append("expected demo URL must be https")
    if not expected_url:
        warnings.append("expected demo URL not provided; local check only")

    return DemoSiteCheck(not errors, errors, warnings, metrics)


def write_demo_site_report(path: Path, result: DemoSiteCheck) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics_json = json.dumps(result.metrics, ensure_ascii=False, sort_keys=True)
    lines = [
        "# Demo Site Check",
        "",
        f"- ok: `{result.ok}`",
        f"- metrics: `{metrics_json}`",
        "",
        "## Errors",
        "",
    ]
    lines.extend([f"- {error}" for error in result.errors] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the static public demo site.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--expected-url", default="https://rvbernucci.github.io/track1-token-router/")
    parser.add_argument("--report", type=Path, default=Path("reports/generated/demo-site-check.md"))
    parser.add_argument("--check", action="store_true", help="Fail if the demo site is not publishable.")
    args = parser.parse_args()

    result = check_demo_site(args.root, expected_url=args.expected_url)
    write_demo_site_report(args.report, result)
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if result.ok or not args.check else 1


def _directory_size(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _check_static_boundary(refs: list[str], errors: list[str]) -> None:
    for ref in refs:
        parsed = urlparse(ref)
        if parsed.scheme and parsed.scheme not in {"https", "mailto"}:
            errors.append(f"unsupported URL scheme in demo link: {ref}")
        if ref.startswith(("/api/", "/v1/", "http://")):
            errors.append(f"demo must not depend on backend or insecure URL: {ref}")


def _check_internal_refs(demo_root: Path, refs: list[str], errors: list[str]) -> None:
    for ref in refs:
        parsed = urlparse(ref)
        if parsed.scheme or ref.startswith("#") or ref.startswith("mailto:"):
            continue
        local_ref = parsed.path
        if not local_ref:
            continue
        target = (demo_root / local_ref).resolve()
        try:
            target.relative_to(demo_root.resolve())
        except ValueError:
            errors.append(f"demo link escapes demo-site: {ref}")
            continue
        if not target.exists():
            errors.append(f"demo link target does not exist: {ref}")


def _check_required_reports(demo_root: Path, errors: list[str], metrics: dict[str, object]) -> None:
    present = []
    for relative in sorted(REQUIRED_PUBLIC_REPORTS):
        path = demo_root / relative
        if not path.exists():
            errors.append(f"missing public report: {path}")
        else:
            present.append(relative)
    metrics["required_public_reports_present"] = present


def _check_required_github_links(links: list[str], errors: list[str]) -> None:
    for required in sorted(REQUIRED_GITHUB_LINKS):
        if required not in links:
            errors.append(f"missing required GitHub link: {required}")


def _check_safety(demo_root: Path, errors: list[str], metrics: dict[str, object]) -> None:
    scanned_files = 0
    for path in sorted(demo_root.rglob("*")):
        if not path.is_file():
            continue
        scanned_files += 1
        text = _read_text(path)
        if text is None:
            continue
        findings = _blocking_findings(text)
        errors.extend([f"{path}: {finding}" for finding in findings])
    metrics["scanned_files"] = scanned_files


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _blocking_findings(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(f"secret-like token found: {pattern.pattern}")
    if ENV_SECRET_PATTERN.search(text):
        findings.append("secret-like environment assignment found")
    if PRIVATE_HOST_PATTERN.search(text):
        findings.append("private hostname found")
    if PRIVATE_IP_PATTERN.search(text):
        findings.append("private IP found")
    if ABSOLUTE_PATH_PATTERN.search(text):
        findings.append("local absolute path found")
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
