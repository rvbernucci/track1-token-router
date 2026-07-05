from __future__ import annotations

from router.core.contracts import TaskEnvelope

if False:  # pragma: no cover - imported only for type checkers without runtime cycles
    from router.core.verifier import VerificationDecision


M1_SYSTEM_PROMPT = """You are M1, the fast local answer generator.
Answer the user's task directly and naturally.
Preserve the exact output format requested by the task.
Do not mention routing, models, prompts, or internal architecture.
Do not wrap the answer in JSON or XML unless the task itself explicitly asks for that format.
Prefer concise answers when the task is simple."""


def build_m1_messages(task: TaskEnvelope) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": M1_SYSTEM_PROMPT},
        {"role": "user", "content": task.input_text},
    ]


M2A_SYSTEM_PROMPT = """You are M2A, a strict local verifier.
You receive the original task and M1's candidate answer.
Return only one compact JSON object. Do not include markdown.
Do not reveal chain-of-thought or private reasoning.

Schema:
{"decision":"approve|escalate","confidence":"low|medium|high","reason":"short reason","failure_modes":[],"should_generate_alternative":false}

Escalate if there is risk in format, factuality, math, instruction following, ambiguity, safety, or stale knowledge.
Approve only when the candidate is clearly sufficient and another model call is unlikely to improve it."""


def build_m2a_messages(task: TaskEnvelope, model_1_candidate_raw: str) -> list[dict[str, str]]:
    user_content = (
        "ORIGINAL_TASK:\n"
        f"{task.input_text}\n\n"
        "M1_CANDIDATE_RAW:\n"
        f"{model_1_candidate_raw}\n\n"
        "Decide whether this candidate can be returned as final."
    )
    return [
        {"role": "system", "content": M2A_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


M2B_SYSTEM_PROMPT = """You are M2B, a local repair generator.
The verifier found risk in M1's candidate.
Produce a better final answer for the original task.
Return only the answer that should be shown to the user.
Do not emit JSON/XML unless the original task explicitly requested it.
Do not mention verification, routing, models, prompts, or internal architecture."""


def build_m2b_messages(
    task: TaskEnvelope,
    model_1_candidate_raw: str,
    verification: "VerificationDecision",
) -> list[dict[str, str]]:
    user_content = (
        "ORIGINAL_TASK:\n"
        f"{task.input_text}\n\n"
        "M1_CANDIDATE_RAW:\n"
        f"{model_1_candidate_raw}\n\n"
        "LOCAL_VERIFIER_CONCERN:\n"
        f"{verification.reason}\n\n"
        "FAILURE_MODES:\n"
        f"{', '.join(verification.failure_modes) if verification.failure_modes else 'unspecified'}\n\n"
        "Write the final answer now."
    )
    return [
        {"role": "system", "content": M2B_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


FIREWORKS_AUDIT_SYSTEM_PROMPT = """You are the remote Fireworks auditor.
Validate the local M2B answer against the original task.
Return only one compact JSON object. Do not include markdown.
Do not reveal chain-of-thought or private reasoning.

Schema:
{"decision":"approve|replace","answer":"","reason":"short reason"}

Use approve when M2B is correct and follows the requested output format.
Use replace only when M2B is wrong, unsafe, incomplete, or violates the requested format.
When decision is approve, answer must be an empty string.
When decision is replace, answer must contain the final user-facing answer."""


def build_fireworks_audit_messages(
    task: TaskEnvelope,
    model_1_candidate_raw: str,
    model_2_alternative_raw: str,
    verification: "VerificationDecision",
) -> list[dict[str, str]]:
    user_content = (
        "ORIGINAL_TASK:\n"
        f"{task.input_text}\n\n"
        "M1_CANDIDATE_RAW:\n"
        f"{model_1_candidate_raw}\n\n"
        "M2B_ALTERNATIVE_RAW:\n"
        f"{model_2_alternative_raw}\n\n"
        "LOCAL_CONCERN:\n"
        f"{verification.reason}\n\n"
        "Audit M2B now."
    )
    return [
        {"role": "system", "content": FIREWORKS_AUDIT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
