from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import threading
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


PLAN_SCHEMA_VERSION = "e2b-regression-v2-plan-v1"
GENERATED_SCHEMA_VERSION = "e2b-regression-v2-generated-v1"
INPUT_SCHEMA_VERSION = "e2b-regression-v2-input-v1"
REFERENCE_SCHEMA_VERSION = "e2b-regression-v2-reference-v1"
METADATA_SCHEMA_VERSION = "e2b-regression-v2-metadata-v1"
MANIFEST_SCHEMA_VERSION = "e2b-regression-v2-corpus-manifest-v1"
SEED = 55059

CATEGORIES = (
    "factual_qa",
    "math_reasoning",
    "sentiment",
    "summarization",
    "ner",
    "code_debugging",
    "logic_puzzle",
    "code_generation",
)
SPLIT_LINEAGES_PER_CATEGORY = {"train": 75, "validation": 25, "final_holdout": 25}
PROVIDERS = ("agy", "fireworks")
ANSWER_MODES = ("exact", "semantic", "json", "executable_code")
OUTPUT_SHAPES = ("short_text", "free_text", "number", "label", "json", "code")
MUTATION_KINDS = ("paraphrase", "strict_format", "long_context", "prompt_injection", "typo")
FORBIDDEN_PROMPT_MARKERS = (
    "functiongemma",
    "fireworks ai",
    "gemma e2b",
    "route this",
    "routing score",
    "difficulty score",
)


class DatasetProvider(Protocol):
    def invoke(self, *, prompt: str, response_schema: Mapping[str, Any], role: str) -> ProviderInvocation:
        ...


@dataclass(frozen=True)
class E2BV2Paths:
    root: Path

    @property
    def plan(self) -> Path:
        return self.root / "plan.jsonl"

    @property
    def generated(self) -> Path:
        return self.root / "raw" / "generated-candidates.jsonl"

    @property
    def provider_responses(self) -> Path:
        return self.root / "raw" / "provider-responses.jsonl"

    @property
    def failures(self) -> Path:
        return self.root / "state" / "failures.jsonl"

    @property
    def checkpoint(self) -> Path:
        return self.root / "state" / "checkpoint.json"

    @property
    def metadata(self) -> Path:
        return self.root / "metadata.jsonl"

    @property
    def lineage_map(self) -> Path:
        return self.root / "lineage-map.jsonl"

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    def inputs(self, split: str) -> Path:
        return self.root / "inputs" / f"{split}.jsonl"

    def references(self, split: str) -> Path:
        directory = "sealed" if split == "final_holdout" else "references"
        return self.root / directory / f"{split}.jsonl"


@dataclass(frozen=True)
class E2BV2Target:
    target_id: str
    task_id: str
    category: str
    split: str
    provider: str
    template_family: str
    mutation_lineage: str
    semantic_seed: str
    pair_index: int
    parent_target_id: str | None
    language: str
    mutation_kind: str
    boundary_case: bool
    output_contract_variant: bool
    evidence_mode: str
    requested_answer_mode: str
    requested_output_shape: str
    schema_version: str = PLAN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "E2BV2Target":
        required = set(cls.__dataclass_fields__)
        if set(payload) != required:
            raise ValueError("E2B V2 target fields are invalid.")
        target = cls(**{name: payload[name] for name in required})
        target.validate()
        return target

    def validate(self) -> None:
        if self.schema_version != PLAN_SCHEMA_VERSION:
            raise ValueError("E2B V2 target schema is invalid.")
        if self.category not in CATEGORIES or self.split not in SPLIT_LINEAGES_PER_CATEGORY:
            raise ValueError("E2B V2 target category or split is invalid.")
        if self.provider not in PROVIDERS or self.pair_index not in {0, 1}:
            raise ValueError("E2B V2 target provider or pair index is invalid.")
        if self.requested_answer_mode not in ANSWER_MODES or self.requested_output_shape not in OUTPUT_SHAPES:
            raise ValueError("E2B V2 target answer contract is invalid.")
        if self.evidence_mode not in {"mechanical", "grounded", "semantic"}:
            raise ValueError("E2B V2 evidence mode is invalid.")
        for name in (
            "target_id",
            "task_id",
            "template_family",
            "mutation_lineage",
            "semantic_seed",
            "language",
            "mutation_kind",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"E2B V2 target {name} is invalid.")


@dataclass(frozen=True)
class GenerationWork:
    index: int
    provider: str
    targets: tuple[E2BV2Target, ...]


