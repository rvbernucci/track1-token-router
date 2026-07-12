from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping, Protocol, Sequence

from router.dataset_forge.contracts import ProviderProvenance, stable_id, utc_now
from router.dataset_forge.pipeline import BudgetLedger
from router.dataset_forge.providers import (
    FireworksDatasetProvider,
    ProviderBudgetExceeded,
    ProviderError,
    ProviderInvocation,
    ProviderQuotaExhausted,
)
from router.dataset_forge.storage import AppendOnlyJsonl, AtomicCheckpoint
from router.orchestration.assessment import approximate_token_count


SCHEMA_VERSION = "e2b-expansion-plan-v1"
GENERATED_SCHEMA_VERSION = "e2b-expansion-generated-v1"
SEED = 70070
CATEGORIES = (
    "factual_qa", "math_reasoning", "sentiment", "summarization", "ner",
    "code_debugging", "logic_puzzle", "code_generation",
)
DIFFICULTIES = ("easy", "moderate", "hard")
SPLIT_COUNTS = {"train": 60, "calibration": 20, "final_holdout": 20}
PROVIDERS = ("agy", "fireworks")


class DatasetProvider(Protocol):
    def invoke(self, *, prompt: str, response_schema: Mapping[str, Any], role: str) -> ProviderInvocation:
        ...


@dataclass(frozen=True)
class ExpansionPaths:
    root: Path

    @property
    def plan(self) -> Path:
        return self.root / "plan.jsonl"

    @property
    def generated(self) -> Path:
        return self.root / "raw" / "generated-candidates.jsonl"

    @property
    def responses(self) -> Path:
        return self.root / "raw" / "provider-responses.jsonl"

    @property
    def failures(self) -> Path:
        return self.root / "state" / "failures.jsonl"

    @property
    def checkpoint(self) -> Path:
        return self.root / "state" / "checkpoint.json"

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def metadata(self) -> Path:
        return self.root / "metadata.jsonl"

    def tasks(self, split: str) -> Path:
        directory = self.root / ("sealed/tasks" if split == "final_holdout" else "splits")
        return directory / f"{split}.jsonl"

    def references(self, split: str) -> Path:
        directory = self.root / ("sealed/references" if split == "final_holdout" else "references")
        return directory / f"{split}.jsonl"


