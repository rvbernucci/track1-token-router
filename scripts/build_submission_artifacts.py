#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path


FINAL_ROOT = Path("submission/final")
SLIDES_PDF = FINAL_ROOT / "slides.pdf"
COVER_PNG = FINAL_ROOT / "cover.png"
SPEAKER_NOTES = FINAL_ROOT / "speaker-notes.md"
MANIFEST = FINAL_ROOT / "artifact-manifest.json"
VIDEO_PLACEHOLDER = FINAL_ROOT / "video-placeholder-approved.md"
FINAL_README = FINAL_ROOT / "README.md"
LABLAB_FIELDS = FINAL_ROOT / "lablab-submit-fields.md"
SUBMISSION_STATUS = FINAL_ROOT / "submission-status.json"


def build_submission_artifacts(root: Path = Path(".")) -> dict[str, object]:
    final_root = root / FINAL_ROOT
    final_root.mkdir(parents=True, exist_ok=True)
    slides = _parse_slides(root / "submission" / "slides-outline.md")
    _write_pdf(root / SLIDES_PDF, slides)
    _write_cover_png(root / COVER_PNG)
    _write_speaker_notes(root / SPEAKER_NOTES, slides)
    _write_video_placeholder(root / VIDEO_PLACEHOLDER)
    _write_final_readme(root / FINAL_README)
    _write_lablab_fields(root / LABLAB_FIELDS, root)
    manifest = _manifest(root, slides)
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def validate_submission_artifacts(root: Path = Path(".")) -> list[str]:
    errors: list[str] = []
    for relative in (SLIDES_PDF, COVER_PNG, SPEAKER_NOTES, MANIFEST, VIDEO_PLACEHOLDER, FINAL_README, LABLAB_FIELDS):
        path = root / relative
        if not path.exists():
            errors.append(f"missing {relative}")
            continue
        if path.stat().st_size < 100:
            errors.append(f"{relative} is unexpectedly small")
    if (root / SLIDES_PDF).exists() and not (root / SLIDES_PDF).read_bytes().startswith(b"%PDF-"):
        errors.append("slides.pdf is not a PDF")
    if (root / COVER_PNG).exists() and not (root / COVER_PNG).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        errors.append("cover.png is not a PNG")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build final or placeholder hackathon submission artifacts.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true", help="Fail if generated artifacts are invalid.")
    args = parser.parse_args()

    manifest = build_submission_artifacts(args.root)
    errors = validate_submission_artifacts(args.root)
    print(json.dumps({"ok": not errors, "errors": errors, "manifest": manifest}, sort_keys=True))
    return 0 if not args.check or not errors else 1


def _parse_slides(path: Path) -> list[dict[str, str]]:
    content = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^## Slide\s+(\d+)\s+-\s+(.+)$", content, flags=re.MULTILINE))
    slides: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        slides.append(
            {
                "number": match.group(1),
                "title": match.group(2).strip(),
                "body": body,
            }
        )
    if not slides:
        raise ValueError(f"no slides found in {path}")
    return slides


def _write_pdf(path: Path, slides: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    objects: list[bytes] = []
    pages_ids = []
    font_id = 3
    for slide in slides:
        content = _pdf_text_stream(slide)
        content_id = len(objects) + 4
        page_id = len(objects) + 5
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content
            + b"\nendstream"
        )
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1280 720] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        pages_ids.append(page_id)

    pdf_objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in pages_ids)}] /Count {len(pages_ids)} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        *objects,
    ]
    _write_pdf_objects(path, pdf_objects)


def _write_pdf_objects(path: Path, objects: list[bytes]) -> None:
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(b"".join(chunks))