@dataclass(frozen=True)
class GenerationResult:
    work: GenerationWork
    invocation: ProviderInvocation | None
    error: str = ""
    quota_exhausted: bool = False


def build_targets(*, seed: int = SEED) -> list[E2BV2Target]:
    targets: list[E2BV2Target] = []
    global_lineage = 0
    global_task = 0
    for category_index, category in enumerate(CATEGORIES):
        category_lineage = 0
        for split, lineage_count in SPLIT_LINEAGES_PER_CATEGORY.items():
            for _ in range(lineage_count):
                provider = PROVIDERS[global_lineage % len(PROVIDERS)]
                lineage = f"e2b-v2-{split}-{category}-lineage-{category_lineage:03d}"
                template = f"e2b-v2-{split}-{category}-template-{category_lineage:03d}"
                semantic_seed = hashlib.sha256(f"{seed}:{lineage}".encode()).hexdigest()[:20]
                first_target_id: str | None = None
                for pair_index in (0, 1):
                    target_id = stable_id("e2b-v2-target", str(seed), category, split, str(category_lineage), str(pair_index))
                    contract = _contract(category, category_lineage, pair_index)
                    target = E2BV2Target(
                        target_id=target_id,
                        task_id=f"e2b_v2_{category}_{global_task:04d}",
                        category=category,
                        split=split,
                        provider=provider,
                        template_family=template,
                        mutation_lineage=lineage,
                        semantic_seed=semantic_seed,
                        pair_index=pair_index,
                        parent_target_id=first_target_id if pair_index else None,
                        language=_language(global_task),
                        mutation_kind="canonical" if pair_index == 0 else MUTATION_KINDS[global_lineage % len(MUTATION_KINDS)],
                        boundary_case=global_task % 4 == 0,
                        output_contract_variant=global_task % 5 == 0,
                        evidence_mode=_evidence_mode(category, category_lineage),
                        requested_answer_mode=contract[0],
                        requested_output_shape=contract[1],
                    )
                    target.validate()
                    targets.append(target)
                    first_target_id = first_target_id or target_id
                    global_task += 1
                category_lineage += 1
                global_lineage += 1
        if category_lineage != 125:
            raise AssertionError(f"Unexpected lineage count for {category_index}.")
    _validate_target_population(targets)
    return targets


def target_summary(targets: Sequence[E2BV2Target]) -> dict[str, Any]:
    return {
        "rows": len(targets),
        "lineages": len({target.mutation_lineage for target in targets}),
        "categories": dict(sorted(Counter(target.category for target in targets).items())),
        "splits": dict(sorted(Counter(target.split for target in targets).items())),
        "providers": dict(sorted(Counter(target.provider for target in targets).items())),
        "languages": dict(sorted(Counter(target.language for target in targets).items())),
        "mutations": dict(sorted(Counter(target.mutation_kind for target in targets).items())),
        "evidence_modes": dict(sorted(Counter(target.evidence_mode for target in targets).items())),
        "boundary_cases": sum(target.boundary_case for target in targets),
        "output_contract_variants": sum(target.output_contract_variant for target in targets),
    }


def write_plan(paths: E2BV2Paths, targets: Sequence[E2BV2Target]) -> None:
    encoded = "".join(_json_line(target.to_dict()) for target in targets)
    if paths.plan.exists() and paths.plan.read_text(encoding="utf-8") != encoded:
        raise ValueError("Existing E2B V2 plan differs from the frozen target plan.")
    _atomic_text(paths.plan, encoded)


def generation_response_schema(item_count: int) -> dict[str, Any]:
    item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "target_id",
            "prompt",
            "reference_answer",
            "reference_rubric",
            "ambiguity",
            "template_family",
            "mutation_lineage",
            "semantic_seed",
            "parent_target_id",
        ],
        "properties": {
            "target_id": {"type": "string"},
            "prompt": {"type": "string"},
            "reference_answer": {"type": "string"},
            "reference_rubric": {"type": "string"},
            "ambiguity": {"type": "boolean"},
            "template_family": {"type": "string"},
            "mutation_lineage": {"type": "string"},
            "semantic_seed": {"type": "string"},
            "parent_target_id": {"type": ["string", "null"]},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "minItems": item_count,
                "maxItems": item_count,
                "items": item,
            }
        },
    }


