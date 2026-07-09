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


def check_submission_readiness(root: Path = Path("."), *, strict: bool = False) -> SubmissionReadiness:
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
    if strict:
        _check_strict_artifacts(root, errors, warnings, metrics)
    _check_pending_items(root, warnings)

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
    parser.add_argument("--strict", action="store_true", help="Require final URLs, CI status and final artifacts.")
    args = parser.parse_args()

    readiness = check_submission_readiness(args.root, strict=args.strict)
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


def _check_strict_artifacts(root: Path, errors: list[str], warnings: list[str], metrics: dict[str, object]) -> None:
    final_root = root / "submission" / "final"
    status_path = final_root / "submission-status.json"
    metrics["strict_mode"] = True
    if not final_root.exists():
        errors.append("strict: missing submission/final")
        return
    status = _load_status(status_path, errors)
    metrics["strict_status"] = status

    repo_url = str(status.get("repo_url") or "")
    demo_url = str(status.get("demo_url") or "")
    video_url = str(status.get("video_url") or "")
    ci_status = str(status.get("ci_status") or "")
    docker_image = str(status.get("docker_image") or "")
    image_audit_status = str(status.get("image_audit_status") or "")
    if not repo_url.startswith("https://"):
        errors.append("strict: repo_url must be a public https URL")
    if not demo_url.startswith("https://"):
        errors.append("strict: demo_url must be a public https URL")
    if ci_status != "green":
        errors.append("strict: ci_status must be green")
    if not _is_explicit_ghcr_image(docker_image):
        errors.append("strict: docker_image must be an explicit ghcr.io image tag or digest")
    if image_audit_status != "green":
        errors.append("strict: image_audit_status must be green")

    slides_pdf = final_root / "slides.pdf"
    if not slides_pdf.exists() or slides_pdf.stat().st_size < 100 or not slides_pdf.read_bytes().startswith(b"%PDF-"):
        errors.append("strict: submission/final/slides.pdf must exist and be a valid PDF")
    _check_lablab_submit_fields(final_root / "lablab-submit-fields.md", status, errors)
    cover_candidates = [final_root / "cover.png", final_root / "cover.jpg", final_root / "cover.jpeg"]
    if not any(path.exists() and path.stat().st_size >= 100 for path in cover_candidates):
        errors.append("strict: submission/final/cover.png or cover.jpg must exist")

    video_files = [path for path in final_root.glob("*.mp4") if _is_valid_mp4(path)]
    metrics["strict_video_files"] = [str(path.relative_to(root)) for path in video_files]
    placeholder_ok = bool(status.get("video_placeholder_approved")) and (final_root / "video-placeholder-approved.md").exists()
    if not video_url.startswith("https://") and not video_files and not placeholder_ok:
        errors.append("strict: provide video_url, video MP4, or approved video placeholder")
    if placeholder_ok and not video_url and not video_files:
        warnings.append("strict: video placeholder is approved but must be replaced before final submission")


def _check_lablab_submit_fields(path: Path, status: dict[str, object], errors: list[str]) -> None:
    if not path.exists():
        errors.append("strict: missing submission/final/lablab-submit-fields.md")
        return
    content = _read(path)
    required_literals = [
        "lablab.ai Submission Fields",
        "Track 1 - Hybrid Token-Efficient Routing Agent",
        "Public Docker Image",
        "Image Audit Command",
        "scripts/competition_submission_audit.py",
        str(status.get("repo_url") or ""),
        str(status.get("demo_url") or ""),
        str(status.get("docker_image") or ""),
        str(status.get("release_tag") or ""),
        str(status.get("commit_sha") or ""),
    ]
    for literal in required_literals:
        if literal and literal not in content:
            errors.append(f"strict: lablab-submit-fields.md missing literal: {literal}")


def _is_explicit_ghcr_image(value: str) -> bool:
    if not value.startswith("ghcr.io/"):
        return False
    if "@sha256:" in value:
        return True
    slash = value.rfind("/")
    colon = value.rfind(":")
    if colon <= slash:
        return False
    tag = value[colon + 1 :]
    return bool(tag) and tag != "latest"


def _is_valid_mp4(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1000:
        return False
    header = path.read_bytes()[:16]
    return len(header) >= 12 and header[4:8] == b"ftyp"


def _load_status(path: Path, errors: list[str]) -> dict[str, object]:
    if not path.exists():
        errors.append("strict: missing submission/final/submission-status.json")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"strict: invalid submission status JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("strict: submission status must be a JSON object")
        return {}
    return payload


def _check_pending_items(root: Path, warnings: list[str]) -> None:
    final_root = root / "submission" / "final"
    status = _load_optional_status(final_root / "submission-status.json")
    repo_url = str(status.get("repo_url") or "")
    video_url = str(status.get("video_url") or "")
    video_files = [path for path in final_root.glob("*.mp4") if _is_valid_mp4(path)] if final_root.exists() else []
    if not repo_url.startswith("https://"):
        warnings.append("Add final public repository URL in lablab form.")
    if not video_url.startswith("https://") and not video_files:
        warnings.append("Add final demo/video URL after recording.")
    warnings.append("Replace dry-run evidence with real AMD/Fireworks benchmark after final official evaluator access is available.")


def _load_optional_status(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _bullet_count(text: str) -> int:
    return len(re.findall(r"^\s*-\s+", text, flags=re.MULTILINE))


if __name__ == "__main__":
    raise SystemExit(main())
