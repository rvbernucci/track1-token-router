from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.adapters.official import get_adapter
from router.core.contracts import AnswerResult


def main() -> int:
    fixture = Path("fixtures/official/json_task.json").read_text(encoding="utf-8")
    adapter = get_adapter("json_task")
    task = adapter.parse(fixture)[0]
    result = AnswerResult(id=task.id, answer="4", route="playground")
    payload = json.loads(adapter.format([result]))

    print(
        json.dumps(
            {
                "adapter": adapter.name,
                "task_id": task.id,
                "input_text": task.input_text,
                "output_answer": payload["answer"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