def generation_prompt(targets: Sequence[E2BV2Target]) -> str:
    visible = [target.to_dict() for target in targets]
    return f"""Create exactly {len(targets)} self-contained benchmark tasks and reference answers.

Copy target_id, template_family, mutation_lineage, semantic_seed and parent_target_id exactly. Return each target_id once and only once.
The prompt is the complete text shown to an answer model. Never mention E2B, FunctionGemma, Fireworks, routing, difficulty scores, or this generation request inside it.
The reference_answer must satisfy the prompt. The reference_rubric must briefly state how an independent judge can verify semantic correctness without hidden chain-of-thought.
Set ambiguity=false and make the task objectively judgeable. Do not use current, private, unpublished, inaccessible, or real-time facts.
For semantic tasks, define enough source text or explicit criteria to support reliable independent judgment.
For grounded tasks, include all necessary source material in the prompt.
For mechanical tasks, use bounded deterministic behavior and no unsafe execution requirements.
If output_contract_variant=true, include an explicit output-format constraint.
If boundary_case=true, create a legitimate edge case without making the reference ambiguous.
For pair_index=1, create a meaningful mutation of the same structural family, not a duplicate.
Honor requested_answer_mode, requested_output_shape, language and mutation_kind.

Category guidance:
{json.dumps(_category_guidance(), ensure_ascii=False, sort_keys=True)}

Targets:
{json.dumps(visible, ensure_ascii=False, sort_keys=True)}
"""


def generate(
    *,
    targets: Sequence[E2BV2Target],
    providers: Mapping[str, DatasetProvider],
    paths: E2BV2Paths,
    batch_size: int,
    max_workers: int,
    fireworks_budget_usd: float,
    max_batches: int | None = None,
    force_target_ids: set[str] | None = None,
) -> dict[str, Any]:
    if set(providers) != set(PROVIDERS):
        raise ValueError("E2B V2 generation requires exactly agy and fireworks providers.")
    if batch_size < 2 or batch_size % 2 or max_workers < 1:
        raise ValueError("E2B V2 batch size must be positive and even; workers must be positive.")
    checkpoint_store = AtomicCheckpoint(paths.checkpoint)
    checkpoint = checkpoint_store.load()
    completed = set(str(value) for value in checkpoint.get("completed_target_ids") or [])
    forced = force_target_ids or set()
    unknown_forced = forced - {target.target_id for target in targets}
    if unknown_forced:
        raise ValueError(f"Unknown forced E2B V2 target IDs: {sorted(unknown_forced)}")
    works = _build_work(
        [target for target in targets if target.target_id not in completed or target.target_id in forced], batch_size
    )
    if max_batches is not None:
        works = works[:max_batches]
    ledger = BudgetLedger(
        fireworks_budget_usd,
        spent_usd=float(checkpoint.get("fireworks_billable_usd") or 0.0),
    )
    candidate_store = AppendOnlyJsonl(paths.generated)
    response_store = AppendOnlyJsonl(paths.provider_responses)
    failure_store = AppendOnlyJsonl(paths.failures)
    lock = threading.Lock()
    written = 0
    paused = False
    batches_completed = int(checkpoint.get("batches_completed") or 0)

    for start in range(0, len(works), max_workers):
        wave = works[start : start + max_workers]
        with ThreadPoolExecutor(max_workers=len(wave), thread_name_prefix="e2b-v2-forge") as executor:
            futures = [executor.submit(_invoke_work, work, providers[work.provider], ledger) for work in wave]
            results = [future.result() for future in futures]
        for result in sorted(results, key=lambda row: row.work.index):
            if result.invocation is None:
                paused = paused or result.quota_exhausted
                failure_store.append_unique(
                    {
                        "id": stable_id("e2b-v2-failure", str(result.work.index), result.work.provider, result.error),
                        "batch_index": result.work.index,
                        "provider": result.work.provider,
                        "target_ids": [target.target_id for target in result.work.targets],
                        "error": result.error,
                        "retriable": True,
                        "created_at": utc_now(),
                    }
                )
                continue
            invocation = result.invocation
            response_store.append_unique(
                {
                    "id": invocation.provenance.request_id,
                    "batch_index": result.work.index,
                    "provider": result.work.provider,
                    "target_ids": [target.target_id for target in result.work.targets],
                    "payload": invocation.payload,
                    "provenance": invocation.provenance.to_dict(),
                    "created_at": utc_now(),
                }
            )
            try:
                candidates = validate_generated_batch(result.work.targets, invocation)
            except (TypeError, ValueError) as exc:
                failure_store.append_unique(
                    {
                        "id": stable_id("e2b-v2-invalid", invocation.provenance.request_id),
                        "batch_index": result.work.index,
                        "provider": result.work.provider,
                        "target_ids": [target.target_id for target in result.work.targets],
                        "error": f"invalid_provider_payload:{exc}",
                        "retriable": True,
                        "created_at": utc_now(),
                    }
                )
                continue
            for candidate in candidates:
                if candidate_store.append_unique(candidate):
                    written += 1
                completed.add(str(candidate["target_id"]))
            batches_completed += 1
            with lock:
                checkpoint_store.save(
                    {
                        **checkpoint,
                        "completed_target_ids": sorted(completed),
                        "fireworks_billable_usd": round(ledger.spent_usd, 10),
                        "batches_completed": batches_completed,
                        "updated_at": utc_now(),
                    }
                )
    return {
        "planned": len(targets),
        "completed": len(completed),
        "pending": len(targets) - len(completed),
        "written": written,
        "batches_attempted": len(works),
        "batches_completed": batches_completed,
        "paused_for_quota": paused,
        "fireworks_billable_usd": round(ledger.spent_usd, 10),
    }