@dataclass(frozen=True)
class ExpansionTarget:
    target_id: str
    task_id: str
    category: str
    difficulty: str
    split: str
    provider: str
    template_family: str
    mutation_lineage: str
    semantic_seed: str
    language: str
    requested_output_shape: str
    evidence_mode: str
    difficulty_contract: str
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("Expansion target schema is invalid.")
        if self.category not in CATEGORIES or self.difficulty not in DIFFICULTIES:
            raise ValueError("Expansion category or difficulty is invalid.")
        if self.split not in SPLIT_COUNTS or self.provider not in PROVIDERS:
            raise ValueError("Expansion split or provider is invalid.")
        if not all(isinstance(value, str) and value for value in asdict(self).values()):
            raise ValueError("Expansion target fields must be non-empty strings.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenerationWork:
    index: int
    provider: str
    targets: tuple[ExpansionTarget, ...]


def build_targets(*, seed: int = SEED) -> list[ExpansionTarget]:
    targets: list[ExpansionTarget] = []
    index = 0
    for category in CATEGORIES:
        for difficulty in DIFFICULTIES:
            local_index = 0
            for split, count in SPLIT_COUNTS.items():
                for _ in range(count):
                    lineage = f"s70-{category}-{difficulty}-{split}-{local_index:03d}"
                    semantic_seed = hashlib.sha256(f"{seed}:{lineage}".encode()).hexdigest()[:20]
                    provider = PROVIDERS[index % len(PROVIDERS)]
                    target = ExpansionTarget(
                        target_id=stable_id("s70-target", str(seed), lineage),
                        task_id=f"s70_{category}_{difficulty}_{local_index:03d}",
                        category=category,
                        difficulty=difficulty,
                        split=split,
                        provider=provider,
                        template_family=f"s70-{category}-{difficulty}-template-{local_index:03d}",
                        mutation_lineage=lineage,
                        semantic_seed=semantic_seed,
                        language=_language(index),
                        requested_output_shape=_output_shape(category, local_index),
                        evidence_mode=_evidence_mode(category, local_index),
                        difficulty_contract=_difficulty_contract(category, difficulty),
                    )
                    target.validate()
                    targets.append(target)
                    index += 1
                    local_index += 1
    validate_plan(targets)
    return targets


def validate_plan(targets: Sequence[ExpansionTarget]) -> None:
    if len(targets) != 2400 or len({target.target_id for target in targets}) != 2400:
        raise ValueError("Expansion plan must contain 2,400 unique targets.")
    for category in CATEGORIES:
        for difficulty in DIFFICULTIES:
            cohort = [row for row in targets if row.category == category and row.difficulty == difficulty]
            if Counter(row.split for row in cohort) != SPLIT_COUNTS:
                raise ValueError(f"Expansion split imbalance for {category}/{difficulty}.")
    if Counter(row.provider for row in targets) != Counter({"agy": 1200, "fireworks": 1200}):
        raise ValueError("Expansion provider allocation is imbalanced.")
    protected = ("mutation_lineage", "template_family", "semantic_seed", "target_id")
    for field in protected:
        split_values = {
            split: {getattr(row, field) for row in targets if row.split == split}
            for split in SPLIT_COUNTS
        }
        for left_index, left in enumerate(SPLIT_COUNTS):
            for right in tuple(SPLIT_COUNTS)[left_index + 1:]:
                if split_values[left] & split_values[right]:
                    raise ValueError(f"Expansion {field} leaks across {left}/{right}.")


def summary(targets: Sequence[ExpansionTarget]) -> dict[str, Any]:
    return {
        "rows": len(targets),
        "lineages": len({row.mutation_lineage for row in targets}),
        "categories": dict(sorted(Counter(row.category for row in targets).items())),
        "difficulties": dict(sorted(Counter(row.difficulty for row in targets).items())),
        "splits": dict(sorted(Counter(row.split for row in targets).items())),
        "providers": dict(sorted(Counter(row.provider for row in targets).items())),
        "languages": dict(sorted(Counter(row.language for row in targets).items())),
        "evidence_modes": dict(sorted(Counter(row.evidence_mode for row in targets).items())),
    }


def write_plan(paths: ExpansionPaths, targets: Sequence[ExpansionTarget]) -> None:
    content = "".join(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True) + "\n" for row in targets)
    if paths.plan.exists() and paths.plan.read_text(encoding="utf-8") != content:
        raise ValueError("Existing expansion plan differs from the frozen protocol.")
    paths.plan.parent.mkdir(parents=True, exist_ok=True)
    paths.plan.write_text(content, encoding="utf-8")


def generation_schema(count: int) -> dict[str, Any]:
    required = (
        "target_id", "prompt", "reference_answer", "reference_rubric", "ambiguity",
        "template_family", "mutation_lineage", "semantic_seed",
    )
    return {
        "type": "object", "additionalProperties": False, "required": ["items"],
        "properties": {"items": {"type": "array", "minItems": count, "maxItems": count, "items": {
            "type": "object", "additionalProperties": False, "required": list(required),
            "properties": {
                "target_id": {"type": "string"}, "prompt": {"type": "string"},
                "reference_answer": {"type": "string"}, "reference_rubric": {"type": "string"},
                "ambiguity": {"type": "boolean"}, "template_family": {"type": "string"},
                "mutation_lineage": {"type": "string"}, "semantic_seed": {"type": "string"},
            },
        }}},
    }


def generation_prompt(targets: Sequence[ExpansionTarget]) -> str:
    visible = [row.to_dict() for row in targets]
    return f"""Create exactly {len(targets)} independent benchmark tasks with reference answers.

Copy target_id, template_family, mutation_lineage and semantic_seed exactly. Return each target once.
The prompt field is the complete text given to an answer model. It must never mention routing, E2B,
FunctionGemma, Fireworks, the generator, difficulty labels or benchmark construction. Set ambiguity=false.
Use only stable knowledge or source-grounded facts. Every task must be self-contained and objectively judgeable.
The reference rubric must permit correctness adjudication without private chain-of-thought.
Honor category, language, requested_output_shape, evidence_mode and difficulty_contract.
Difficulty is a construction quota only and must not appear in the generated task.
Use semantic_seed to derive distinctive names, values, source passages, premises or code constants.
Avoid textbook-default questions and never reuse the same prompt structure or content across targets.

Targets:
{json.dumps(visible, ensure_ascii=False, sort_keys=True)}
"""


