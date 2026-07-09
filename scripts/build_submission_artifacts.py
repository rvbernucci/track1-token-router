#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import zlib
from pathlib import Path


FINAL_ROOT = Path("submission/final")
SLIDES_PDF = FINAL_ROOT / "slides.pdf"
COVER_PNG = FINAL_ROOT / "cover.png"
SPEAKER_NOTES = FINAL_ROOT / "speaker-notes.md"
MANIFEST = FINAL_ROOT / "artifact-manifest.json"
VIDEO_PLACEHOLDER = FINAL_ROOT / "video-placeholder-approved.md"
DEMO_MP4 = FINAL_ROOT / "demo.mp4"
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
    _write_demo_video(root / DEMO_MP4, slides)
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
    if (root / DEMO_MP4).exists():
        if (root / DEMO_MP4).stat().st_size < 1000:
            errors.append("demo.mp4 is unexpectedly small")
        if not _is_valid_mp4(root / DEMO_MP4):
            errors.append("demo.mp4 is not an MP4")
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


def _write_demo_video(path: Path, slides: list[dict[str, str]]) -> bool:
    if _is_valid_mp4(path):
        return True
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="track1-video-") as tmp_name:
        tmp = Path(tmp_name)
        for index, slide in enumerate(slides, start=1):
            _write_video_frame(tmp / f"frame_{index:03d}.ppm", slide)
        pattern = str(tmp / "frame_%03d.ppm")
        commands = [
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                "1/3",
                "-i",
                pattern,
                "-vf",
                "fps=30,format=yuv420p",
                "-movflags",
                "+faststart",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "30",
                str(path),
            ],
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                "1/3",
                "-i",
                pattern,
                "-vf",
                "fps=30,format=yuv420p",
                "-movflags",
                "+faststart",
                "-c:v",
                "mpeg4",
                "-q:v",
                "6",
                str(path),
            ],
        ]
        for command in commands:
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
                return path.exists() and path.stat().st_size > 1000
            except (OSError, subprocess.CalledProcessError):
                continue
    return False


