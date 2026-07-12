#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.dataset_forge.e2b_expansion import (
    ExpansionPaths, build_targets, generation_prompt, generation_schema, validate_generated,
)
from router.dataset_forge.providers import provider_from_env
from router.dataset_forge.storage import AppendOnlyJsonl


def main() -> int:
    _load_env()
    retry_ids = set((ROOT / "evals/e2b-expansion-v1/state/dedup-retry-target-ids.txt").read_text().split())
    targets = [row for row in build_targets() if row.target_id in retry_ids]
    providers = {
        name: provider_from_env(name, role="e2b_expansion_dedup_repair", max_tokens=4096)
        for name in {row.provider for row in targets}
    }
    paths = ExpansionPaths(ROOT / "evals/e2b-expansion-v1")
    candidates = AppendOnlyJsonl(paths.generated)
    responses = AppendOnlyJsonl(paths.responses)
    written = 0
    for target in targets:
        first = 11 + int(target.semantic_seed[:4], 16) % 79
        second = 11 + int(target.semantic_seed[4:8], 16) % 79
        prompt = generation_prompt([target]) + f"""

DEDUPLICATION REPAIR REQUIREMENTS:
- The previous rectangular-garden question with values 18 and 7 is forbidden.
- The new task must meaningfully use both distinctive integers {first} and {second}.
- Do not use a rectangular garden, marbles, apples, trains, or a generic textbook template.
"""
        invocation = providers[target.provider].invoke(
            prompt=prompt, response_schema=generation_schema(1), role="e2b_expansion_dedup_repair",
        )
        validated = validate_generated([target], invocation)
        responses.append_unique({
            "id": invocation.provenance.request_id, "provider": target.provider,
            "target_ids": [target.target_id], "payload": invocation.payload,
            "provenance": invocation.provenance.to_dict(), "created_at": "dedup-repair",
        })
        written += int(candidates.append_unique(validated[0]))
    print(json.dumps({"targets": len(targets), "written": written}, sort_keys=True))
    return 0


def _load_env() -> None:
    for relative in (Path(".env.dataset-forge.local"), Path(".env.fireworks.local")):
        path = ROOT / relative
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    os.environ["DATASET_FIREWORKS_MODEL"] = "accounts/fireworks/models/kimi-k2p7-code"


if __name__ == "__main__":
    raise SystemExit(main())
