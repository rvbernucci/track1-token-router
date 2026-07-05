#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


MATRIX_PATH = Path("docs/TEST_MATRIX.md")


@dataclass(frozen=True)
class DomainCoverage:
    domain: str
    automated_tests: list[str]
    playground: list[str]

    @property
    def has_automated_test(self) -> bool:
        return bool(self.automated_tests)


def load_matrix(path: Path = MATRIX_PATH) -> list[DomainCoverage]:
    rows: list[DomainCoverage] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        if line.startswith("| Domain ") or line.startswith("|---"):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) < 4:
            continue
        rows.append(
            DomainCoverage(
                domain=columns[0],
                automated_tests=_extract_paths(columns[2]),
                playground=_extract_paths(columns[3]),
            )
        )
    return rows


def validate_matrix(path: Path = MATRIX_PATH) -> list[str]:
    errors: list[str] = []
    rows = load_matrix(path)
    if not rows:
        errors.append("test matrix has no domains")
    for row in rows:
        if not row.has_automated_test:
            errors.append(f"{row.domain}: missing automated test")
        for test_path in row.automated_tests:
            if not Path(test_path).exists():
                errors.append(f"{row.domain}: missing test file {test_path}")
        for playground_path in row.playground:
            if playground_path != "none" and not Path(playground_path).exists():
                errors.append(f"{row.domain}: missing playground file {playground_path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="List and validate test coverage domains.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")
    parser.add_argument("--check", action="store_true", help="Fail if the matrix is incomplete.")
    args = parser.parse_args()

    rows = load_matrix()
    if args.json:
        print(json.dumps([row.__dict__ for row in rows], indent=2, sort_keys=True))
    else:
        for row in rows:
            print(f"{row.domain}: tests={','.join(row.automated_tests)} playground={','.join(row.playground)}")

    errors = validate_matrix()
    if args.check and errors:
        for error in errors:
            print(f"coverage error: {error}")
        return 1
    return 0


def _extract_paths(value: str) -> list[str]:
    if value == "none":
        return []
    return re.findall(r"`([^`]+)`", value)


if __name__ == "__main__":
    raise SystemExit(main())