def _is_valid_mp4(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1000:
        return False
    header = path.read_bytes()[:16]
    return len(header) >= 12 and header[4:8] == b"ftyp"


def _write_video_frame(path: Path, slide: dict[str, str], width: int = 1280, height: int = 720) -> None:
    pixels = _video_background(width, height, int(slide["number"]))
    _fill_rect(pixels, width, height, 0, 0, width, 18, (242, 98, 35))
    _fill_rect(pixels, width, height, 64, 94, 1160, 3, (242, 98, 35))
    _draw_text(pixels, width, height, 68, 52, "TRACK 1 TOKEN ROUTER", 5, (250, 250, 242))
    _draw_text(pixels, width, height, 762, 58, "LOCAL-FIRST | GATED REMOTE", 3, (255, 188, 112))

    title = f"{slide['number']}. {_clean_video_text(slide['title'])}"
    y = 150
    for line in _wrap_video_text(title, max_chars=30)[:2]:
        _draw_text(pixels, width, height, 76, y, line, 7, (255, 244, 222))
        y += 72

    body = _clean_video_text(slide["body"])
    y = max(y + 20, 300)
    for line in _wrap_video_text(body, max_chars=52)[:6]:
        _draw_text(pixels, width, height, 96, y, line, 4, (226, 236, 244))
        y += 44

    _fill_rect(pixels, width, height, 70, 626, 1140, 52, (20, 35, 47))
    _draw_text(pixels, width, height, 100, 644, "DOCKER AMD64 | STRICT READINESS GREEN | PUBLIC GHCR IMAGE", 3, (167, 232, 186))
    _write_ppm(path, pixels, width, height)


def _video_background(width: int, height: int, slide_number: int) -> bytearray:
    pixels = bytearray(width * height * 3)
    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * 3
            glow = max(0, 220 - abs(x - 980) // 3 - abs(y - 130) // 2)
            ember = max(0, 190 - abs(x - 200) // 4 - abs(y - 620) // 3)
            stripe = 16 if ((x + y + slide_number * 23) // 96) % 2 == 0 else 0
            pixels[offset] = min(255, 12 + glow // 4 + ember // 3 + stripe)
            pixels[offset + 1] = min(255, 24 + glow // 6 + stripe // 2)
            pixels[offset + 2] = min(255, 36 + glow // 8)
    return pixels


def _write_ppm(path: Path, pixels: bytearray, width: int, height: int) -> None:
    path.write_bytes(f"P6\n{width} {height}\n255\n".encode("ascii") + bytes(pixels))


def _draw_text(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    scale: int,
    color: tuple[int, int, int],
) -> None:
    cursor = x
    for char in text.upper():
        if char == " ":
            cursor += 4 * scale
            continue
        pattern = FONT_5X7.get(char, FONT_5X7["?"])
        for row_index, row in enumerate(pattern):
            for col_index, bit in enumerate(row):
                if bit == "1":
                    _fill_rect(
                        pixels,
                        width,
                        height,
                        cursor + col_index * scale,
                        y + row_index * scale,
                        scale,
                        scale,
                        color,
                    )
        cursor += 6 * scale


def _fill_rect(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    rect_width: int,
    rect_height: int,
    color: tuple[int, int, int],
) -> None:
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(width, x + rect_width)
    y1 = min(height, y + rect_height)
    for yy in range(y0, y1):
        row = yy * width * 3
        for xx in range(x0, x1):
            offset = row + xx * 3
            pixels[offset] = color[0]
            pixels[offset + 1] = color[1]
            pixels[offset + 2] = color[2]


def _clean_video_text(value: str) -> str:
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"[*_#\[\]]", " ", value)
    return re.sub(r"[^A-Za-z0-9 .,:;!?()/+*=_#&|'-]", " ", value).strip()


def _wrap_video_text(value: str, max_chars: int) -> list[str]:
    return textwrap.wrap(value, width=max_chars, break_long_words=False, break_on_hyphens=False) or [""]


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
        "- `demo.mp4`: generated short demo slideshow when `ffmpeg` is available.\n"
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
    video_file = str(status.get("video_file") or "")
    if not video_file and (root / DEMO_MP4).exists():
        video_file = str(DEMO_MP4)
    raw_video_url = str(status.get("video_url") or "")
    video_url = raw_video_url
    if not raw_video_url:
        if video_file:
            video_url = f"Local MP4 included in repository: {video_file}"
        else:
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
        "- Use the local MP4 if lablab accepts uploads; replace with a hosted URL if the form requires a link.",
        "- Keep this file aligned with `submission/final/submission-status.json`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _manifest(root: Path, slides: list[dict[str, str]]) -> dict[str, object]:
    artifacts = {
        str(relative): (root / relative).stat().st_size
        for relative in (SLIDES_PDF, COVER_PNG, SPEAKER_NOTES, VIDEO_PLACEHOLDER, FINAL_README, LABLAB_FIELDS)
    }
    if (root / DEMO_MP4).exists():
        artifacts[str(DEMO_MP4)] = (root / DEMO_MP4).stat().st_size
    return {
        "slides": len(slides),
        "artifacts": artifacts,
        "notes": "Generated submission artifacts. Replace visuals before final submission if a designed deck/cover is available.",
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


FONT_5X7 = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ",": ["00000", "00000", "00000", "00000", "01100", "00100", "01000"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    ";": ["00000", "01100", "01100", "00000", "01100", "00100", "01000"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "'": ["00100", "00100", "01000", "00000", "00000", "00000", "00000"],
    '"': ["01010", "01010", "01010", "00000", "00000", "00000", "00000"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    "\\": ["10000", "01000", "01000", "00100", "00010", "00010", "00001"],
    "(": ["00010", "00100", "01000", "01000", "01000", "00100", "00010"],
    ")": ["01000", "00100", "00010", "00010", "00010", "00100", "01000"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    "*": ["00000", "10101", "01110", "11111", "01110", "10101", "00000"],
    "=": ["00000", "00000", "11111", "00000", "11111", "00000", "00000"],
    "_": ["00000", "00000", "00000", "00000", "00000", "00000", "11111"],
    "#": ["01010", "01010", "11111", "01010", "11111", "01010", "01010"],
    "&": ["01100", "10010", "10100", "01000", "10101", "10010", "01101"],
    "|": ["00100", "00100", "00100", "00100", "00100", "00100", "00100"],
    "<": ["00010", "00100", "01000", "10000", "01000", "00100", "00010"],
    ">": ["01000", "00100", "00010", "00001", "00010", "00100", "01000"],
}


if __name__ == "__main__":
    raise SystemExit(main())
