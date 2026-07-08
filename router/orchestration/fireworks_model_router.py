from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from router.core.contracts import TaskEnvelope


DOMAIN_CORRELATION_MATRIX: dict[str, dict[str, float]] = {
    "classification": {
        "classification": 1.00,
        "formatting": 0.65,
        "general": 0.55,
        "summarization": 0.25,
    },
    "formatting": {
        "formatting": 1.00,
        "classification": 0.65,
        "general": 0.55,
        "summarization": 0.25,
    },
    "summarization": {
        "summarization": 1.00,
        "extraction": 0.70,
        "general": 0.60,
        "reasoning": 0.35,
    },
    "extraction": {
        "extraction": 1.00,
        "summarization": 0.70,
        "formatting": 0.55,
        "general": 0.50,
    },
    "logic": {
        "logic": 1.00,
        "math_reasoning": 0.85,
        "reasoning": 0.85,
        "agentic": 0.55,
        "general": 0.35,
    },
    "math_reasoning": {
        "math_reasoning": 1.00,
        "logic": 0.85,
        "reasoning": 0.85,
        "agentic": 0.45,
        "general": 0.30,
    },
    "code_debug": {
        "code_debug": 1.00,
        "code_generation": 0.85,
        "agentic": 0.75,
        "logic": 0.55,
        "reasoning": 0.45,
        "general": 0.25,
    },
    "code_generation": {
        "code_generation": 1.00,
        "code_debug": 0.85,
        "agentic": 0.75,
        "logic": 0.45,
        "reasoning": 0.45,
        "general": 0.25,
    },
    "current_factual": {
        "current_factual": 1.00,
        "general": 0.45,
        "reasoning": 0.35,
        "summarization": 0.25,
    },
    "general": {
        "general": 1.00,
        "summarization": 0.55,
        "reasoning": 0.45,
        "classification": 0.35,
        "formatting": 0.35,
    },
}

TIER_GAME_WEIGHTS: dict[str, dict[str, float]] = {
    "cheap": {"cost": 0.65, "quality": 0.25, "latency": 0.10},
    "medium": {"cost": 0.50, "quality": 0.35, "latency": 0.15},
    "strong": {"cost": 0.40, "quality": 0.50, "latency": 0.10},
}

FIREWORKS_MODEL_ALIASES: dict[str, str] = {
    "minimax-m3": "accounts/fireworks/models/minimax-m3",
    "kimi-k2p7-code": "accounts/fireworks/models/kimi-k2p7-code",
    "gemma-4-31b-it": "accounts/fireworks/models/gemma-4-31b-it",
    "gemma-4-26b-a4b-it": "accounts/fireworks/models/gemma-4-26b-a4b-it",
    "gemma-4-31b-it-nvfp4": "accounts/fireworks/models/gemma-4-31b-it-nvfp4",
}


@dataclass(frozen=True)
class FireworksModelProfile:
    input_price_per_mtok: float
    output_price_per_mtok: float
    latency_ms: int
    simple_total_tokens: int
    strengths: frozenset[str]
    reliability: float = 1.0
    service_path: str = "standard"
    kind: str = "chat"
    supports_chat: bool = True


@dataclass(frozen=True)
class FireworksCandidate:
    model: str
    estimated_cost_usd: float
    latency_ms: int
    capability: int
    reliability: float
    service_path: str
    kind: str
    supports_chat: bool
    correlation: float = 0.0
    quality_utility: float = 0.0
    cost_utility: float = 0.0
    latency_utility: float = 0.0
    nash_product: float = 0.0
    prisoner_payoff: float = 0.0
    game_label: str = "unscored"
    dominated: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FireworksModelSelection:
    model: str
    tier: str
    domain: str
    service_path: str
    reason: str
    ranked_models: list[str]
    pareto_frontier: list[str]
    estimated_cost_usd: float
    game_theory: dict[str, object]
    candidates: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def select_fireworks_model(
    task: TaskEnvelope,
    allowed_models: list[str],
    *,
    default_model: str | None = None,
) -> FireworksModelSelection:
    ranked = rank_fireworks_models(allowed_models or ([default_model] if default_model else []))
    if not ranked:
        raise ValueError("No Fireworks model available. Set ALLOWED_MODELS or FIREWORKS_MODEL.")
    task_profile = _task_profile(task.input_text)
    candidates = _build_candidates(ranked, task_profile)
    chat_candidates = [candidate for candidate in candidates if candidate.supports_chat]
    if not chat_candidates:
        raise ValueError("No chat-capable Fireworks model available in ALLOWED_MODELS.")
    eligible = [
        candidate
        for candidate in chat_candidates
        if candidate.capability >= task_profile.required_capability
    ]
    pool = [candidate for candidate in eligible if not candidate.dominated] or eligible or chat_candidates
    selected = max(pool, key=_nash_selection_score)
    pareto_frontier = [
        candidate.model
        for candidate in chat_candidates
        if not candidate.dominated
    ]
    return FireworksModelSelection(
        model=selected.model,
        tier=task_profile.tier,
        domain=task_profile.domain,
        service_path=selected.service_path,
        reason=task_profile.reason,
        ranked_models=ranked,
        pareto_frontier=pareto_frontier,
        estimated_cost_usd=selected.estimated_cost_usd,
        game_theory=_game_theory_summary(selected, pool, task_profile),
        candidates=[candidate.to_dict() for candidate in candidates],
    )


