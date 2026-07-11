from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from router.dataset_forge.contracts import ProviderProvenance
from router.dataset_forge.e2b_v2 import (
    E2BV2Paths,
    _build_work,
    build_targets,
    generation_prompt,
    generate,
    materialize,
    target_summary,
    validate_generated_batch,
    verify_materialized,
    write_plan,
)
from router.dataset_forge.providers import ProviderInvocation


def _provenance(provider: str, *, model: str | None = None, request_id: str = "request-1") -> ProviderProvenance:
    return ProviderProvenance(
        provider=provider,
        model=model or f"{provider}-pinned-model",
        role="e2b_v2_generator",
        auth_mode="test",
        usage_window="test",
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        equivalent_cost_usd=0.0,
        billable_cost_usd=0.0,
        request_id=request_id,
        config_sha256="a" * 64,
    )


def _item(target, *, prompt: str | None = None) -> dict[str, object]:
    return {
        "target_id": target.target_id,
        "prompt": prompt or f"Solve this stable task and return the result token {target.semantic_seed}.",
        "reference_answer": f"answer-{target.semantic_seed}",
        "reference_rubric": "The answer must equal the supplied stable result token.",
        "ambiguity": False,
        "template_family": target.template_family,
        "mutation_lineage": target.mutation_lineage,
        "semantic_seed": target.semantic_seed,
        "parent_target_id": target.parent_target_id,
    }


def _candidate(target) -> dict[str, object]:
    digest = hashlib.sha256(target.target_id.encode()).hexdigest()
    markers = " ".join(digest[index : index + 4] for index in range(0, 40, 4))
    instruction = "Return the exact requested output." if target.output_contract_variant else "Determine the requested output."
    invocation = ProviderInvocation(
        payload={"items": [_item(target, prompt=f"{instruction} Stable benchmark markers: {markers}.")]},
        provenance=_provenance(target.provider, request_id=f"request-{target.target_id}"),
    )
    return validate_generated_batch([target], invocation)[0]


