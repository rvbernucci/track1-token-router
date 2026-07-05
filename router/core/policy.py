from __future__ import annotations

from router.core.contracts import TaskEnvelope, TokenUsage


POLICIES = ("aggressive", "balanced", "conservative")
DEFAULT_POLICY = "balanced"

POLICY_GUIDANCE = {
    "aggressive": (
        "Policy: aggressive. Prefer approving local answers when they are plausibly correct. "
        "Escalate only for clear mathematical, factual, safety, stale-knowledge, or format risk."
    ),
    "balanced": (
        "Policy: balanced. Approve simple, well-formatted answers. Escalate multi-step math, "
        "strict uncertainty, stale knowledge, adversarial prompts, and any format mismatch."
    ),
    "conservative": (
        "Policy: conservative. Escalate whenever correctness is uncertain, the task is multi-step, "
        "the prompt is adversarial, or the answer may need stronger validation."
    ),
}


def normalize_policy(policy: str | None) -> str:
    normalized = (policy or DEFAULT_POLICY).strip().lower()
    if normalized not in POLICIES:
        raise ValueError(f"Unsupported ROUTER_POLICY: {policy}. Expected one of: {', '.join(POLICIES)}")
    return normalized


def policy_guidance(policy: str | None) -> str:
    return POLICY_GUIDANCE[normalize_policy(policy)]


def simulate_policy_route(task: TaskEnvelope, policy: str | None) -> str:
    normalized = normalize_policy(policy)
    category = str(task.metadata.get("category") or "unknown")
    difficulty = str(task.metadata.get("difficulty") or "unknown")
    risk = str(task.metadata.get("risk") or "unknown")

    if normalized == "aggressive":
        return _aggressive_route(category, difficulty, risk)
    if normalized == "balanced":
        return _balanced_route(category, difficulty, risk)
    return _conservative_route(category, difficulty, risk)


def simulated_remote_tokens(route: str) -> TokenUsage:
    if route == "fireworks_replaced":
        return TokenUsage(prompt=240, completion=40, total=280)
    return TokenUsage.empty()


def _aggressive_route(category: str, _difficulty: str, _risk: str) -> str:
    if category in {"dificil", "matematica", "conhecimento_instavel"}:
        return "m2b_candidate"
    return "m1_approved"


def _balanced_route(category: str, _difficulty: str, _risk: str) -> str:
    if category in {"facil", "media", "formato", "instrucao"}:
        return "m1_approved"
    if category == "conhecimento_instavel":
        return "fireworks_replaced"
    return "m2b_candidate"


def _conservative_route(category: str, _difficulty: str, _risk: str) -> str:
    if category in {"facil", "formato", "instrucao"}:
        return "m1_approved"
    if category == "media":
        return "m2b_candidate"
    return "fireworks_replaced"