def _pdf_text_stream(slide: dict[str, str]) -> bytes:
    title = _pdf_escape(f"Slide {slide['number']} - {slide['title']}")
    body_lines = [_pdf_escape(line.strip()) for line in slide["body"].splitlines() if line.strip()]
    commands = [
        "BT",
        "/F1 34 Tf",
        "72 642 Td",
        f"({title}) Tj",
        "/F1 20 Tf",
    ]
    y_step = -34
    for line in body_lines[:8]:
        commands.append(f"0 {y_step} Td")
        commands.append(f"({line[:120]}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_cover_png(path: Path, width: int = 1280, height: int = 720) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            warm = int(45 + 120 * (x / width))
            ember = int(35 + 150 * (y / height))
            pulse = 70 if (x // 90 + y // 90) % 2 == 0 else 20
            row.extend((min(255, warm + pulse), min(255, ember), 28))
        rows.append(bytes(row))
    raw = b"".join(rows)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(raw, level=9))
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _write_speaker_notes(path: Path, slides: list[dict[str, str]]) -> None:
    lines = ["# Speaker Notes", ""]
    for slide in slides:
        lines.extend(
            [
                f"## Slide {slide['number']} - {slide['title']}",
                "",
                _short_note(slide["body"]),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_video_placeholder(path: Path) -> None:
    path.write_text(
        "# Video Placeholder Approved\n\n"
        "Final MP4 or hosted video URL is expected after recording. "
        "This placeholder is allowed only before final upload and is checked by strict readiness.\n",
        encoding="utf-8",
    )


def _write_final_readme(path: Path) -> None:
    path.write_text(
        "# Final Submission Artifacts\n\n"
        "Generated with:\n\n"
        "```bash\n"
        "python3 scripts/build_submission_artifacts.py --check\n"
        "```\n\n"
        "## Contents\n\n"
        "- `slides.pdf`: generated placeholder deck from `submission/slides-outline.md`.\n"
        "- `cover.png`: generated placeholder cover image.\n"
        "- `speaker-notes.md`: short notes generated from the slide outline.\n"
        "- `video-placeholder-approved.md`: temporary placeholder until final recording is uploaded.\n"
        "- `submission-status.json`: strict readiness status for repo, demo, video, CI and public GHCR image.\n"
        "- `lablab-submit-fields.md`: copy-paste fields for the lablab.ai submission form.\n\n"
        "Replace visual placeholders before final submission if a designed deck or cover is available.\n",
        encoding="utf-8",
    )


def _write_lablab_fields(path: Path, root: Path) -> None:
    status = _load_status(root / SUBMISSION_STATUS)
    title = _read_text(root / "submission" / "title.md").strip()
    short = _read_text(root / "submission" / "short-description.md").strip()
    long = _strip_markdown_title(_read_text(root / "submission" / "long-description.md")).strip()
    tags = _strip_markdown_title(_read_text(root / "submission" / "tags.md")).strip()
    docker_image = str(status.get("docker_image") or "PENDING_GHCR_IMAGE")
    release_tag = str(status.get("release_tag") or "PENDING_RELEASE_TAG")
    commit_sha = str(status.get("commit_sha") or "PENDING_COMMIT_SHA")
    demo_url = str(status.get("demo_url") or "PENDING_DEMO_URL")
    repo_url = str(status.get("repo_url") or "PENDING_REPO_URL")
    raw_video_url = str(status.get("video_url") or "")
    video_url = raw_video_url
    if not raw_video_url:
        video_url = "PENDING_VIDEO_URL - placeholder approved until final recording upload"
    lines = [
        "# lablab.ai Submission Fields",
        "",
        "Use this as the copy-paste source of truth for the final hackathon form.",
        "",
        "## Project Title",
        "",
        title,
        "",
        "## Short Description",
        "",
        short,
        "",
        "## Long Description",
        "",
        long,
        "",
        "## Tags",
        "",
        tags,
        "",
        "## Track",
        "",
        "Track 1 - Hybrid Token-Efficient Routing Agent",
        "",
        "## Public Repository",
        "",
        repo_url,
        "",
        "## Demo URL",
        "",
        demo_url,
        "",
        "## Video URL",
        "",
        video_url,
        "",
        "## Public Docker Image",
        "",
        docker_image,
        "",
        "## Release Evidence",
        "",
        f"- release_tag: `{release_tag}`",
        f"- commit_sha: `{commit_sha}`",
        f"- ci_status: `{status.get('ci_status', 'unknown')}`",
        f"- release_status: `{status.get('release_status', 'unknown')}`",
        f"- image_audit_status: `{status.get('image_audit_status', 'unknown')}`",
        f"- image_platform: `{status.get('image_platform', 'unknown')}`",
        f"- image_compressed_size_bytes: `{status.get('image_compressed_size_bytes', 'unknown')}`",
        "",
        "## Image Audit Command",
        "",
        "```bash",
        "python3 scripts/competition_submission_audit.py \\",
        f"  --image {docker_image} \\",
        f"  --expected-revision {commit_sha} \\",
        f"  --expected-version {release_tag}",
        "```",
        "",
        "## Notes",
        "",
        "- Submit the Docker image above for Track 1.",
        "- Replace the video URL before final submission if lablab requires a hosted video.",
        "- Keep this file aligned with `submission/final/submission-status.json`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _manifest(root: Path, slides: list[dict[str, str]]) -> dict[str, object]:
    return {
        "slides": len(slides),
        "artifacts": {
            str(relative): (root / relative).stat().st_size
            for relative in (SLIDES_PDF, COVER_PNG, SPEAKER_NOTES, VIDEO_PLACEHOLDER, FINAL_README, LABLAB_FIELDS)
        },
        "notes": "Generated placeholder artifacts. Replace visuals before final submission if a designed deck/cover is available.",
    }


def _short_note(body: str) -> str:
    compact = " ".join(line.strip() for line in body.splitlines() if line.strip())
    return compact[:220] + ("..." if len(compact) > 220 else "")


def _load_status(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_markdown_title(value: str) -> str:
    return re.sub(r"^# .+?\n+", "", value.strip(), count=1)


if __name__ == "__main__":
    raise SystemExit(main())
