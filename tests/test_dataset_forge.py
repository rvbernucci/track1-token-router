import contextlib
from dataclasses import replace
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from router.core.contracts import AssessmentScores, Intent, TaskAssessment
from router.dataset_forge.adjudication import adjudicate
from router.dataset_forge.cli import main as forge_main
from router.dataset_forge.contracts import (
    AssessmentRating,
    DatasetProposal,
    GoldAssessment,
    ProviderProvenance,
    content_sha256,
    rationales_from_mapping,
    stable_id,
    utc_now,
)
from router.dataset_forge.dedup import deduplicate
from router.dataset_forge.metrics import agreement_metrics, build_report, weighted_quadratic_kappa
from router.dataset_forge.hidden_seed import import_hidden_seed
from router.dataset_forge.pipeline import (
    BudgetLedger,
    ForgePaths,
    deduplicate_validated,
    generate,
    rate,
    rate_target_contract,
    validate,
)
from router.dataset_forge.planner import build_generation_targets, target_summary
from router.dataset_forge.providers import (
    AGY_MODEL,
    AntigravityProvider,
    ClaudeCodeProvider,
    ProviderBudgetExceeded,
    ProviderError,
    ProviderInvocation,
)
from router.dataset_forge.split import build_splits
from router.dataset_forge.storage import AppendOnlyJsonl, AtomicCheckpoint
from router.orchestration.solvers import SOLVERS


RATIONALES = {
    "deterministic_fit": "The task structure determines the mechanical fit.",
    "reasoning_demand": "The task requires the stated number of dependent steps.",
    "knowledge_uncertainty": "The needed information has the stated availability.",
    "generation_demand": "The requested response has the stated output length.",
    "format_complexity": "The output contract has the stated strictness.",
}


class ScriptedProvider:
    def __init__(self, name: str, model: str, *, inject_field: bool = False) -> None:
        self.name = name
        self.model = model
        self.inject_field = inject_field
        self.calls = 0

    def invoke(self, *, prompt, response_schema, role):
        self.calls += 1
        if role == "generator":
            targets = json.loads(prompt.split("Targets:\n", 1)[1])
            items = [self._generation_item(target) for target in targets]
            if self.inject_field:
                items[0]["engine"] = "fireworks"
        else:
            tasks = json.loads(prompt.split("Tasks:\n", 1)[1])
            items = [
                {
                    "example_id": task["example_id"],
                    "assessment": factual_assessment().to_dict(),
                    "rationales": RATIONALES,
                }
                for task in tasks
            ]
        return ProviderInvocation(
            payload={"items": items},
            provenance=provenance(self.name, self.model, role, request_id=f"{self.name}-{self.calls}"),
        )

    def _generation_item(self, target):
        scores = {name: 5 for name in RATIONALES}
        scores[target["boundary_dimension"]] = target["boundary_anchor"]
        return {
            "target_id": target["target_id"],
            "task_text": f"Synthetic {target['target_id']} task in {target['language']}.",
            "assessment": {
                "intent": target["intent"],
                "sub_intent": target["sub_intent"],
                "scores": scores,
            },
            "rationales": RATIONALES,
            "template_family": f"synthetic-{target['intent']}-v1",
            "mutation_lineage": target["lineage_id"],
            "language": target["language"],
            "mutation_kind": target["mutation_kind"],
            "boundary_dimension": target["boundary_dimension"],
            "boundary_anchor": target["boundary_anchor"],
            "parent_id": target["parent_target_id"],
        }


class DatasetForgePlannerTests(unittest.TestCase):
    def test_generation_plan_is_balanced_deterministic_and_paired(self) -> None:
        first = build_generation_targets(120, seed=46)
        second = build_generation_targets(120, seed=46)
        summary = target_summary(first)

        self.assertEqual(first, second)
        self.assertEqual(summary["count"], 120)
        self.assertEqual(summary["lineages"], 60)
        self.assertEqual(set(summary["intents"]), {intent.value for intent in Intent})
        self.assertEqual(set(summary["boundary_anchors"]), {"0", "2", "5", "8", "10"})
        for index in range(0, len(first), 2):
            left, right = first[index : index + 2]
            self.assertEqual((left.intent, left.sub_intent), (right.intent, right.sub_intent))
            self.assertEqual(left.boundary_dimension, right.boundary_dimension)
            self.assertNotEqual(left.boundary_anchor, right.boundary_anchor)
            self.assertEqual(left.lineage_id, right.lineage_id)
            self.assertIsNone(left.parent_target_id)
            self.assertEqual(right.parent_target_id, left.id)
            if left.boundary_dimension == "deterministic_fit" and {left.boundary_anchor, right.boundary_anchor} & {8, 10}:
                capabilities = {capability for registration in SOLVERS for capability in registration.capabilities}
                self.assertIn((left.intent, left.sub_intent), capabilities)

    def test_plan_cli_is_network_free_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = forge_main(["--root", tmp, "plan", "--count", "12", "--providers", "claude,agy"])
            payload = json.loads(output.getvalue())

        self.assertEqual(code, 0)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["network_calls"], 0)
        self.assertFalse(Path(tmp).exists())


