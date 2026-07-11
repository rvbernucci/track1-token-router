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
    if (
        "return only python code" in text
        or re.search(r"\b(?:write|provide)\s+only\s+(?:python|javascript|typescript|java|rust|go|c\+\+)\s+code\b", text)
        or "return only corrected python code" in text
        or "return only code" in text
        or re.search(r"\b(?:write|return|provide)\s+only\s+the\s+.*\bfunction signature\b", text)
        or re.search(
            r"\b(?:write|return|provide)\s+only\s+(?:the\s+)?(?:source|corrected|complete|working|implementation)\s+code\b",
            text,
        )
        or re.search(r"\b(?:write|define|implement|create)\s+a\s+(?:rust|javascript|typescript|java|c\+\+|go)\s+function\b", text)
        or re.search(
            r"\b(?:write|define|implement|create)\s+(?:only\s+)?(?:a|an|the)\s+"
            r"(?:python\s+)?(?:function|class|method)\b",
            text,
        )
        or re.search(r"\b(?:provide|return)\s+(?:only\s+)?(?:a|the)\s+complete\s+(?:python\s+)?implementation\b", text)
        or ("corrected implementation" in text and re.search(r"\b(debug|bug|fix|broken)\b", text))
    ):
        return "code"
    if (
        "return only the number" in text
        or re.search(r"\b(?:return|provide|answer with)\s+only\s+(?:the\s+)?(?:final\s+)?numeric(?: value)?\b", text)
        or re.search(r"\bwhat is\b.*[+\-*/]", text)
    ):
        return "number"
    if "uppercase" in text:
        return "uppercase"
    if re.search(r"\b(?:return|answer|respond)\s+(?:exactly\s+)?(?:yes\s+or\s+no|yes/no)\b", text):
        return "yes_no"
    if extract_literal_echo(task):
        return "literal_echo"
    return "free_text"


def extract_literal_echo(task: TaskEnvelope) -> str:
    explicit = re.search(
        r"return exactly this string and nothing else\s*:\s*(.+?)[.!]?$",
        task.input_text,
        re.IGNORECASE,
    )
    if explicit:
        return explicit.group(1).strip().strip("\"'")
    match = re.search(
        r"return exactly (.+?)(?: and nothing else)?[.!]?$",
        task.input_text,
        re.IGNORECASE,
    )
    if match is None:
        return ""
    raw = match.group(1).strip()
    quoted = len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'"
    candidate = raw.strip("\"'")
    # Avoid treating natural instructions such as "return exactly one sentence"
    # as literal payloads. Unquoted literals must be a single token.
    if not quoted and re.search(r"\s", candidate):
        return ""
    return candidate


def _compact(value: str, max_chars: int) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."
