#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.dataset_forge.e2b_expansion import _dedup_audit, build_targets


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit generated Sprint 70 prompts and create a retry queue.")
    parser.add_argument("--retry-file", type=Path, default=Path("evals/e2b-expansion-v1/state/dedup-retry-target-ids.txt"))
    args = parser.parse_args()
    target_index = {row.target_id: row for row in build_targets()}
    generated = [json.loads(line) for line in (ROOT / "evals/e2b-expansion-v1/raw/generated-candidates.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = {str(row["target_id"]): row for row in generated}
    targets = [target_index[target_id] for target_id in selected]
    result = _dedup_audit(targets, selected)
    retry = ROOT / args.retry_file
    retry.parent.mkdir(parents=True, exist_ok=True)
    retry.write_text("".join(target_id + "\n" for target_id in result["retry_target_ids"]), encoding="utf-8")
    print(json.dumps({
        "rows": len(targets), "retry_targets": len(result["retry_target_ids"]),
        "gates": result["gates"], "retry_file": str(args.retry_file),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