def rank_fireworks_models(models: list[str]) -> list[str]:
    unique = []
    seen = set()
    for model in models:
        clean = normalize_fireworks_model_id(model)
        if clean and clean not in seen:
            unique.append(clean)
            seen.add(clean)
    return sorted(unique, key=_model_cost_score)


def normalize_fireworks_model_id(model: str | None) -> str:
    if not model:
        return ""
    clean = model.strip()
    if clean.startswith("accounts/"):
        return clean
    return FIREWORKS_MODEL_ALIASES.get(clean, clean)


def select_reasoning_effort(model: str, tier: str) -> str | None:
    """Choose the cheapest safe reasoning setting observed in Fireworks smoke tests."""
    lowered = model.lower()
    if "gpt-oss" in lowered:
        return "low"
    if "gemma" in lowered:
        return None
    if tier in {"cheap", "medium"}:
        return "none"
    return None


@dataclass(frozen=True)
class _TaskProfile:
    tier: str
    domain: str
    reason: str
    required_capability: int
    expected_input_tokens: int
    expected_output_tokens: int


def _task_profile(prompt: str) -> _TaskProfile:
    tier, reason = _task_tier(prompt)
    domain = _task_domain(prompt)
    if tier == "cheap":
        return _TaskProfile(tier, domain, reason, 1, 80, 8)
    if tier == "medium":
        return _TaskProfile(tier, domain, reason, 2, 180, 80)
    if domain in {"code_generation", "code_debug", "logic", "math_reasoning"}:
        return _TaskProfile(tier, domain, reason, 4, 260, 180)
    return _TaskProfile(tier, domain, reason, 3, 260, 180)


def _task_tier(prompt: str) -> tuple[str, str]:
    lowered = prompt.lower()
    if _has_any(lowered, ["debug", "bug", "traceback", "fix the code", "write a function", "define a function", "implement", "code generation"]):
        return "strong", "code_task_requires_stronger_model"
    if _looks_like_syllogism(lowered):
        return "strong", "deductive_reasoning_requires_stronger_model"
    if _has_any(lowered, ["logical", "deductive", "constraint", "puzzle", "all conditions", "prove"]):
        return "strong", "deductive_reasoning_requires_stronger_model"
    if _has_any(lowered, ["multi-step", "word problem", "projection", "percentage", "percent", "rate", "average", "reasoning"]):
        return "strong", "multi_step_reasoning_requires_stronger_model"
    if _has_any(lowered, ["current", "latest", "today", "now", "price", "ceo", "version"]):
        return "strong", "time_sensitive_factuality_requires_stronger_model"
    if _has_any(lowered, ["summaris", "summariz", "named entity", "extract", "entity", "entities", "factual", "explain", "definition"]):
        return "medium", "language_extraction_or_factual_task"
    if _has_any(lowered, ["sentiment", "classify", "label", "positive", "negative", "neutral"]):
        return "cheap", "classification_task_can_start_on_cheapest_model"
    if _has_any(lowered, ["return only", "return exactly", "exactly this string", "nothing else", "json", "uppercase", "lowercase", "format"]):
        return "cheap", "format_constrained_task_can_start_on_cheapest_model"
    return "medium", "general_language_task_uses_middle_model"