def validate_generated(targets: Sequence[ExpansionTarget], invocation: ProviderInvocation) -> list[dict[str, Any]]:
    items = invocation.payload.get("items")
    if not isinstance(items, list) or len(items) != len(targets):
        raise ValueError("Expansion provider item count mismatch.")
    expected = {row.target_id: row for row in targets}
    required = set(generation_schema(1)["properties"]["items"]["items"]["required"])
    result = []
    seen = set()
    for item in items:
        if not isinstance(item, Mapping) or set(item) != required:
            raise ValueError("Expansion provider item fields are invalid.")
        target_id = _string(item, "target_id")
        target = expected.get(target_id)
        if target is None or target_id in seen:
            raise ValueError("Expansion provider returned an unknown or duplicate target.")
        seen.add(target_id)
        for field in ("template_family", "mutation_lineage", "semantic_seed"):
            if _string(item, field) != getattr(target, field):
                raise ValueError(f"Expansion provider changed frozen {field}.")
        if item.get("ambiguity") is not False or invocation.provenance.provider != target.provider:
            raise ValueError("Expansion ambiguity or provider provenance is invalid.")
        prompt = _string(item, "prompt")
        reference = _string(item, "reference_answer")
        rubric = _string(item, "reference_rubric")
        _validate_prompt(prompt)
        result.append({
            "id": stable_id("s70-candidate", target_id, invocation.provenance.request_id),
            "schema_version": GENERATED_SCHEMA_VERSION,
            "target_id": target_id,
            "prompt": prompt,
            "reference_answer": reference,
            "reference_rubric": rubric,
            "provider": target.provider,
            "provenance": invocation.provenance.to_dict(),
            "created_at": utc_now(),
        })
    if seen != set(expected):
        raise ValueError("Expansion provider omitted targets.")
    return sorted(result, key=lambda row: row["target_id"])


def generate(
    *, targets: Sequence[ExpansionTarget], providers: Mapping[str, DatasetProvider], paths: ExpansionPaths,
    batch_size: int = 10, max_workers: int = 2, fireworks_budget_usd: float = 8.0,
    max_batches: int | None = None, provider_batch_sizes: Mapping[str, int] | None = None,
    force_target_ids: set[str] | None = None,
) -> dict[str, Any]:
    if set(providers) != set(PROVIDERS) or batch_size < 1 or max_workers < 1:
        raise ValueError("Expansion generation configuration is invalid.")
    checkpoint_store = AtomicCheckpoint(paths.checkpoint)
    checkpoint = checkpoint_store.load()
    completed = set(str(value) for value in checkpoint.get("completed_target_ids") or [])
    forced = force_target_ids or set()
    unknown = forced - {row.target_id for row in targets}
    if unknown:
        raise ValueError(f"Unknown forced expansion targets: {sorted(unknown)}")
    works = _works(
        [row for row in targets if row.target_id not in completed or row.target_id in forced], batch_size,
        provider_batch_sizes=provider_batch_sizes,
    )
    if max_batches is not None:
        works = works[:max_batches]
    ledger = BudgetLedger(fireworks_budget_usd, spent_usd=float(checkpoint.get("fireworks_billable_usd") or 0))
    candidates = AppendOnlyJsonl(paths.generated)
    responses = AppendOnlyJsonl(paths.responses)
    failures = AppendOnlyJsonl(paths.failures)
    batches_completed = int(checkpoint.get("batches_completed") or 0)
    for start in range(0, len(works), max_workers):
        wave = works[start:start + max_workers]
        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            rows = list(pool.map(lambda work: _invoke(work, providers[work.provider], ledger), wave))
        for work, invocation, error in sorted(rows, key=lambda row: row[0].index):
            if invocation is None:
                failures.append_unique({
                    "id": stable_id("s70-failure", str(work.index), error), "provider": work.provider,
                    "target_ids": [row.target_id for row in work.targets], "error": error,
                    "retriable": True, "created_at": utc_now(),
                })
                continue
            responses.append_unique({
                "id": invocation.provenance.request_id, "provider": work.provider,
                "target_ids": [row.target_id for row in work.targets], "payload": invocation.payload,
                "provenance": invocation.provenance.to_dict(), "created_at": utc_now(),
            })
            try:
                validated = validate_generated(work.targets, invocation)
            except ValueError as exc:
                failures.append_unique({
                    "id": stable_id("s70-invalid", invocation.provenance.request_id), "provider": work.provider,
                    "target_ids": [row.target_id for row in work.targets], "error": str(exc),
                    "retriable": True, "created_at": utc_now(),
                })
                continue
            for row in validated:
                candidates.append_unique(row)
                completed.add(row["target_id"])
            batches_completed += 1
            checkpoint_store.save({
                **checkpoint, "completed_target_ids": sorted(completed),
                "fireworks_billable_usd": round(ledger.spent_usd, 10),
                "batches_completed": batches_completed, "updated_at": utc_now(),
            })
    return {
        "planned": len(targets), "completed": len(completed), "pending": len(targets) - len(completed),
        "batches_attempted": len(works), "batches_completed": batches_completed,
        "fireworks_billable_usd": round(ledger.spent_usd, 10),
    }


