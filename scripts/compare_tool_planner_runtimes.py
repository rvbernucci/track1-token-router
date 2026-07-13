#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--litert", type=Path, required=True)
    parser.add_argument("--cuda", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    litert = json.loads(args.litert.read_text())
    cuda = json.loads(args.cuda.read_text())
    left = {row["id"]: row for row in litert["rows"]}
    right = {row["id"]: row for row in cuda["rows"]}
    ids = sorted(set(left) & set(right))
    rows = []
    for identifier in ids:
        lrow, crow = left[identifier], right[identifier]
        rows.append({
            "id": identifier,
            "litert_tool": (lrow.get("actual") or {}).get("tool"),
            "cuda_tool": (crow.get("actual") or {}).get("tool"),
            "tool_agreement": (lrow.get("actual") or {}).get("tool") == (crow.get("actual") or {}).get("tool"),
            "plan_agreement": lrow.get("actual") == crow.get("actual"),
            "release_agreement": lrow["route"]["accepted"] == crow["route"]["accepted"],
            "answer_agreement": lrow["route"]["answer"] == crow["route"]["answer"],
        })
    payload = {
        "schema_version": "tool-planner-runtime-parity-v1",
        "litert_sha256": _sha(args.litert), "cuda_sha256": _sha(args.cuda),
        "common_tasks": len(rows),
        "tool_agreement": sum(row["tool_agreement"] for row in rows),
        "plan_agreement": sum(row["plan_agreement"] for row in rows),
        "release_agreement": sum(row["release_agreement"] for row in rows),
        "answer_agreement": sum(row["answer_agreement"] for row in rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, sort_keys=True))
    return 0


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