class DatasetForgeStorageTests(unittest.TestCase):
    def test_append_only_store_is_idempotent_and_checkpoint_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AppendOnlyJsonl(Path(tmp) / "rows.jsonl")
            self.assertTrue(store.append_unique({"id": "one", "value": 1}))
            self.assertFalse(store.append_unique({"id": "one", "value": 2}))
            checkpoint = AtomicCheckpoint(Path(tmp) / "state" / "checkpoint.json")
            payload = checkpoint.load()
            payload["completed_target_ids"] = ["one"]
            checkpoint.save(payload)

            self.assertEqual(store.read_all(), [{"id": "one", "value": 1}])
            self.assertEqual(checkpoint.load()["completed_target_ids"], ["one"])
            self.assertEqual(list((Path(tmp) / "state").glob("*.tmp")), [])

    def test_budget_ledger_reserves_reconciles_and_blocks_overspend(self) -> None:
        ledger = BudgetLedger(1.0)
        ledger.reserve(0.6)
        with self.assertRaises(ProviderBudgetExceeded):
            ledger.reserve(0.5)
        ledger.reconcile(0.6, 0.2)
        ledger.reserve(0.7)
        ledger.reconcile(0.7, 0.6)
        self.assertAlmostEqual(ledger.spent_usd, 0.8)


