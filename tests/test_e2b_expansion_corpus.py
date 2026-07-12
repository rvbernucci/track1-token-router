import unittest
import tempfile
from pathlib import Path
import json
from collections import Counter

from router.dataset_forge.contracts import ProviderProvenance
from router.dataset_forge.e2b_expansion import (
    ExpansionPaths, _works, build_targets, generation_prompt, materialize, summary,
    validate_generated, verify_manifest, write_plan,
)
from router.dataset_forge.providers import ProviderInvocation


class E2BExpansionCorpusTests(unittest.TestCase):
    def test_plan_is_deterministic_balanced_and_split_safe(self) -> None:
        targets = build_targets()
        self.assertEqual([row.to_dict() for row in targets], [row.to_dict() for row in build_targets()])
        counts = summary(targets)
        self.assertEqual(counts["rows"], 2400)
        self.assertEqual(set(counts["categories"].values()), {300})
        self.assertEqual(counts["difficulties"], {"easy": 800, "hard": 800, "moderate": 800})
        self.assertEqual(counts["splits"], {"calibration": 480, "final_holdout": 480, "train": 1440})
        self.assertEqual(counts["providers"], {"agy": 1200, "fireworks": 1200})
        for category in counts["categories"]:
            for difficulty in ("easy", "moderate", "hard"):
                cohort = [row for row in targets if row.category == category and row.difficulty == difficulty]
                self.assertEqual(Counter(row.split for row in cohort), {"train": 60, "calibration": 20, "final_holdout": 20})

    def test_batches_interleave_providers_and_prompt_hides_references(self) -> None:
        works = _works(build_targets()[:40], 5)
        self.assertEqual([row.provider for row in works[:4]], ["agy", "fireworks", "agy", "fireworks"])
        prompt = generation_prompt(works[0].targets)
        self.assertNotIn("reference_answer", prompt)
        self.assertIn("difficulty_contract", prompt)

    def test_provider_must_preserve_frozen_metadata(self) -> None:
        target = build_targets()[0]
        provenance = ProviderProvenance(
            provider=target.provider, model="test", role="e2b_expansion_generator", auth_mode="test",
            usage_window="test", prompt_tokens=1, completion_tokens=1, total_tokens=2,
            equivalent_cost_usd=0, billable_cost_usd=0, request_id="request", config_sha256="a" * 64,
        )
        item = {
            "target_id": target.target_id, "prompt": "Return only the stable answer for this self-contained task.",
            "reference_answer": "answer", "reference_rubric": "The answer must equal answer.",
            "ambiguity": False, "template_family": target.template_family,
            "mutation_lineage": target.mutation_lineage, "semantic_seed": target.semantic_seed,
        }
        valid = ProviderInvocation(payload={"items": [item]}, provenance=provenance)
        self.assertEqual(validate_generated([target], valid)[0]["target_id"], target.target_id)
        item["semantic_seed"] = "changed"
        with self.assertRaisesRegex(ValueError, "semantic_seed"):
            validate_generated([target], ProviderInvocation(payload={"items": [item]}, provenance=provenance))

    def test_materialization_requires_complete_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = ExpansionPaths(Path(directory))
            targets = build_targets()
            write_plan(paths, targets)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                materialize(targets=targets, paths=paths)


if __name__ == "__main__":
    unittest.main()