def _task_domain(prompt: str) -> str:
    lowered = prompt.lower()
    if _has_any(lowered, ["debug", "bug", "traceback", "fix the code"]):
        return "code_debug"
    if _has_any(lowered, ["write a function", "define a function", "implement", "code generation"]):
        return "code_generation"
    if _looks_like_syllogism(lowered):
        return "logic"
    if _has_any(lowered, ["logical", "deductive", "constraint", "puzzle", "prove"]):
        return "logic"
    if _has_any(lowered, ["multi-step", "word problem", "percentage", "percent", "rate", "average", "reasoning"]):
        return "math_reasoning"
    if _has_any(lowered, ["current", "latest", "today", "now", "price", "ceo", "version"]):
        return "current_factual"
    if _has_any(lowered, ["summaris", "summariz"]):
        return "summarization"
    if _has_any(lowered, ["named entity", "extract", "entity", "entities"]):
        return "extraction"
    if _has_any(lowered, ["sentiment", "classify", "label", "positive", "negative", "neutral"]):
        return "classification"
    if _has_any(lowered, ["return only", "return exactly", "exactly this string", "nothing else", "json", "uppercase", "lowercase", "format"]):
        return "formatting"
    return "general"


def _looks_like_syllogism(lowered_prompt: str) -> bool:
    return "all " in lowered_prompt and " no " in f" {lowered_prompt} " and "can " in lowered_prompt


def _model_cost_score(model: str) -> tuple[float, str]:
    lowered = model.lower()
    profile = _known_profile(lowered)
    if profile:
        return profile.input_price_per_mtok + profile.output_price_per_mtok, lowered
    explicit = _extract_parameter_billions(lowered)
    if explicit is not None:
        return explicit, lowered
    keyword_scores = [
        ("nano", 1.0),
        ("tiny", 1.5),
        ("mini", 2.0),
        ("lite", 2.5),
        ("small", 3.0),
        ("medium", 20.0),
        ("large", 70.0),
        ("xl", 120.0),
    ]
    for keyword, score in keyword_scores:
        if keyword in lowered:
            return score, lowered
    return 40.0, lowered


def _extract_parameter_billions(model: str) -> float | None:
    match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*b(?:\b|-|_)", model)
    if match:
        return float(match.group(1))
    return None


def _has_any(value: str, needles: list[str]) -> bool:
    return any(needle in value for needle in needles)


def _build_candidates(models: list[str], task: _TaskProfile) -> list[FireworksCandidate]:
    raw = [
        _candidate_for_model(model, task)
        for model in models
    ]
    scored = []
    for candidate in raw:
        dominated = (not candidate.supports_chat) or _is_dominated(candidate, raw)
        metrics = _game_metrics(candidate, raw, task)
        scored.append(FireworksCandidate(
            model=candidate.model,
            estimated_cost_usd=candidate.estimated_cost_usd,
            latency_ms=candidate.latency_ms,
            capability=candidate.capability,
            reliability=candidate.reliability,
            service_path=candidate.service_path,
            kind=candidate.kind,
            supports_chat=candidate.supports_chat,
            correlation=candidate.correlation,
            quality_utility=metrics["quality_utility"],
            cost_utility=metrics["cost_utility"],
            latency_utility=metrics["latency_utility"],
            nash_product=metrics["nash_product"],
            prisoner_payoff=metrics["prisoner_payoff"],
            game_label=_game_label(candidate, raw, task, dominated, metrics),
            dominated=dominated,
        ))
    return scored


def _candidate_for_model(model: str, task: _TaskProfile) -> FireworksCandidate:
    profile = _profile_for_model(model)
    output_tokens = _expected_output_tokens(model, task, profile)
    estimated_cost_usd = (
        (task.expected_input_tokens * profile.input_price_per_mtok)
        + (output_tokens * profile.output_price_per_mtok)
    ) / 1_000_000
    return FireworksCandidate(
        model=model,
        estimated_cost_usd=estimated_cost_usd,
        latency_ms=profile.latency_ms,
        capability=_capability_for_domain(profile, task.domain),
        reliability=profile.reliability,
        service_path=profile.service_path,
        kind=profile.kind,
        supports_chat=profile.supports_chat,
        correlation=_domain_correlation(profile, task.domain),
        dominated=False,
    )