class E2BRegressionV2CorpusTests(unittest.TestCase):
    def test_target_plan_is_balanced_deterministic_and_split_isolated(self) -> None:
        targets = build_targets()
        self.assertEqual([target.to_dict() for target in targets], [target.to_dict() for target in build_targets()])
        summary = target_summary(targets)
        self.assertEqual(summary["splits"], {"final_holdout": 400, "train": 1200, "validation": 400})
        self.assertEqual(summary["providers"], {"agy": 1000, "fireworks": 1000})
        self.assertEqual(set(summary["categories"].values()), {250})
        by_lineage = defaultdict(list)
        for target in targets:
            by_lineage[target.mutation_lineage].append(target)
        self.assertEqual(len(by_lineage), 1000)
        self.assertTrue(all(len(rows) == 2 and len({row.split for row in rows}) == 1 for rows in by_lineage.values()))
        for field in ("mutation_lineage", "template_family", "semantic_seed"):
            values = {
                split: {getattr(target, field) for target in targets if target.split == split}
                for split in ("train", "validation", "final_holdout")
            }
            self.assertFalse(values["train"] & values["validation"])
            self.assertFalse(values["train"] & values["final_holdout"])
            self.assertFalse(values["validation"] & values["final_holdout"])

    def test_work_interleaves_providers_and_prompt_excludes_references(self) -> None:
        works = _build_work(build_targets(), 10)
        self.assertEqual([work.provider for work in works[:4]], ["agy", "fireworks", "agy", "fireworks"])
        self.assertTrue(all(len(work.targets) == 10 for work in works))
        prompt = generation_prompt(works[0].targets)
        self.assertNotIn("answer-", prompt)
        self.assertNotIn("The answer must equal the supplied stable result token.", prompt)

    def test_generation_can_force_completed_targets_for_append_only_retry(self) -> None:
        target = build_targets()[0]
        with tempfile.TemporaryDirectory() as directory:
            paths = E2BV2Paths(Path(directory))
            paths.checkpoint.parent.mkdir(parents=True, exist_ok=True)
            paths.checkpoint.write_text(
                json.dumps(
                    {
                        "schema_version": "dataset-forge-checkpoint-v1",
                        "completed_target_ids": [target.target_id],
                        "fireworks_billable_usd": 0.0,
                        "batches_completed": 0,
                    }
                ),
                encoding="utf-8",
            )

            class Provider:
                def invoke(self, **_kwargs):
                    return ProviderInvocation(
                        payload={"items": [_item(target)]}, provenance=_provenance(target.provider, request_id="retry")
                    )

            other = "fireworks" if target.provider == "agy" else "agy"
            result = generate(
                targets=[target],
                providers={target.provider: Provider(), other: Provider()},
                paths=paths,
                batch_size=2,
                max_workers=1,
                fireworks_budget_usd=1.0,
                force_target_ids={target.target_id},
            )
            self.assertEqual(result["written"], 1)

    def test_batch_validation_rejects_provenance_and_frozen_metadata_changes(self) -> None:
        target = build_targets()[0]
        valid = ProviderInvocation(payload={"items": [_item(target)]}, provenance=_provenance(target.provider))
        self.assertEqual(validate_generated_batch([target], valid)[0]["target_id"], target.target_id)
        other = "fireworks" if target.provider == "agy" else "agy"
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_generated_batch(
                [target], ProviderInvocation(payload=valid.payload, provenance=_provenance(other))
            )
        changed = _item(target)
        changed["semantic_seed"] = "changed"
        with self.assertRaisesRegex(ValueError, "semantic_seed"):
            validate_generated_batch(
                [target], ProviderInvocation(payload={"items": [changed]}, provenance=_provenance(target.provider))
            )

    def test_output_contract_accepts_explicit_format_language(self) -> None:
        target = next(target for target in build_targets() if target.output_contract_variant)
        for prompt in (
            "The output must contain only one valid JSON object.",
            "A saída deve conter somente um objeto JSON válido.",
            "La salida debe contener solamente un objeto JSON válido.",
        ):
            invocation = ProviderInvocation(
                payload={"items": [_item(target, prompt=prompt)]}, provenance=_provenance(target.provider)
            )
            self.assertEqual(validate_generated_batch([target], invocation)[0]["target_id"], target.target_id)

    def test_materialization_separates_inputs_references_and_generator_judges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            os.chdir(directory)
            try:
                root = Path(directory)
                paths = E2BV2Paths(root / "evals" / "e2b-regression-v2")
                config = root / "configs" / "e2b-regression-v2-corpus.json"
                report = root / "reports" / "corpus.md"
                targets = build_targets()
                write_plan(paths, targets)
                paths.generated.parent.mkdir(parents=True, exist_ok=True)
                paths.generated.write_text(
                    "".join(json.dumps(_candidate(target), sort_keys=True) + "\n" for target in targets),
                    encoding="utf-8",
                )
                manifest = materialize(targets=targets, paths=paths, config_path=config, report_path=report)
                self.assertEqual(
                    verify_materialized(config),
                    {"passed": True, "rows": 2000, "lineages": 1000, "artifacts": 10},
                )
                self.assertTrue(manifest["judge_policy"]["exclude_generator_provider"])
                self.assertEqual(
                    manifest["provider_models"],
                    {"agy": "agy-pinned-model", "fireworks": "fireworks-pinned-model"},
                )
                expected = {"train": 1200, "validation": 400, "final_holdout": 400}
                metadata = [json.loads(line) for line in paths.metadata.read_text(encoding="utf-8").splitlines()]
                self.assertEqual(Counter(row["split"] for row in metadata), expected)
                self.assertTrue(all(row["generator_provider"] not in row["eligible_judges"] for row in metadata))
                for split, count in expected.items():
                    inputs = [json.loads(line) for line in paths.inputs(split).read_text(encoding="utf-8").splitlines()]
                    references = [
                        json.loads(line) for line in paths.references(split).read_text(encoding="utf-8").splitlines()
                    ]
                    self.assertEqual(len(inputs), count)
                    self.assertEqual(len(references), count)
                    self.assertTrue(all(set(row) == {"schema_version", "task_id", "prompt"} for row in inputs))
                    self.assertTrue(all("reference_answer" not in row for row in inputs))
                self.assertEqual(paths.references("final_holdout").parent.name, "sealed")
            finally:
                os.chdir(previous)

    def test_materialization_rejects_model_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            os.chdir(directory)
            try:
                root = Path(directory)
                paths = E2BV2Paths(root / "corpus")
                targets = build_targets()
                write_plan(paths, targets)
                candidates = [_candidate(target) for target in targets]
                candidates[2]["provenance"]["model"] = "unexpected-model"
                paths.generated.parent.mkdir(parents=True, exist_ok=True)
                paths.generated.write_text(
                    "".join(json.dumps(row) + "\n" for row in candidates), encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, "Provider model changed"):
                    materialize(
                        targets=targets,
                        paths=paths,
                        config_path=root / "config.json",
                        report_path=root / "report.md",
                    )
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