class DatasetForgePipelineTests(unittest.TestCase):
    def test_generation_is_resumable_and_rejects_model_controlled_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = ForgePaths(Path(tmp))
            targets = build_generation_targets(8, seed=1)
            good = ScriptedProvider("fake-a", "model-a")
            summary = generate(
                targets=targets,
                providers={"fake": good},
                paths=paths,
                batch_size=2,
                max_workers=2,
                fireworks_budget_usd=0,
            )
            calls_after_first = good.calls
            resumed = generate(
                targets=targets,
                providers={"fake": good},
                paths=paths,
                batch_size=2,
                max_workers=2,
                fireworks_budget_usd=0,
            )

            bad_paths = ForgePaths(Path(tmp) / "bad")
            bad = ScriptedProvider("fake-b", "model-b", inject_field=True)
            bad_summary = generate(
                targets=targets[:2],
                providers={"bad": bad},
                paths=bad_paths,
                batch_size=2,
                max_workers=1,
                fireworks_budget_usd=0,
            )
            bad_failure_count = len(AppendOnlyJsonl(bad_paths.failures).read_all())

        self.assertEqual(summary["completed"], 8)
        self.assertEqual(resumed["pending_at_start"], 0)
        self.assertEqual(good.calls, calls_after_first)
        self.assertEqual(bad_summary["completed"], 0)
        self.assertEqual(bad_failure_count, 1)

    def test_validate_deduplicate_rate_adjudicate_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = ForgePaths(Path(tmp))
            targets = build_generation_targets(6, seed=2)
            generator = ScriptedProvider("generator", "teacher")
            generate(
                targets=targets,
                providers={"generator": generator},
                paths=paths,
                batch_size=3,
                max_workers=1,
                fireworks_budget_usd=0,
            )
            validation = validate(paths)
            dedup_summary = deduplicate_validated(paths)
            first_rater = ScriptedProvider("rater-a", "model-a")
            second_rater = ScriptedProvider("rater-b", "model-b")
            rate(provider_name="a", provider=first_rater, paths=paths, batch_size=3, fireworks_budget_usd=0)
            rate(provider_name="b", provider=second_rater, paths=paths, batch_size=3, fireworks_budget_usd=0)
            adjudication = adjudicate(paths)
            report = build_report(paths)

        self.assertEqual(validation["invalid"], 0)
        self.assertEqual(dedup_summary["accepted"], 6)
        self.assertEqual(adjudication["accepted"], 6)
        self.assertEqual(report["gold_accepted"], 6)
        self.assertEqual(report["agreement"]["intent_exact"], 1.0)
        self.assertEqual(len(report["rater_families"]), 2)

    def test_target_contract_rating_is_offline_idempotent_and_grounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = ForgePaths(Path(tmp))
            targets = build_generation_targets(4, seed=7)
            generate(
                targets=targets,
                providers={"generator": ScriptedProvider("generator", "teacher")},
                paths=paths,
                batch_size=2,
                max_workers=1,
                fireworks_budget_usd=0,
            )
            validate(paths)
            deduplicate_validated(paths)
            first = rate_target_contract(paths)
            second = rate_target_contract(paths)
            ratings = [AssessmentRating.from_mapping(row) for row in AppendOnlyJsonl(paths.ratings).read_all()]
            proposals = {
                row["id"]: DatasetProposal.from_mapping(row)
                for row in AppendOnlyJsonl(paths.deduped_proposals).read_all()
            }
            for item in proposals.values():
                semantic_provenance = provenance(
                    "semantic",
                    "judge-v1",
                    "rater",
                    request_id=f"semantic-{item.id}",
                )
                AppendOnlyJsonl(paths.ratings).append_unique(
                    AssessmentRating(
                        id=stable_id("rating", item.id, "semantic:judge-v1"),
                        example_id=item.id,
                        rater_id="semantic:judge-v1",
                        assessment=item.assessment,
                        rationales=tuple(sorted(RATIONALES.items())),
                        provenance=semantic_provenance,
                        created_at=utc_now(),
                    ).to_dict()
                )
            adjudication = adjudicate(paths)

        self.assertEqual(first["written"], 4)
        self.assertEqual(second["written"], 0)
        self.assertEqual(len(ratings), 4)
        self.assertTrue(all(rating.provenance.total_tokens == 0 for rating in ratings))
        self.assertTrue(all(rating.assessment == proposals[rating.example_id].assessment for rating in ratings))
        self.assertEqual(adjudication["accepted"], 4)

    def test_boundary_pair_is_not_removed_as_near_duplicate(self) -> None:
        base = proposal("a", "Return only 5.", lineage="pair", anchor=2)
        boundary = proposal("b", "Return only 6.", lineage="pair", anchor=8)

        accepted, decisions = deduplicate([base, boundary])

        self.assertEqual(len(accepted), 2)
        self.assertTrue(all(decision.accepted for decision in decisions))

    def test_dedup_selects_one_canonical_proposal_per_target(self) -> None:
        first = proposal("a", "First independently generated task.")
        collision = replace(
            proposal("b", "Different content generated concurrently."),
            target_id=first.target_id,
        )

        accepted, decisions = deduplicate([collision, first])

        self.assertEqual([item.id for item in accepted], ["a"])
        rejected = next(item for item in decisions if item.example_id == "b")
        self.assertEqual(rejected.reason, "target_id_collision")
        self.assertEqual(rejected.duplicate_of, "a")

    def test_split_keeps_teacher_rows_out_of_hidden_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = ForgePaths(Path(tmp))
            proposal_store = AppendOnlyJsonl(paths.deduped_proposals)
            gold_store = AppendOnlyJsonl(paths.root / "adjudicated" / "gold.jsonl")
            teacher = proposal("teacher", "Teacher task", source="teacher:claude_code", lineage="train")
            hidden = proposal("hidden", "Reserved hidden task", source="codex_hidden_seed", lineage="hidden")
            for item in (teacher, hidden):
                proposal_store.append_unique(item.to_dict())
                gold_store.append_unique(gold(item.id).to_dict())

            manifest = build_splits(paths)
            hidden_tasks = AppendOnlyJsonl(paths.root / "splits" / "hidden_test_tasks.jsonl").read_all()

        self.assertEqual(manifest["counts"]["hidden_test"], 1)
        self.assertEqual(hidden_tasks[0]["id"], hidden.id)
        self.assertNotEqual(manifest["assignments"][teacher.id], "hidden_test")

    def test_split_components_prevent_lineage_and_template_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = ForgePaths(Path(tmp))
            proposal_store = AppendOnlyJsonl(paths.deduped_proposals)
            gold_store = AppendOnlyJsonl(paths.root / "adjudicated" / "gold.jsonl")
            lineage_a = proposal("lineage-a", "Task one", lineage="shared-lineage")
            lineage_b = proposal("lineage-b", "Task two", lineage="shared-lineage")
            template_a = proposal("template-a", "Task three", lineage="other-a")
            template_b = proposal("template-b", "Task four", lineage="other-b")
            template_b = DatasetProposal(
                **{
                    **template_b.__dict__,
                    "template_family": template_a.template_family,
                }
            )
            for item in (lineage_a, lineage_b, template_a, template_b):
                proposal_store.append_unique(item.to_dict())
                gold_store.append_unique(gold(item.id).to_dict())

            manifest = build_splits(paths)

        self.assertEqual(manifest["assignments"][lineage_a.id], manifest["assignments"][lineage_b.id])
        self.assertEqual(manifest["assignments"][template_a.id], manifest["assignments"][template_b.id])

    def test_private_hidden_seed_is_teacher_blind_and_split_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = ForgePaths(Path(tmp) / "forge")
            input_path = Path(tmp) / "hidden.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "id": "hidden-one",
                        "task_text": "What is 1 + 1?",
                        "assessment": factual_assessment().to_dict(),
                        "template_family": "private-hidden-family",
                        "mutation_lineage": "private-hidden-lineage",
                        "language": "en",
                        "evidence": "Teacher-blind Codex rubric review.",
                        "author": "codex-hidden-pass-v1",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            imported = import_hidden_seed(paths, input_path)
            manifest = build_splits(paths)
            hidden_tasks = AppendOnlyJsonl(paths.root / "splits" / "hidden_test_tasks.jsonl").read_all()

        self.assertEqual(imported, {"validated": 1, "written": 1})
        self.assertEqual(manifest["counts"]["hidden_test"], 1)
        self.assertEqual(hidden_tasks, [{"id": "hidden-one", "input_text": "What is 1 + 1?"}])
        self.assertEqual(manifest["assignments"]["hidden-one"], "hidden_test")