def validate_generated_batch(
    targets: Sequence[E2BV2Target], invocation: ProviderInvocation
) -> list[dict[str, Any]]:
    items = invocation.payload.get("items")
    if not isinstance(items, list) or len(items) != len(targets):
        raise ValueError("Provider item count differs from target count.")
    target_index = {target.target_id: target for target in targets}
    if len(target_index) != len(targets):
        raise ValueError("Generation batch has duplicate targets.")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("Provider item must be an object.")
        expected_fields = set(generation_response_schema(1)["properties"]["items"]["items"]["required"])
        if set(item) != expected_fields:
            raise ValueError("Provider item fields are invalid.")
        target_id = _required_string(item, "target_id")
        target = target_index.get(target_id)
        if target is None or target_id in seen:
            raise ValueError("Provider returned an unknown or duplicate target ID.")
        seen.add(target_id)
        for name in ("template_family", "mutation_lineage", "semantic_seed"):
            if _required_string(item, name) != getattr(target, name):
                raise ValueError(f"Provider changed frozen {name}.")
        if item.get("parent_target_id") != target.parent_target_id:
            raise ValueError("Provider changed frozen parent_target_id.")
        if item.get("ambiguity") is not False:
            raise ValueError("Provider declared an ambiguous benchmark task.")
        if invocation.provenance.provider != target.provider:
            raise ValueError("Provider provenance differs from the frozen provider assignment.")
        prompt = _required_string(item, "prompt")
        reference = _required_string(item, "reference_answer")
        rubric = _required_string(item, "reference_rubric")
        _validate_prompt(prompt, target)
        if len(reference) > 12_000 or len(rubric) > 2_000:
            raise ValueError("Reference answer or rubric exceeds the corpus limit.")
        provenance = invocation.provenance.to_dict()
        records.append(
            {
                "id": stable_id("e2b-v2-candidate", target_id, invocation.provenance.request_id),
                "schema_version": GENERATED_SCHEMA_VERSION,
                "target_id": target_id,
                "prompt": prompt,
                "reference_answer": reference,
                "reference_rubric": rubric,
                "answer_mode": target.requested_answer_mode,
                "output_shape": target.requested_output_shape,
                "ambiguity": False,
                "template_family": target.template_family,
                "mutation_lineage": target.mutation_lineage,
                "semantic_seed": target.semantic_seed,
                "parent_target_id": target.parent_target_id,
                "provider": target.provider,
                "provenance": provenance,
                "created_at": utc_now(),
            }
        )
    if seen != set(target_index):
        raise ValueError("Provider omitted one or more target IDs.")
    return sorted(records, key=lambda row: str(row["target_id"]))


