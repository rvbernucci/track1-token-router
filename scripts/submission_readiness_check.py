#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REQUIRED_SUBMISSION_FILES = {
    "title.md",
    "short-description.md",
    "long-description.md",
    "tags.md",
    "video-script.md",
    "slides-outline.md",
    "demo-plan.md",
    "cover-brief.md",
}

REQUIRED_REPO_FILES = {
    "README.md",
    "SUBMISSION.md",
    "CREDIT_ACTIVATION.md",
    "Dockerfile",
    ".github/workflows/ci.yml",
}


@dataclass(frozen=True)
class SubmissionReadiness:
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


def check_submission_readiness(root: Path = Path(".")) -> SubmissionReadiness:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, object] = {}
    submission_root = root / "submission"
    if not submission_root.exists():
        return SubmissionReadiness(False, [f"missing {submission_root}"], warnings, metrics)

    _check_required_files(submission_root, REQUIRED_SUBMISSION_FILES, errors)
    _check_required_files(root, REQUIRED_REPO_FILES, errors)
    if errors:
        return SubmissionReadiness(False, errors, warnings, metrics)

    title = _read(submission_root / "title.md")
    short = _read(submission_root / "short-description.md")
    long = _read(submission_root / "long-description.md")
    tags = _read(submission_root / "tags.md")
    video = _read(submission_root / "video-script.md")
    slides = _read(submission_root / "slides-outline.md")
    demo = _read(submission_root / "demo-plan.md")
    cover = _read(submission_root / "cover-brief.md")

    metrics["title"] = title.strip()
    metrics["short_description_chars"] = len(short.strip())
    metrics["long_description_words"] = _word_count(long)
    metrics["tags"] = _bullet_count(tags)
    metrics["video_script_words"] = _word_count(video)
    metrics["slides"] = len(re.findall(r"^## Slide\s+\d+", slides, flags=re.MULTILINE))

    if not title.strip():
        errors.append("title is empty")
    if len(short.strip()) > 255:
        errors.append("short description must be <= 255 characters")
    if len(short.strip()) < 40:
        errors.append("short description is too short to explain the project")
    if _word_count(long) < 100:
        errors.append("long description must have at least 100 words")
    if _bullet_count(tags) < 6:
        errors.append("tags.md must contain at least 6 tags")
    if _word_count(video) > 750:
        errors.append("video script is likely longer than 5 minutes")
    if int(metrics["slides"]) < 8:
        errors.append("slides outline must contain at least 8 slides")
    for required in ("CLI demo", "Visual demo optional", "Demo URL checklist", "Repo public checklist", "Docker/CI checklist"):
        if required not in demo:
            errors.append(f"demo-plan.md missing section: {required}")
    if "PNG" not in cover and "JPG" not in cover:
        errors.append("cover brief must mention PNG or JPG")

    _check_submission_notes(root / "SUBMISSION.md", errors)
    _check_readme(root / "README.md", errors)
    _check_pending_items(warnings)

    return SubmissionReadiness(not errors, errors, warnings, metrics)


def write_readiness_report(path: Path, readiness: SubmissionReadiness) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics_json = json.dumps(readiness.metrics, ensure_ascii=False, sort_keys=True)
    lines = [
        "# Submission Readiness Report",
        "",
        f"- ok: `{readiness.ok}`",
        f"- metrics: `{metrics_json}`",
        "",
        "## Errors",
        "",
    ]
    lines.extend([f"- {error}" for error in readiness.errors] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in readiness.warnings] or ["- none"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate hackathon submission readiness artifacts.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/submission-readiness.md"))
    args = parser.parse_args()

    readiness = check_submission_readiness(args.root)
    write_readiness_report(args.report, readiness)
    print(json.dumps(readiness.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if readiness.ok else 1


def _check_required_files(root: Path, required: set[str], errors: list[str]) -> None:
    for relative in sorted(required):
        path = root / relative
        if not path.exists():
            errors.append(f"missing {path}")


def _check_submission_notes(path: Path, errors: list[str]) -> None:
    content = _read(path)
    for token in ("Token Efficiency Strategy", "Reproduce", "Docker", "Short Pitch"):
        if token not in content:
            errors.append(f"SUBMISSION.md missing section/token: {token}")


def _check_readme(path: Path, errors: list[str]) -> None:
    content = _read(path)
    for token in ("Instalacao local", "Modo competicao dry-run", "Docker"):
        if token not in content:
            errors.append(f"README.md missing section/token: {token}")


def _check_pending_items(warnings: list[str]) -> None:
    warnings.extend(
        [
            "Add final public repository URL in lablab form.",
            "Add final demo/video URL after recording.",
            "Replace dry-run evidence with real AMD/Fireworks benchmark after credits arrive.",
        ]
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _bullet_count(text: str) -> int:
    return len(re.findall(r"^\s*-\s+", text, flags=re.MULTILINE))


if __name__ == "__main__":
    raise SystemExit(main())