def materialize(*, targets: Sequence[ExpansionTarget], paths: ExpansionPaths) -> dict[str, Any]:
    rows = AppendOnlyJsonl(paths.generated).read_all()
    selected = {str(row.get("target_id")): row for row in rows if row.get("target_id")}
    expected = {row.target_id: row for row in targets}
    if set(selected) != set(expected):
        raise ValueError(f"Expansion corpus is incomplete; missing {len(set(expected) - set(selected))} targets.")
    audit = _dedup_audit(targets, selected)
    if not all(audit["gates"].values()):
        failed = [name for name, passed in audit["gates"].items() if not passed]
        raise ValueError(f"Expansion deduplication gates failed: {failed}")
    tasks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    references: dict[str, list[dict[str, Any]]] = defaultdict(list)
    metadata = []
    for target in targets:
        candidate = selected[target.target_id]
        prompt = str(candidate["prompt"])
        reference = str(candidate["reference_answer"])
        tasks[target.split].append({"task_id": target.task_id, "prompt": prompt})
        references[target.split].append({
            "task_id": target.task_id, "reference_answer": reference,
            "reference_rubric": candidate["reference_rubric"],
            "evidence_mode": target.evidence_mode, "output_shape": target.requested_output_shape,
        })
        metadata.append({
            "task_id": target.task_id, "target_id": target.target_id, "category": target.category,
            "difficulty": target.difficulty, "split": target.split, "provider": target.provider,
            "provider_model": candidate["provenance"]["model"],
            "provider_request_id": candidate["provenance"]["request_id"],
            "template_family": target.template_family, "mutation_lineage": target.mutation_lineage,
            "semantic_seed": target.semantic_seed, "language": target.language,
            "output_shape": target.requested_output_shape, "evidence_mode": target.evidence_mode,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "reference_sha256": hashlib.sha256(reference.encode()).hexdigest(),
            "eligible_judges": [name for name in ("agy", "fireworks", "codex") if name != target.provider],
        })
    artifacts: dict[str, Path] = {"plan": paths.plan, "generated": paths.generated, "metadata": paths.metadata}
    _jsonl(paths.metadata, metadata)
    for split in SPLIT_COUNTS:
        _jsonl(paths.tasks(split), tasks[split])
        _jsonl(paths.references(split), references[split])
        artifacts[f"tasks_{split}"] = paths.tasks(split)
        artifacts[f"references_{split}"] = paths.references(split)
    manifest = {
        "schema_version": "e2b-expansion-manifest-v1", "seed": SEED,
        "rows": len(targets), "summary": summary(targets), "deduplication": audit,
        "holdout_policy": "sealed_one_time_promotion_only",
        "generation": {
            "provider_models": dict(sorted(Counter(
                f"{row.provider}:{selected[row.target_id]['provenance']['model']}" for row in targets
            ).items())),
            "fireworks_billable_usd": float(
                AtomicCheckpoint(paths.checkpoint).load().get("fireworks_billable_usd") or 0.0
            ),
            "credentials_embedded": False,
        },
        "fit_splits": ["train"], "calibration_split": "calibration", "promotion_split": "final_holdout",
        "artifacts": {
            name: {"path": str(path.relative_to(Path.cwd())), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for name, path in sorted(artifacts.items())
        },
    }
    paths.manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_manifest(paths: ExpansionPaths) -> dict[str, Any]:
    payload = json.loads(paths.manifest.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "e2b-expansion-manifest-v1" or payload.get("rows") != 2400:
        raise ValueError("Expansion manifest contract is invalid.")
    for name, artifact in payload["artifacts"].items():
        path = Path(artifact["path"])
        if _sha256(path) != artifact["sha256"] or path.stat().st_size != artifact["bytes"]:
            raise ValueError(f"Expansion artifact mismatch: {name}")
    if not all(payload["deduplication"]["gates"].values()):
        raise ValueError("Expansion manifest contains failed deduplication gates.")
    return {"passed": True, "rows": payload["rows"], "artifacts": len(payload["artifacts"])}


def _dedup_audit(targets: Sequence[ExpansionTarget], selected: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    historical = _historical_prompts()
    history_hashes = {_normalized_hash(prompt) for prompt in historical}
    hashes: dict[str, list[str]] = defaultdict(list)
    tokens = {}
    cross_history = []
    invalid_prompts = []
    for target in targets:
        prompt = str(selected[target.target_id]["prompt"])
        try:
            _validate_prompt(prompt)
        except ValueError:
            invalid_prompts.append(target.target_id)
        digest = _normalized_hash(prompt)
        hashes[digest].append(target.target_id)
        tokens[target.target_id] = _tokens(prompt)
        if digest in history_hashes:
            cross_history.append(target.target_id)
    exact_internal = sum(len(ids) - 1 for ids in hashes.values() if len(ids) > 1)
    retry_ids = set(cross_history)
    for ids in hashes.values():
        if len(ids) > 1:
            retry_ids.update(sorted(ids)[1:])
    # Candidate pairs only need comparison inside the same category; a lexical
    # inverted index avoids an O(N^2) full-corpus scan while finding high-overlap rows.
    near_pairs = []
    by_category: dict[str, list[ExpansionTarget]] = defaultdict(list)
    for target in targets:
        by_category[target.category].append(target)
    for cohort in by_category.values():
        index: dict[str, list[str]] = defaultdict(list)
        for target in cohort:
            rare = sorted(tokens[target.target_id], key=lambda token: (len(index[token]), token))[:8]
            candidates = {other for token in rare for other in index[token]}
            for other in candidates:
                union = tokens[target.target_id] | tokens[other]
                similarity = len(tokens[target.target_id] & tokens[other]) / len(union) if union else 1.0
                if similarity >= 0.92:
                    near_pairs.append((other, target.target_id, round(similarity, 4)))
                    retry_ids.add(max(other, target.target_id))
            for token in tokens[target.target_id]:
                index[token].append(target.target_id)
    split_lineages = {
        split: {row.mutation_lineage for row in targets if row.split == split}
        for split in SPLIT_COUNTS
    }
    leakage = any(
        split_lineages[left] & split_lineages[right]
        for index, left in enumerate(SPLIT_COUNTS)
        for right in tuple(SPLIT_COUNTS)[index + 1:]
    )
    return {
        "historical_prompts_scanned": len(historical), "normalized_cross_history": len(cross_history),
        "internal_normalized_duplicates": exact_internal, "semantic_near_duplicate_pairs": len(near_pairs),
        "invalid_prompts": len(invalid_prompts),
        "near_duplicate_sample": near_pairs[:20],
        "retry_target_ids": sorted(retry_ids),
        "gates": {
            "zero_normalized_history_overlap": not cross_history,
            "zero_internal_normalized_duplicates": exact_internal == 0,
            "zero_semantic_near_duplicates": not near_pairs,
            "zero_lineage_split_leakage": not leakage,
            "all_prompts_runtime_safe": not invalid_prompts,
        },
    }


def _historical_prompts() -> list[str]:
    paths = [
        Path("data/e2b-regression-2000/tasks.jsonl"),
        Path("evals/e2b-regression-v2/inputs/train.jsonl"),
        Path("evals/e2b-regression-v2/inputs/validation.jsonl"),
        Path("evals/e2b-regression-v2/inputs/final_holdout.jsonl"),
        Path("evals/e2b-boundary-v1/sealed/tasks.jsonl"),
    ]
    result = []
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                prompt = row.get("prompt") or row.get("input_text")
                if isinstance(prompt, str):
                    result.append(prompt)
    return result


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def _normalized_hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode()).hexdigest()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", _normalize(text), flags=re.UNICODE))


def _jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _works(
    targets: Sequence[ExpansionTarget], batch_size: int,
    *, provider_batch_sizes: Mapping[str, int] | None = None,
) -> list[GenerationWork]:
    grouped = {provider: [row for row in targets if row.provider == provider] for provider in PROVIDERS}
    sizes = {provider: int((provider_batch_sizes or {}).get(provider, batch_size)) for provider in PROVIDERS}
    if any(value < 1 for value in sizes.values()):
        raise ValueError("Expansion provider batch sizes must be positive.")
    provider_batches = {
        provider: [tuple(rows[index:index + sizes[provider]]) for index in range(0, len(rows), sizes[provider])]
        for provider, rows in grouped.items()
    }
    result = []
    for index in range(max((len(rows) for rows in provider_batches.values()), default=0)):
        for provider in PROVIDERS:
            if index < len(provider_batches[provider]):
                result.append(GenerationWork(len(result), provider, provider_batches[provider][index]))
    return result


def _invoke(work: GenerationWork, provider: DatasetProvider, ledger: BudgetLedger) -> tuple[GenerationWork, ProviderInvocation | None, str]:
    prompt = generation_prompt(work.targets)
    estimate = 0.0
    if isinstance(provider, FireworksDatasetProvider):
        estimate = provider.estimate_upper_bound_usd(prompt)
        try:
            ledger.reserve(estimate)
        except ProviderBudgetExceeded as exc:
            return work, None, str(exc)
    try:
        invocation = provider.invoke(prompt=prompt, response_schema=generation_schema(len(work.targets)), role="e2b_expansion_generator")
        if estimate:
            ledger.reconcile(estimate, invocation.provenance.billable_cost_usd)
        return work, invocation, ""
    except (ProviderError, ProviderQuotaExhausted, ProviderBudgetExceeded) as exc:
        if estimate:
            ledger.release(estimate)
        return work, None, str(exc)


def _difficulty_contract(category: str, difficulty: str) -> str:
    base = {
        "easy": "One direct operation or explicit extraction; short context; no distractors.",
        "moderate": "Two or three linked operations, relevant distractors, or a constrained transformation.",
        "hard": "Multiple dependencies, adversarial distractors, nuanced constraints, or longer grounded context.",
    }[difficulty]
    category_rule = {
        "factual_qa": "Use stable facts or facts explicitly grounded in the prompt.",
        "math_reasoning": "Provide one objectively recomputable numeric or symbolic result.",
        "sentiment": "Define a finite label set and include realistic linguistic cues.",
        "summarization": "Include all source text and an explicit summary constraint.",
        "ner": "Include all source text and define requested entity types.",
        "code_debugging": "Provide a bounded buggy function and an exact behavioral requirement.",
        "logic_puzzle": "State complete premises and require one uniquely entailed answer.",
        "code_generation": "Request a bounded function with explicit inputs, outputs and constraints.",
    }[category]
    return f"{base} {category_rule}"


def _output_shape(category: str, index: int) -> str:
    choices = {
        "factual_qa": ("short_text", "free_text"), "math_reasoning": ("number", "short_text"),
        "sentiment": ("label",), "summarization": ("free_text", "short_text"),
        "ner": ("json", "list"), "code_debugging": ("code",),
        "logic_puzzle": ("short_text", "json"), "code_generation": ("code",),
    }[category]
    return choices[index % len(choices)]


def _evidence_mode(category: str, index: int) -> str:
    if category in {"math_reasoning", "sentiment", "ner", "code_debugging", "logic_puzzle", "code_generation"}:
        return "mechanical"
    if category == "factual_qa" and index % 2:
        return "grounded"
    return "semantic"


def _language(index: int) -> str:
    # English dominates the hidden benchmark assumption; multilingual rows measure shift.
    return "en" if index % 10 < 8 else ("pt" if index % 10 == 8 else "es")


def _validate_prompt(prompt: str) -> None:
    if len(prompt.strip()) < 12 or len(prompt) > 24_000:
        raise ValueError("Expansion prompt length is invalid.")
    if approximate_token_count(prompt) > 1500:
        raise ValueError("Expansion prompt exceeds the local 2,048-token context safety margin.")
    forbidden = re.compile(r"\b(?:E2B|FunctionGemma|Fireworks|routing|difficulty label|benchmark construction)\b", re.I)
    if forbidden.search(prompt):
        raise ValueError("Expansion prompt leaks experiment metadata.")


def _string(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expansion field {name} must be a non-empty string.")
    return value
