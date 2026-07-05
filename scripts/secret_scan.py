#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


IGNORED_PARTS = {
    ".git",
    "__pycache__",
    "track1_token_router.egg-info",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

SECRET_PATTERNS = [
    re.compile(r"gho_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"fw_[A-Za-z0-9_\-]{20,}"),
]


def main() -> int:
    findings: list[str] = []
    for path in Path(".").rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"{path}: matched {pattern.pattern}")

    if findings:
        for finding in findings:
            print(finding)
        return 1

    print("secret scan ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
