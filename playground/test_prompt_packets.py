from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.core.contracts import TaskEnvelope
from router.core.prompts import build_m1_messages, build_m2a_messages, build_m2b_messages, build_fireworks_audit_messages
from router.core.verifier import VerificationDecision


def main() -> int:
    task = TaskEnvelope(id="playground", input_text="What is 2+2?")
    verification = VerificationDecision.escalate(
        reason="playground risk",
        failure_modes=["math"],
    )
    packets = {
        "m1": build_m1_messages(task),
        "m2a": build_m2a_messages(task, "4", policy="balanced"),
        "m2b": build_m2b_messages(task, "5", verification),
        "fireworks": build_fireworks_audit_messages(task, "5", "4", verification),
    }
    print(
        json.dumps(
            {name: {"messages": len(messages), "roles": [message["role"] for message in messages]} for name, messages in packets.items()},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
