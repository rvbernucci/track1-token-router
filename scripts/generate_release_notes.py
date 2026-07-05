#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local Markdown release notes from git log.")
    parser.add_argument("--tag", default=os.getenv("GITHUB_REF_NAME", "local-dry-run"))
    parser.add_argument("--from-ref", help="Optional previous tag or commit. When omitted, recent commits are used.")
    parser.add_argument("--to-ref", default="HEAD")
    parser.add_argument("--max-commits", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path("reports/generated/release-notes.md"))
    args = parser.parse_args()

    commits = _git_log(args.from_ref, args.to_ref, args.max_commits)
    notes = _render_notes(args.tag, args.from_ref, args.to_ref, commits)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(notes, encoding="utf-8")
    print(str(args.output))
    return 0


def _git_log(from_ref: str | None, to_ref: str, max_commits: int) -> list[tuple[str, str]]:
    range_ref = f"{from_ref}..{to_ref}" if from_ref else to_ref
    completed = subprocess.run(
        ["git", "log", f"-{max_commits}", "--format=%h%x09%s", range_ref],
        check=True,
        capture_output=True,
        text=True,
    )
    commits: list[tuple[str, str]] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        commits.append((sha.strip(), subject.strip()))
    return commits


def _render_notes(tag: str, from_ref: str | None, to_ref: str, commits: list[tuple[str, str]]) -> str:
    source = f"{from_ref}..{to_ref}" if from_ref else to_ref
    lines = [
        f"# Release {tag}",
        "",
        f"- source: `{source}`",
        f"- commits: {len(commits)}",
        "",
        "## Changes",
        "",
    ]
    if commits:
        for sha, subject in commits:
            lines.append(f"- {subject} (`{sha}`)")
    else:
        lines.append("- No commits found.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
