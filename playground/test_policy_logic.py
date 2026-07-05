from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.adapters.io import load_jsonl_tasks
from router.core.policy import POLICIES, simulate_policy_route


def main() -> int:
    tasks = load_jsonl_tasks(Path("evals/offline/tasks.jsonl"))
    sample = tasks[:8]
    rows = []
    for task in sample:
        rows.append(
            {
                "id": task.id,
                "category": task.metadata.get("category"),
                "expected_route": task.metadata.get("expected_route"),
                "routes": {policy: simulate_policy_route(task, policy) for policy in POLICIES},
            }
        )

    print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
