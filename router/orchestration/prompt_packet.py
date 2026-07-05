from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

from router.core.contracts import TaskEnvelope
from router.core.policy import simulate_policy_route


REMOTE_AUDIT_ROUTES = {"fireworks_replaced", "m2b_fireworks_approved", "m2b_fireworks_error_approved"}


@dataclass(frozen=True)
class RemoteAuditPacket:
    task: str
    candidate: str
    concern: str
    expected_format: str

    def render(self) -> str:
        return (
            f"TASK:{self.task}\n"
            f"CANDIDATE:{self.candidate}\n"
            f"CONCERN:{self.concern}\n"
            f"EXPECTED_FORMAT:{self.expected_format}"
        )

    def chars(self) -> int:
        return len(self.render())

    def approx_tokens(self) -> int:
        return math.ceil(self.chars() / 4)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["chars"] = self.chars()
        payload["approx_tokens"] = self.approx_tokens()
        return payload


def build_remote_audit_packet(
    task: TaskEnvelope,
    candidate: str,
    concern: str,
    *,
    max_task_chars: int = 800,
    max_candidate_chars: int = 500,
) -> RemoteAuditPacket:
    return RemoteAuditPacket(
        task=_compact(task.input_text, max_task_chars),
        candidate=_compact(candidate, max_candidate_chars),
        concern=_compact(concern or "local_verifier_escalated", 240),
        expected_format=infer_expected_format(task),
    )


def estimate_policy_packet_tokens(tasks: list[TaskEnvelope], policy: str) -> int:
    total = 0
    for task in tasks:
        route = simulate_policy_route(task, policy)
        if route in REMOTE_AUDIT_ROUTES:
            packet = build_remote_audit_packet(
                task,
                candidate="LOCAL_CANDIDATE",
                concern=str(task.metadata.get("risk") or "routing_risk"),
            )
            total += packet.approx_tokens()
    return total


def infer_expected_format(task: TaskEnvelope) -> str:
    text = task.input_text.lower()
    if "json" in text:
        return "json"
    if "return only the number" in text or re.search(r"\bwhat is\b.*[+\-*/]", text):
        return "number"
    if "uppercase" in text:
        return "uppercase"
    if re.search(r"return exactly .+?(?: and nothing else)?[.!]?$", task.input_text, re.IGNORECASE):
        return "literal_echo"
    return "free_text"


def extract_literal_echo(task: TaskEnvelope) -> str:
    match = re.search(r"return exactly (.+?)(?: and nothing else)?[.!]?$", task.input_text, re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip().strip("\"'")


def _compact(value: str, max_chars: int) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."
