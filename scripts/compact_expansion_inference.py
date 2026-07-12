#!/usr/bin/env python3
from __future__ import annotations

import json
import argparse
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.orchestration.assessment import approximate_token_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep the latest prompt-hash result per expansion task.")
    parser.add_argument("--only", choices=("functiongemma", "e2b"))
    parser.add_argument("--authoritative-runtime-id")
    parser.add_argument("--authoritative-min-prompt-tokens", type=int)
    args = parser.parse_args()
    result = {}
    base = ROOT / "reports/generated/e2b-expansion-v1"
    for name in ((args.only,) if args.only else ("functiongemma", "e2b")):
        path = base / f"{name}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        latest = {str(row["task_id"]): row for row in rows}
        plan = {row["target_id"]: row for row in _rows(ROOT / "evals/e2b-expansion-v1/plan.jsonl")}
        generated = {row["target_id"]: row for row in _rows(ROOT / "evals/e2b-expansion-v1/raw/generated-candidates.jsonl")}
        expected_hashes = {
            plan[target_id]["task_id"]: hashlib.sha256(row["prompt"].encode()).hexdigest()
            for target_id, row in generated.items()
        }
        latest = {
            task_id: row for task_id, row in latest.items()
            if row.get("prompt_sha256") == expected_hashes.get(task_id)
        }
        if name == "functiongemma" and args.authoritative_runtime_id:
            if args.authoritative_min_prompt_tokens is None:
                raise ValueError("Authoritative runtime compaction requires a prompt-token threshold.")
            forced = {
                plan[target_id]["task_id"] for target_id, row in generated.items()
                if approximate_token_count(row["prompt"]) > args.authoritative_min_prompt_tokens
            }
            authoritative = {
                str(row["task_id"]): row for row in rows
                if row.get("runtime_id") == args.authoritative_runtime_id
            }
            for task_id in forced:
                if task_id in authoritative:
                    latest[task_id] = authoritative[task_id]
                else:
                    latest.pop(task_id, None)
        path.write_text(
            "".join(json.dumps(latest[key], ensure_ascii=False, sort_keys=True) + "\n" for key in sorted(latest)),
            encoding="utf-8",
        )
        result[name] = {"before": len(rows), "after": len(latest)}
    print(json.dumps(result, sort_keys=True))
    return 0


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


if __name__ == "__main__":
    raise SystemExit(main())
