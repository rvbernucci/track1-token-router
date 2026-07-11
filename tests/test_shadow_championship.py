from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from router.evals.shadow_runtime import (
    FrozenE2BAdapter,
    FrozenFireworksAdapter,
    ShadowRuntime,
    ShadowVariant,
)
from router.orchestration.local_adjudication import LocalAdjudicationPolicy
from scripts.offline_shadow_championship import run_shadow
from scripts.verify_amd_return_manifest import (
    load_manifest,
    prepare_return_checksums,
    verify_return_bundle,
    verify_source_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/championship-shadow-policy-v1.json"


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ShadowChampionshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_shadow(CONFIG_PATH)
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.inputs = _jsonl(ROOT / cls.config["evaluation"]["inputs_path"])
        cls.labels = _jsonl(ROOT / cls.config["evaluation"]["labels_path"])

    def test_holdout_is_hash_pinned_label_isolated_and_lineage_disjoint(self) -> None:
        evaluation = self.config["evaluation"]
        manifest_path = ROOT / evaluation["manifest_path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        for name in ("inputs", "labels", "manifest"):
            path = ROOT / evaluation[f"{name}_path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), evaluation[f"{name}_sha256"])
        self.assertEqual(manifest["rows"], 240)
        self.assertEqual(manifest["splits"], {"train": 96, "validation": 64, "final_holdout": 80})
        self.assertEqual(len(manifest["categories"]), 8)
        self.assertTrue(manifest["labels_are_separate_from_runtime_inputs"])
        self.assertTrue(all("expected_answer" not in row for row in self.inputs))
        self.assertEqual([row["task_id"] for row in self.inputs], [row["task_id"] for row in self.labels])

        for key in ("mutation_lineage", "template_family"):
            split_values = {
                split: {row[key] for row in self.inputs if row["regression_split"] == split}
                for split in ("train", "validation", "final_holdout")
            }
            self.assertTrue(split_values["train"].isdisjoint(split_values["validation"]))
            self.assertTrue(split_values["train"].isdisjoint(split_values["final_holdout"]))
            self.assertTrue(split_values["validation"].isdisjoint(split_values["final_holdout"]))

    def test_frozen_adapters_enforce_authorization_and_well_formed_candidates(self) -> None:
        row = next(row for row in self.inputs if row["regression_split"] == "final_holdout")
        model = row["frozen_fireworks"]["model"]
        adapter = FrozenFireworksAdapter(base_url="https://shadow.invalid/v1", allowed_models=[model])

        result = adapter.complete(row)
        self.assertEqual(result.task_id, row["task_id"])
        self.assertGreater(result.remote_tokens, 0)
        with self.assertRaises(ValueError):
            FrozenFireworksAdapter(
                base_url="https://shadow.invalid/v1",
                allowed_models=["accounts/fireworks/models/not-allowed"],
            ).complete(row)

        malformed = copy.deepcopy(row)
        malformed["frozen_e2b"]["answer"] = ""
        with self.assertRaises(ValueError):
            FrozenE2BAdapter().candidate(malformed)

    def test_runtime_preserves_order_and_writes_deadline_fallbacks(self) -> None:
        rows = [row for row in self.inputs if row["regression_split"] == "final_holdout"][:3]
        allowed = [rows[0]["frozen_fireworks"]["model"]]
        runtime = ShadowRuntime(
            variant=ShadowVariant.FIREWORKS_ONLY,
            local_policy=LocalAdjudicationPolicy.load(ROOT / "configs/local-adjudication-policy-v1.json"),
            fireworks=FrozenFireworksAdapter(base_url="https://shadow.invalid/v1", allowed_models=allowed),
            deadline_ms=1,
            reserve_ms=0,
        )

        results = runtime.run(rows)

        self.assertEqual([row.task_id for row in results], [row["task_id"] for row in rows])
        self.assertEqual(len(results), len(rows))
        self.assertEqual(results[-1].route, "shadow_deadline_exhausted")
        self.assertTrue(all(result.answer for result in results))

    def test_selected_variant_clears_accuracy_and_token_efficiency_gates(self) -> None:
        selected = self.report["variants"]["deterministic_fireworks"]
        baseline = self.report["variants"]["fireworks_only"]
        selected_rows = _jsonl(ROOT / "reports/generated/shadow-championship/deterministic_fireworks.jsonl")
        local_rows = [row for row in selected_rows if row["local_release"]]

        self.assertEqual(selected["accuracy"], 1.0)
        self.assertEqual(selected["local_releases"], 40)
        self.assertEqual(selected["local_precision"], 1.0)
        self.assertGreater(selected["local_wilson_lower_95"], 0.9)
        self.assertEqual(selected["remote_tokens"], 1145)
        self.assertEqual(baseline["remote_tokens"], 2676)
        self.assertEqual(self.report["token_savings_bootstrap"]["observed_tokens_saved"], 1531)
        self.assertGreater(self.report["token_savings_bootstrap"]["tokens_saved_ci95"][0], 0)
        self.assertEqual(len(local_rows), 40)
        self.assertTrue(all(row["proof"] and row["proof"]["hard_gate_passed"] for row in local_rows))
        self.assertTrue(all(row["accuracy"] == 1.0 for row in selected["by_category"].values()))
        self.assertTrue(all(row["accuracy"] == 1.0 for row in self.report["distribution_mixes"].values()))

    def test_unverified_e2b_ablation_is_rejected_despite_lower_token_count(self) -> None:
        unsafe = self.report["variants"]["e2b_regression_without_proofs"]
        selected = self.report["variants"]["deterministic_fireworks"]

        self.assertLess(unsafe["remote_tokens"], selected["remote_tokens"])
        self.assertLess(unsafe["accuracy"], self.config["gates"]["minimum_accuracy"])
        self.assertLess(unsafe["local_precision"], self.config["gates"]["minimum_local_precision"])
        self.assertEqual(self.report["decision"]["selected_runtime_variant"], "deterministic_fireworks")

    def test_chaos_and_official_io_pass_but_release_stays_blocked(self) -> None:
        decision = self.report["decision"]

        self.assertTrue(self.report["chaos"]["passed"])
        self.assertTrue(all(self.report["chaos"]["checks"].values()))
        self.assertTrue(self.report["official_io"]["passed"])
        self.assertTrue(all(self.report["official_io"]["checks"].values()))
        self.assertTrue(self.report["docker"]["static_gate_passed"])
        self.assertFalse(self.report["docker"]["live_gate_executed"])
        self.assertTrue(decision["offline_gate_passed"])
        self.assertFalse(decision["local_e2b_policy_enabled"])
        self.assertFalse(decision["release_ready"])
        self.assertFalse(decision["submission_attempt_allowed"])

    def test_amd_source_manifest_and_runbook_are_executable_contracts(self) -> None:
        manifest_path = ROOT / "configs/amd-return-manifest-v1.json"
        manifest = load_manifest(manifest_path)
        result = verify_source_bundle(manifest, root=ROOT)
        runbook = (ROOT / "docs/AMD_RETURN_RUNBOOK.md").read_text(encoding="utf-8")

        self.assertTrue(result["passed"])
        self.assertEqual(result["checked"], len(manifest["source_bundle"]))
        self.assertEqual(manifest["model_pins"]["functiongemma_base"]["revision"], "39eccb091651513a5dfb56892d3714c1b5b8276c")
        self.assertTrue(manifest["model_pins"]["gemma_e2b"]["release_blocked_without_new_artifact_hash"])
        self.assertIn("verify_amd_return_manifest.py source --write-checksums", runbook)
        self.assertIn("verify_amd_return_manifest.py prepare-return", runbook)
        self.assertIn("verify_amd_return_manifest.py verify-return", runbook)
        self.assertIn("docker buildx build --platform linux/amd64", runbook)

    def test_amd_checksum_chain_detects_source_and_return_tampering(self) -> None:
        real_manifest = load_manifest(ROOT / "configs/amd-return-manifest-v1.json")
        with tempfile.TemporaryDirectory(prefix="amd-manifest-") as temporary:
            root = Path(temporary)
            source = root / "critical.txt"
            source.write_text("frozen\n", encoding="utf-8")
            manifest = copy.deepcopy(real_manifest)
            manifest["source_bundle"] = [
                {"path": "critical.txt", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
            ]
            self.assertTrue(verify_source_bundle(manifest, root=root)["passed"])
            source.write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_source_bundle(manifest, root=root)

            model = root / "artifacts/e2b.gguf"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"quantized-model")
            return_root = root / "reports/amd-return"
            return_root.mkdir(parents=True)
            (return_root / "environment.json").write_text("{}\n", encoding="utf-8")
            (return_root / "combined-runtime.json").write_text("{}\n", encoding="utf-8")
            (return_root / "fresh-inference.jsonl").write_text('{"task_id":"fresh-1"}\n', encoding="utf-8")
            (return_root / "docker-resource-gate.json").write_text("{}\n", encoding="utf-8")
            model_digest = hashlib.sha256(model.read_bytes()).hexdigest()
            (return_root / "model-artifacts.sha256").write_text(
                f"{model_digest}  artifacts/e2b.gguf\n",
                encoding="utf-8",
            )

            prepared = prepare_return_checksums(manifest, root=root)
            self.assertTrue(prepared["passed"])
            self.assertTrue(verify_return_bundle(manifest, root=root)["passed"])
            model.write_bytes(b"tampered-model")
            with self.assertRaisesRegex(ValueError, "Model artifact SHA-256 mismatch"):
                verify_return_bundle(manifest, root=root)
            model.write_bytes(b"quantized-model")
            (return_root / "combined-runtime.json").write_text('{"tampered":true}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_return_bundle(manifest, root=root)


if __name__ == "__main__":
    unittest.main()