def _expected_output_tokens(model: str, task: _TaskProfile, profile: FireworksModelProfile) -> int:
    if task.tier == "cheap":
        if select_reasoning_effort(model, task.tier) in {"none", "low"}:
            return min(task.expected_output_tokens, max(2, profile.simple_total_tokens // 5))
        return profile.simple_total_tokens
    return task.expected_output_tokens


def _is_dominated(candidate: FireworksCandidate, candidates: list[FireworksCandidate]) -> bool:
    for other in candidates:
        if other.model == candidate.model:
            continue
        if not other.supports_chat:
            continue
        if (
            other.estimated_cost_usd <= candidate.estimated_cost_usd
            and other.latency_ms <= candidate.latency_ms
            and other.capability >= candidate.capability
            and other.reliability >= candidate.reliability
            and (
                other.estimated_cost_usd < candidate.estimated_cost_usd
                or other.latency_ms < candidate.latency_ms
                or other.capability > candidate.capability
                or other.reliability > candidate.reliability
            )
        ):
            return True
    return False


def _game_metrics(
    candidate: FireworksCandidate,
    candidates: list[FireworksCandidate],
    task: _TaskProfile,
) -> dict[str, float]:
    chat_candidates = [item for item in candidates if item.supports_chat] or candidates
    costs = [item.estimated_cost_usd for item in chat_candidates]
    latencies = [float(item.latency_ms) for item in chat_candidates]
    cost_utility = _inverse_range(candidate.estimated_cost_usd, min(costs), max(costs))
    latency_utility = _inverse_range(float(candidate.latency_ms), min(latencies), max(latencies))
    quality_utility = _quality_utility(candidate, task)
    weights = TIER_GAME_WEIGHTS.get(task.tier, TIER_GAME_WEIGHTS["medium"])
    nash_product = (
        (cost_utility ** weights["cost"])
        * (quality_utility ** weights["quality"])
        * (latency_utility ** weights["latency"])
    )
    prisoner_payoff = _prisoner_payoff(candidate, candidates, task, cost_utility, latency_utility, quality_utility)
    return {
        "quality_utility": quality_utility,
        "cost_utility": cost_utility,
        "latency_utility": latency_utility,
        "nash_product": nash_product,
        "prisoner_payoff": prisoner_payoff,
    }


def _quality_utility(candidate: FireworksCandidate, task: _TaskProfile) -> float:
    if not candidate.supports_chat:
        return 0.01
    capability_ratio = _clamp(candidate.capability / max(task.required_capability, 1), 0.0, 1.0)
    return _clamp(
        (0.50 * capability_ratio)
        + (0.30 * candidate.correlation)
        + (0.20 * candidate.reliability),
        0.01,
        1.0,
    )


def _prisoner_payoff(
    candidate: FireworksCandidate,
    candidates: list[FireworksCandidate],
    task: _TaskProfile,
    cost_utility: float,
    latency_utility: float,
    quality_utility: float,
) -> float:
    eligible = [
        item
        for item in candidates
        if item.supports_chat and item.capability >= task.required_capability
    ]
    min_eligible_cost = min((item.estimated_cost_usd for item in eligible), default=candidate.estimated_cost_usd)
    cost_ratio = candidate.estimated_cost_usd / max(min_eligible_cost, 0.000000001)
    over_escalation_penalty = max(0.0, cost_ratio - 1.0) * 0.05
    unsafe_penalty = 0.40 if candidate.capability < task.required_capability else 0.0
    non_chat_penalty = 0.90 if not candidate.supports_chat else 0.0
    payoff = (
        (0.50 * quality_utility)
        + (0.40 * cost_utility)
        + (0.10 * latency_utility)
        - over_escalation_penalty
        - unsafe_penalty
        - non_chat_penalty
    )
    return _clamp(payoff, -1.0, 1.0)


def _game_label(
    candidate: FireworksCandidate,
    candidates: list[FireworksCandidate],
    task: _TaskProfile,
    dominated: bool,
    metrics: dict[str, float],
) -> str:
    if not candidate.supports_chat:
        return "non_chat_auxiliary_strategy"
    if candidate.capability < task.required_capability:
        return "defect_unsafe_underqualified"
    if dominated:
        return "dominated_strategy"
    eligible = [
        item
        for item in candidates
        if item.supports_chat and item.capability >= task.required_capability
    ]
    min_eligible_cost = min((item.estimated_cost_usd for item in eligible), default=candidate.estimated_cost_usd)
    cost_ratio = candidate.estimated_cost_usd / max(min_eligible_cost, 0.000000001)
    best_quality = max((_quality_utility(item, task) for item in eligible), default=metrics["quality_utility"])
    if cost_ratio > 2.5 and metrics["quality_utility"] <= best_quality + 0.02:
        return "defect_expensive_overescalation"
    if cost_ratio <= 1.20 and metrics["quality_utility"] >= 0.75:
        return "cooperate_token_efficient"
    return "cooperate_quality_safe"


def _game_theory_summary(
    selected: FireworksCandidate,
    pool: list[FireworksCandidate],
    task: _TaskProfile,
) -> dict[str, object]:
    return {
        "selection_rule": "pareto_filtered_nash_welfare",
        "equilibrium_model": selected.model,
        "equilibrium_type": "pure_strategy_nash_equilibrium",
        "players": ["accuracy_player", "token_budget_player", "latency_tiebreaker"],
        "tier_weights": TIER_GAME_WEIGHTS.get(task.tier, TIER_GAME_WEIGHTS["medium"]),
        "selected_nash_product": selected.nash_product,
        "selected_prisoner_payoff": selected.prisoner_payoff,
        "selected_correlation": selected.correlation,
        "eligible_pool_size": len(pool),
        "dilemma": (
            "avoid_expensive_overescalation_and_unsafe_underqualification"
        ),
    }


def _domain_correlation(profile: FireworksModelProfile, domain: str) -> float:
    if not profile.supports_chat:
        return 0.0
    row = DOMAIN_CORRELATION_MATRIX.get(domain, DOMAIN_CORRELATION_MATRIX["general"])
    return max((row.get(strength, 0.0) for strength in profile.strengths), default=0.0)


def _inverse_range(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 1.0
    scaled = 1.0 - ((value - minimum) / (maximum - minimum))
    return _clamp(0.10 + (0.90 * scaled), 0.10, 1.0)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _nash_selection_score(candidate: FireworksCandidate) -> tuple[float, float, float, int, str]:
    return (
        candidate.nash_product,
        candidate.prisoner_payoff,
        -candidate.estimated_cost_usd,
        -candidate.latency_ms,
        candidate.model,
    )


def _profile_for_model(model: str) -> FireworksModelProfile:
    lowered = model.lower()
    known = _known_profile(lowered)
    if known:
        return known
    explicit = _extract_parameter_billions(lowered)
    if explicit is None:
        return FireworksModelProfile(
            input_price_per_mtok=0.90,
            output_price_per_mtok=0.90,
            latency_ms=2000,
            simple_total_tokens=24,
            strengths=frozenset({"general"}),
            reliability=0.92,
        )
    if explicit < 4:
        price = 0.10
        strengths = frozenset({"classification", "formatting"})
        reliability = 0.88
    elif explicit <= 16:
        price = 0.20
        strengths = frozenset({"general", "classification", "formatting", "summarization"})
        reliability = 0.90
    else:
        price = 0.90
        strengths = frozenset({"general", "summarization", "logic", "math_reasoning", "code_generation", "code_debug"})
        reliability = 0.92
    return FireworksModelProfile(
        input_price_per_mtok=price,
        output_price_per_mtok=price,
        latency_ms=2200,
        simple_total_tokens=24,
        strengths=strengths,
        reliability=reliability,
    )


def _known_profile(lowered_model: str) -> FireworksModelProfile | None:
    known = [
        (
            "gemma-4-31b-it-nvfp4",
            FireworksModelProfile(
                input_price_per_mtok=0.20,
                output_price_per_mtok=0.50,
                latency_ms=850,
                simple_total_tokens=18,
                strengths=frozenset(
                    {
                        "general",
                        "classification",
                        "formatting",
                        "summarization",
                        "extraction",
                    }
                ),
                reliability=0.92,
            ),
        ),
        (
            "gemma-4-26b-a4b-it",
            FireworksModelProfile(
                input_price_per_mtok=0.20,
                output_price_per_mtok=0.50,
                latency_ms=950,
                simple_total_tokens=20,
                strengths=frozenset(
                    {
                        "general",
                        "classification",
                        "formatting",
                        "summarization",
                        "extraction",
                    }
                ),
                reliability=0.91,
            ),
        ),
        (
            "gemma-4-31b-it",
            FireworksModelProfile(
                input_price_per_mtok=0.24,
                output_price_per_mtok=0.60,
                latency_ms=1050,
                simple_total_tokens=22,
                strengths=frozenset(
                    {
                        "general",
                        "classification",
                        "formatting",
                        "summarization",
                        "extraction",
                    }
                ),
                reliability=0.93,
            ),
        ),
        (
            "qwen3-embedding-8b",
            FireworksModelProfile(
                input_price_per_mtok=0.10,
                output_price_per_mtok=0.0,
                latency_ms=450,
                simple_total_tokens=0,
                strengths=frozenset({"embedding"}),
                reliability=0.99,
                kind="embedding",
                supports_chat=False,
            ),
        ),
        (
            "qwen3-reranker-8b",
            FireworksModelProfile(
                input_price_per_mtok=0.20,
                output_price_per_mtok=0.0,
                latency_ms=450,
                simple_total_tokens=0,
                strengths=frozenset({"reranker"}),
                reliability=0.99,
                kind="reranker",
                supports_chat=False,
            ),
        ),
        (
            "kimi-k2p7-code-fast",
            FireworksModelProfile(
                input_price_per_mtok=1.90,
                output_price_per_mtok=8.00,
                latency_ms=500,
                simple_total_tokens=18,
                strengths=frozenset({"general", "code_generation", "code_debug", "logic", "agentic"}),
                reliability=0.95,
                service_path="fast",
            ),
        ),
        (
            "kimi-k2p6-fast",
            FireworksModelProfile(
                input_price_per_mtok=2.00,
                output_price_per_mtok=8.00,
                latency_ms=500,
                simple_total_tokens=18,
                strengths=frozenset({"general", "code_generation", "code_debug", "logic", "agentic"}),
                reliability=0.95,
                service_path="fast",
            ),
        ),
        (
            "glm-5p2-fast",
            FireworksModelProfile(
                input_price_per_mtok=2.10,
                output_price_per_mtok=6.60,
                latency_ms=650,
                simple_total_tokens=15,
                strengths=frozenset({"general", "classification", "formatting", "summarization", "logic"}),
                reliability=0.94,
                service_path="fast",
            ),
        ),
        (
            "glm-5p1-fast",
            FireworksModelProfile(
                input_price_per_mtok=2.80,
                output_price_per_mtok=8.80,
                latency_ms=650,
                simple_total_tokens=14,
                strengths=frozenset({"general", "classification", "formatting", "summarization", "logic"}),
                reliability=0.94,
                service_path="fast",
            ),
        ),
        (
            "gpt-oss-20b",
            FireworksModelProfile(
                input_price_per_mtok=0.07,
                output_price_per_mtok=0.30,
                latency_ms=900,
                simple_total_tokens=24,
                strengths=frozenset({"general", "classification", "formatting"}),
                reliability=0.93,
            ),
        ),
        (
            "deepseek-v4-flash",
            FireworksModelProfile(
                input_price_per_mtok=0.14,
                output_price_per_mtok=0.28,
                latency_ms=900,
                simple_total_tokens=16,
                strengths=frozenset(
                    {
                        "general",
                        "classification",
                        "formatting",
                        "summarization",
                        "logic",
                        "math_reasoning",
                    }
                ),
                reliability=0.93,
            ),
        ),
        (
            "gpt-oss-120b",
            FireworksModelProfile(
                input_price_per_mtok=0.15,
                output_price_per_mtok=0.60,
                latency_ms=1025,
                simple_total_tokens=102,
                strengths=frozenset(
                    {
                        "general",
                        "classification",
                        "formatting",
                        "summarization",
                        "logic",
                        "math_reasoning",
                    }
                ),
                reliability=0.94,
            ),
        ),
        (
            "minimax-m3",
            FireworksModelProfile(
                input_price_per_mtok=0.30,
                output_price_per_mtok=1.20,
                latency_ms=1200,
                simple_total_tokens=24,
                strengths=frozenset(
                    {
                        "general",
                        "summarization",
                        "reasoning",
                        "code_generation",
                        "code_debug",
                        "logic",
                        "math_reasoning",
                        "agentic",
                    }
                ),
                reliability=0.95,
            ),
        ),
        (
            "minimax-m2p7",
            FireworksModelProfile(
                input_price_per_mtok=0.30,
                output_price_per_mtok=1.20,
                latency_ms=1300,
                simple_total_tokens=24,
                strengths=frozenset(
                    {
                        "general",
                        "summarization",
                        "reasoning",
                        "code_generation",
                        "agentic",
                    }
                ),
                reliability=0.94,
            ),
        ),
        (
            "minimax-m",
            FireworksModelProfile(
                input_price_per_mtok=0.30,
                output_price_per_mtok=1.20,
                latency_ms=1300,
                simple_total_tokens=24,
                strengths=frozenset({"general", "summarization", "reasoning"}),
                reliability=0.94,
            ),
        ),
        (
            "qwen3p7-plus",
            FireworksModelProfile(
                input_price_per_mtok=0.40,
                output_price_per_mtok=1.60,
                latency_ms=1500,
                simple_total_tokens=24,
                strengths=frozenset({"general", "code_generation", "math_reasoning"}),
                reliability=0.94,
            ),
        ),
        (
            "kimi-k2p7-code",
            FireworksModelProfile(
                input_price_per_mtok=0.95,
                output_price_per_mtok=4.00,
                latency_ms=760,
                simple_total_tokens=14,
                strengths=frozenset({"general", "code_generation", "code_debug", "logic", "agentic"}),
                reliability=0.97,
            ),
        ),
        (
            "kimi-k2p6",
            FireworksModelProfile(
                input_price_per_mtok=0.95,
                output_price_per_mtok=4.00,
                latency_ms=868,
                simple_total_tokens=18,
                strengths=frozenset({"general", "code_generation", "code_debug", "logic", "agentic"}),
                reliability=0.95,
            ),
        ),
        (
            "kimi-k2p5",
            FireworksModelProfile(
                input_price_per_mtok=0.95,
                output_price_per_mtok=4.00,
                latency_ms=1200,
                simple_total_tokens=18,
                strengths=frozenset({"general", "code_generation", "code_debug", "logic", "agentic"}),
                reliability=0.82,
            ),
        ),
        (
            "nemotron-3-ultra-nvfp4",
            FireworksModelProfile(
                input_price_per_mtok=0.60,
                output_price_per_mtok=2.40,
                latency_ms=1400,
                simple_total_tokens=24,
                strengths=frozenset(
                    {
                        "general",
                        "logic",
                        "math_reasoning",
                        "code_generation",
                        "code_debug",
                        "agentic",
                    }
                ),
                reliability=0.95,
            ),
        ),
        (
            "glm-5p1",
            FireworksModelProfile(
                input_price_per_mtok=1.40,
                output_price_per_mtok=4.40,
                latency_ms=1333,
                simple_total_tokens=14,
                strengths=frozenset({"general", "classification", "formatting", "summarization", "logic"}),
                reliability=0.94,
            ),
        ),
        (
            "glm-5p2",
            FireworksModelProfile(
                input_price_per_mtok=1.40,
                output_price_per_mtok=4.40,
                latency_ms=1512,
                simple_total_tokens=15,
                strengths=frozenset({"general", "classification", "formatting", "summarization", "logic"}),
                reliability=0.94,
            ),
        ),
        (
            "deepseek-v4-pro",
            FireworksModelProfile(
                input_price_per_mtok=1.74,
                output_price_per_mtok=3.48,
                latency_ms=4198,
                simple_total_tokens=13,
                strengths=frozenset({"general", "code_generation", "code_debug", "logic", "math_reasoning"}),
                reliability=0.96,
            ),
        ),
    ]
    for marker, profile in known:
        if marker in lowered_model:
            return profile
    return None


def _capability_for_domain(profile: FireworksModelProfile, domain: str) -> int:
    if not profile.supports_chat:
        return 0
    if domain in profile.strengths:
        return 4
    if domain in {"classification", "formatting"} and "general" in profile.strengths:
        return 2
    if domain in {"summarization", "extraction", "current_factual"} and "general" in profile.strengths:
        return 2
    if domain in {"logic", "math_reasoning"} and "reasoning" in profile.strengths:
        return 3
    if domain.startswith("code") and "agentic" in profile.strengths:
        return 3
    if "general" in profile.strengths:
        return 2
    return 1