class DatasetForgeProviderSafetyTests(unittest.TestCase):
    def test_antigravity_requires_the_expected_active_account(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            accounts = Path(tmp) / "accounts.json"
            accounts.write_text(json.dumps({"active": "rvbernucci@gmail.com"}), encoding="utf-8")
            provider = AntigravityProvider(expected_email="rvbernucci@gmail.com", accounts_path=accounts)
            provider._verify_account()

            wrong = AntigravityProvider(expected_email="rafael@marianaguia.com", accounts_path=accounts)
            with self.assertRaisesRegex(ProviderError, "does not match"):
                wrong._verify_account()

    def test_claude_rejects_console_or_api_authentication(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["claude", "auth", "status"],
            returncode=0,
            stdout=json.dumps({"authMethod": "api_key", "subscriptionType": "none"}),
            stderr="",
        )
        provider = ClaudeCodeProvider()
        with patch("router.dataset_forge.providers.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(ProviderError, "Pro/Max"):
                provider._validated_subscription_auth()

    def test_antigravity_model_is_pinned_to_available_fast_model(self) -> None:
        self.assertEqual(AGY_MODEL, "Gemini 3.5 Flash (Medium)")


class DatasetForgeMetricsTests(unittest.TestCase):
    def test_weighted_kappa_handles_perfect_and_opposite_ratings(self) -> None:
        self.assertEqual(weighted_quadratic_kappa([(0, 0), (5, 5), (10, 10)]), 1.0)
        self.assertLess(weighted_quadratic_kappa([(0, 10), (10, 0)]), 0.0)


def factual_assessment(deterministic_fit=2) -> TaskAssessment:
    return TaskAssessment(
        intent=Intent.FACTUAL_QA,
        sub_intent="stable_fact",
        scores=AssessmentScores(deterministic_fit, 2, 2, 2, 2),
    )


def provenance(provider_name, model, role, *, request_id="request") -> ProviderProvenance:
    return ProviderProvenance(
        provider=provider_name,
        model=model,
        role=role,
        auth_mode="test",
        usage_window="test-window",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        equivalent_cost_usd=0,
        billable_cost_usd=0,
        request_id=request_id,
        config_sha256="a" * 64,
    )


def proposal(
    identifier,
    text,
    *,
    source="teacher:test",
    lineage="lineage",
    anchor=2,
) -> DatasetProposal:
    return DatasetProposal(
        id=identifier,
        target_id=f"target-{identifier}",
        parent_id=None,
        task_text=text,
        assessment=factual_assessment(anchor),
        rationales=rationales_from_mapping(RATIONALES),
        source=source,
        template_family=f"family-{lineage}",
        mutation_lineage=lineage,
        language="en",
        mutation_kind="canonical",
        boundary_dimension="deterministic_fit",
        boundary_anchor=anchor,
        provenance=provenance("test", "test-model", "generator"),
        content_sha256=content_sha256(text),
        created_at=utc_now(),
    )


def gold(example_id) -> GoldAssessment:
    return GoldAssessment(
        id=stable_id("gold", example_id),
        example_id=example_id,
        assessment=factual_assessment(),
        rating_ids=(f"rating-a-{example_id}", f"rating-b-{example_id}"),
        adjudication_status="accepted",
        intent_agreement=1.0,
        max_score_spread=0,
        adjudicator="test",
        created_at=utc_now(),
    )


if __name__ == "__main__":
    unittest.main()