def materialize(
    *,
    targets: Sequence[E2BV2Target],
    paths: E2BV2Paths,
    config_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    target_index = {target.target_id: target for target in targets}
    candidates = AppendOnlyJsonl(paths.generated).read_all()
    selected: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        target_id = str(candidate.get("target_id") or "")
        if target_id in target_index:
            selected[target_id] = candidate
    if set(selected) != set(target_index):
        missing = sorted(set(target_index) - set(selected))
        raise ValueError(f"E2B V2 corpus is incomplete; missing {len(missing)} targets.")
    audits = _audit_selected(targets, selected)
    if not all(audits["gates"].values()):
        failed = sorted(name for name, passed in audits["gates"].items() if not passed)
        raise ValueError(f"E2B V2 corpus gates failed: {failed}")

    inputs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    references: dict[str, list[dict[str, Any]]] = defaultdict(list)
    metadata: list[dict[str, Any]] = []
    lineages: dict[str, dict[str, Any]] = {}
    for target in targets:
        candidate = selected[target.target_id]
        inputs[target.split].append(
            {
                "schema_version": INPUT_SCHEMA_VERSION,
                "task_id": target.task_id,
                "prompt": candidate["prompt"],
            }
        )
        references[target.split].append(
            {
                "schema_version": REFERENCE_SCHEMA_VERSION,
                "task_id": target.task_id,
                "reference_answer": candidate["reference_answer"],
                "reference_rubric": candidate["reference_rubric"],
                "answer_mode": target.requested_answer_mode,
                "output_shape": target.requested_output_shape,
            }
        )
        eligible_judges = [name for name in ("agy", "fireworks", "codex") if name != target.provider]
        metadata.append(
            {
                "schema_version": METADATA_SCHEMA_VERSION,
                "task_id": target.task_id,
                "target_id": target.target_id,
                "category": target.category,
                "split": target.split,
                "template_family": target.template_family,
                "mutation_lineage": target.mutation_lineage,
                "semantic_seed": target.semantic_seed,
                "pair_index": target.pair_index,
                "language": target.language,
                "mutation_kind": target.mutation_kind,
                "boundary_case": target.boundary_case,
                "output_contract_variant": target.output_contract_variant,
                "evidence_mode": target.evidence_mode,
                "generator_provider": target.provider,
                "generator_model": candidate["provenance"]["model"],
                "generator_request_id": candidate["provenance"]["request_id"],
                "eligible_judges": eligible_judges,
                "prompt_sha256": _digest_text(str(candidate["prompt"])),
                "reference_sha256": _digest_text(str(candidate["reference_answer"])),
            }
        )
        lineages.setdefault(
            target.mutation_lineage,
            {
                "id": target.mutation_lineage,
                "split": target.split,
                "category": target.category,
                "template_family": target.template_family,
                "semantic_seed": target.semantic_seed,
                "target_ids": [],
                "task_ids": [],
            },
        )
        lineages[target.mutation_lineage]["target_ids"].append(target.target_id)
        lineages[target.mutation_lineage]["task_ids"].append(target.task_id)

    for split in SPLIT_LINEAGES_PER_CATEGORY:
        _write_jsonl(paths.inputs(split), inputs[split])
        _write_jsonl(paths.references(split), references[split])
    _write_jsonl(paths.metadata, metadata)
    _write_jsonl(paths.lineage_map, [lineages[key] for key in sorted(lineages)])

    artifacts = {
        "plan": paths.plan,
        "generated_candidates": paths.generated,
        "metadata": paths.metadata,
        "lineage_map": paths.lineage_map,
    }
    for split in SPLIT_LINEAGES_PER_CATEGORY:
        artifacts[f"inputs_{split}"] = paths.inputs(split)
        artifacts[f"references_{split}"] = paths.references(split)
    provider_models = _provider_models(selected)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "seed": SEED,
        "rows": len(targets),
        "lineages": len(lineages),
        "summary": target_summary(targets),
        "audits": audits,
        "provider_models": provider_models,
        "judge_policy": {
            "available": ["agy", "fireworks", "codex"],
            "exclude_generator_provider": True,
        },
        "artifacts": {
            name: {"path": _portable_path(path), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for name, path in sorted(artifacts.items())
        },
    }
    _write_json(paths.manifest, manifest)
    config = {
        "schema_version": "e2b-regression-v2-corpus-config-v1",
        "default_enabled": False,
        "manifest": {"path": _portable_path(paths.manifest), "sha256": _sha256(paths.manifest)},
        "final_holdout_policy": "sealed_one_time_promotion_only",
        "fit_splits": ["train", "validation"],
        "promotion_split": "final_holdout",
        "provider_models": manifest["provider_models"],
    }
    _write_json(config_path, config)
    _atomic_text(report_path, render_report(manifest))
    return manifest


def verify_materialized(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "e2b-regression-v2-corpus-config-v1" or config.get("default_enabled") is not False:
        raise ValueError("E2B V2 corpus config is invalid.")
    manifest_path = _resolve_portable_path(config_path, str(config["manifest"]["path"]))
    if _sha256(manifest_path) != config["manifest"]["sha256"]:
        raise ValueError("E2B V2 manifest hash mismatch.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("E2B V2 manifest schema mismatch.")
    for name, artifact in manifest["artifacts"].items():
        path = _resolve_portable_path(manifest_path, str(artifact["path"]))
        if _sha256(path) != artifact["sha256"] or path.stat().st_size != artifact["bytes"]:
            raise ValueError(f"E2B V2 artifact mismatch: {name}")
    if not all(manifest["audits"]["gates"].values()):
        raise ValueError("E2B V2 manifest contains a failed gate.")
    return {
        "passed": True,
        "rows": manifest["rows"],
        "lineages": manifest["lineages"],
        "artifacts": len(manifest["artifacts"]),
    }


def render_report(manifest: Mapping[str, Any]) -> str:
    summary = manifest["summary"]
    audits = manifest["audits"]
    lines = [
        "# E2B Regression V2 Corpus",
        "",
        f"- rows: `{manifest['rows']}`",
        f"- lineages: `{manifest['lineages']}`",
        f"- providers: `{json.dumps(summary['providers'], sort_keys=True)}`",
        f"- splits: `{json.dumps(summary['splits'], sort_keys=True)}`",
        f"- boundary cases: `{summary['boundary_cases']}`",
        f"- output-contract variants: `{summary['output_contract_variants']}`",
        f"- exact duplicate prompts: `{audits['exact_duplicate_prompts']}`",
        f"- near-duplicate cross-lineage pairs: `{audits['near_duplicate_cross_lineage_pairs']}`",
        f"- quarantined prompts: `{audits['quarantined_prompts']}`",
        "",
        "## Gates",
        "",
    ]
    lines.extend(f"- [{'x' if passed else ' '}] `{name}`" for name, passed in audits["gates"].items())
    lines.append("")
    return "\n".join(lines)


def _build_work(targets: Sequence[E2BV2Target], batch_size: int) -> list[GenerationWork]:
    completed_lineages: dict[str, list[E2BV2Target]] = defaultdict(list)
    for target in targets:
        completed_lineages[target.mutation_lineage].append(target)
    by_provider: dict[str, list[E2BV2Target]] = {provider: [] for provider in PROVIDERS}
    for lineage in sorted(completed_lineages):
        rows = sorted(completed_lineages[lineage], key=lambda target: target.pair_index)
        if len(rows) not in {1, 2}:
            raise ValueError("A pending lineage must contain one or two targets.")
        by_provider[rows[0].provider].extend(rows)
    works: list[GenerationWork] = []
    provider_works: dict[str, list[GenerationWork]] = {provider: [] for provider in PROVIDERS}
    for provider in PROVIDERS:
        rows = by_provider[provider]
        for start in range(0, len(rows), batch_size):
            provider_works[provider].append(
                GenerationWork(index=0, provider=provider, targets=tuple(rows[start : start + batch_size]))
            )
    for batch_index in range(max(len(rows) for rows in provider_works.values())):
        for provider in PROVIDERS:
            if batch_index < len(provider_works[provider]):
                work = provider_works[provider][batch_index]
                works.append(GenerationWork(index=len(works), provider=provider, targets=work.targets))
    return works


def _invoke_work(work: GenerationWork, provider: DatasetProvider, ledger: BudgetLedger) -> GenerationResult:
    prompt = generation_prompt(work.targets)
    estimate = 0.0
    if isinstance(provider, FireworksDatasetProvider):
        estimate = provider.estimate_upper_bound_usd(prompt)
        try:
            ledger.reserve(estimate)
        except ProviderBudgetExceeded as exc:
            return GenerationResult(work=work, invocation=None, error=str(exc), quota_exhausted=True)
    try:
        invocation = provider.invoke(
            prompt=prompt,
            response_schema=generation_response_schema(len(work.targets)),
            role="e2b_v2_generator",
        )
        if estimate:
            ledger.reconcile(estimate, invocation.provenance.billable_cost_usd)
        return GenerationResult(work=work, invocation=invocation)
    except ProviderQuotaExhausted as exc:
        if estimate:
            ledger.release(estimate)
        return GenerationResult(work=work, invocation=None, error=str(exc), quota_exhausted=True)
    except (ProviderError, ProviderBudgetExceeded) as exc:
        if estimate:
            ledger.release(estimate)
        return GenerationResult(work=work, invocation=None, error=str(exc), quota_exhausted=False)


def _audit_selected(
    targets: Sequence[E2BV2Target], selected: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    target_index = {target.target_id: target for target in targets}
    prompt_hashes: dict[str, list[str]] = defaultdict(list)
    token_sets: dict[str, set[str]] = {}
    quarantined: list[str] = []
    for target_id, candidate in selected.items():
        prompt = str(candidate["prompt"])
        prompt_hashes[_digest_text(_normalize(prompt))].append(target_id)
        token_sets[target_id] = set(_normalize(prompt).split())
        try:
            _validate_prompt(prompt, target_index[target_id])
        except ValueError:
            quarantined.append(target_id)
    exact_duplicates = sum(len(ids) - 1 for ids in prompt_hashes.values() if len(ids) > 1)
    near_pairs = 0
    target_ids = sorted(selected)
    buckets: dict[str, list[str]] = defaultdict(list)
    for target_id in target_ids:
        target = target_index[target_id]
        buckets[target.category].append(target_id)
    for ids in buckets.values():
        for left_index, left in enumerate(ids):
            for right in ids[left_index + 1 :]:
                if target_index[left].mutation_lineage == target_index[right].mutation_lineage:
                    continue
                union = token_sets[left] | token_sets[right]
                similarity = len(token_sets[left] & token_sets[right]) / len(union) if union else 1.0
                near_pairs += int(similarity >= 0.96)
    split_lineages: dict[str, set[str]] = defaultdict(set)
    split_templates: dict[str, set[str]] = defaultdict(set)
    split_seeds: dict[str, set[str]] = defaultdict(set)
    for target in targets:
        split_lineages[target.split].add(target.mutation_lineage)
        split_templates[target.split].add(target.template_family)
        split_seeds[target.split].add(target.semantic_seed)
    overlap = False
    splits = tuple(SPLIT_LINEAGES_PER_CATEGORY)
    for index, left in enumerate(splits):
        for right in splits[index + 1 :]:
            overlap = overlap or bool(split_lineages[left] & split_lineages[right])
            overlap = overlap or bool(split_templates[left] & split_templates[right])
            overlap = overlap or bool(split_seeds[left] & split_seeds[right])
    summary = target_summary(targets)
    eligible_judges = {
        target.target_id: tuple(name for name in ("agy", "fireworks", "codex") if name != target.provider)
        for target in targets
    }
    gates = {
        "exact_population": len(targets) == 2000 and all(value == 250 for value in summary["categories"].values()),
        "exact_split_counts": summary["splits"] == {"final_holdout": 400, "train": 1200, "validation": 400},
        "provider_balance": summary["providers"] == {"agy": 1000, "fireworks": 1000},
        "minimum_boundary_coverage": summary["boundary_cases"] >= 500,
        "minimum_output_contract_coverage": summary["output_contract_variants"] >= 400,
        "lineage_template_seed_disjoint": not overlap,
        "no_exact_duplicate_prompts": exact_duplicates == 0,
        "no_near_duplicate_cross_lineage_pairs": near_pairs == 0,
        "no_quarantined_prompts": not quarantined,
        "generator_excluded_from_eligible_judges": all(
            target.provider not in eligible_judges[target.target_id]
            and len(eligible_judges[target.target_id]) == 2
            for target in targets
        ),
        "minimum_development_lineages": all(
            len(
                {
                    target.mutation_lineage
                    for target in targets
                    if target.category == category and target.split in {"train", "validation"}
                }
            )
            >= 100
            for category in CATEGORIES
        ),
    }
    return {
        "gates": gates,
        "exact_duplicate_prompts": exact_duplicates,
        "near_duplicate_cross_lineage_pairs": near_pairs,
        "quarantined_prompts": len(quarantined),
    }


def _validate_target_population(targets: Sequence[E2BV2Target]) -> None:
    summary = target_summary(targets)
    if len(targets) != 2000 or summary["lineages"] != 1000:
        raise AssertionError("E2B V2 target population is incomplete.")
    if summary["categories"] != {category: 250 for category in CATEGORIES}:
        raise AssertionError("E2B V2 categories are unbalanced.")
    if summary["splits"] != {"final_holdout": 400, "train": 1200, "validation": 400}:
        raise AssertionError("E2B V2 splits are unbalanced.")
    if summary["providers"] != {"agy": 1000, "fireworks": 1000}:
        raise AssertionError("E2B V2 providers are unbalanced.")
    by_lineage: dict[str, list[E2BV2Target]] = defaultdict(list)
    for target in targets:
        by_lineage[target.mutation_lineage].append(target)
    if any(len(rows) != 2 or len({row.split for row in rows}) != 1 for rows in by_lineage.values()):
        raise AssertionError("E2B V2 lineage pairing is invalid.")


def _validate_prompt(prompt: str, target: E2BV2Target) -> None:
    if not 20 <= len(prompt) <= 16_000:
        raise ValueError("Generated prompt length is outside the corpus limit.")
    lowered = prompt.casefold()
    if any(marker in lowered for marker in FORBIDDEN_PROMPT_MARKERS):
        raise ValueError("Generated prompt leaks orchestration metadata.")
    current_markers = ("current private", "unpublished", "right now", "today's price", "latest private")
    if target.category == "factual_qa" and any(marker in lowered for marker in current_markers):
        raise ValueError("Generated factual prompt requires unavailable current/private knowledge.")
    if target.output_contract_variant and not re.search(
        r"\b(return|respond|output|format|write|provide|answer|must|json|code|sentence|label|number|"
        r"responda|retorne|escreva|formato|sa[ií]da|deve|frase|r[oó]tulo|n[uú]mero|"
        r"devuelve|responde|escribe|salida|formato|debe|frase|etiqueta|n[uú]mero)\b",
        lowered,
    ):
        raise ValueError("Output-contract target lacks an explicit response instruction.")


def _contract(category: str, lineage_index: int, pair_index: int) -> tuple[str, str]:
    if category == "math_reasoning":
        return "exact", "number"
    if category == "sentiment":
        return "exact", "label"
    if category == "ner":
        return "json", "json"
    if category in {"code_debugging", "code_generation"}:
        return "executable_code", "code"
    if category == "logic_puzzle":
        return "exact", "short_text"
    if category == "summarization":
        return ("exact", "free_text") if (lineage_index + pair_index) % 3 == 0 else ("semantic", "free_text")
    if category == "factual_qa":
        return "exact", "short_text"
    raise ValueError(f"Unsupported category: {category}")


def _evidence_mode(category: str, lineage_index: int) -> str:
    if category in {"math_reasoning", "logic_puzzle", "code_debugging", "code_generation"}:
        return "mechanical"
    if category in {"ner", "factual_qa"}:
        return "grounded" if lineage_index % 4 else "semantic"
    if category == "sentiment":
        return "grounded" if lineage_index % 3 else "semantic"
    if category == "summarization":
        return "grounded" if lineage_index % 3 == 0 else "semantic"
    return "semantic"


def _language(index: int) -> str:
    remainder = index % 10
    return "en" if remainder < 8 else "pt-BR" if remainder == 8 else "es"


def _category_guidance() -> dict[str, str]:
    return {
        "factual_qa": "Use stable facts or prompt-contained context. Never require browsing or private/current information.",
        "math_reasoning": "Use bounded arithmetic or word problems with one objectively verifiable result.",
        "sentiment": "Include explicit, mixed and boundary sentiment while preserving a defensible reference label or rubric.",
        "summarization": "Include the complete source passage and define exact or semantic summary requirements.",
        "ner": "Include source text and request a fully specified JSON entity schema.",
        "code_debugging": "Use self-contained Python with a bounded behavioral contract and corrected reference code.",
        "logic_puzzle": "Use self-contained constraints with one unique answer.",
        "code_generation": "Request bounded Python functions with executable reference behavior and no external packages.",
    }


def _required_string(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _provider_models(selected: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    models: dict[str, set[str]] = defaultdict(set)
    for row in selected.values():
        provider = str(row.get("provider") or "")
        provenance = row.get("provenance")
        if not provider or not isinstance(provenance, Mapping):
            raise ValueError("Generated candidate provenance is invalid.")
        model = provenance.get("model")
        if not isinstance(model, str) or not model:
            raise ValueError("Generated candidate model provenance is invalid.")
        models[provider].add(model)
    inconsistent = sorted(provider for provider, names in models.items() if len(names) != 1)
    if inconsistent:
        raise ValueError(f"Provider model changed during corpus generation: {inconsistent}")
    return {provider: next(iter(names)) for provider, names in sorted(models.items())}


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(resolved)


def _resolve_portable_path(anchor: Path, encoded: str) -> Path:
    path = Path(encoded)
    if path.is_absolute():
        return path
    candidates = (Path.cwd() / path, anchor.resolve().parent / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def _json_line(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    _atomic_text(path, "".join(_json_line(row) for row in rows))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
