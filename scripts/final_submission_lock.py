#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the final Track 1 image and rollback decision.")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--rollback", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--manifest-digest", required=True)
    parser.add_argument("--platform-digest", required=True)
    parser.add_argument("--compressed-size-bytes", type=int, required=True)
    parser.add_argument("--release-run", type=int, required=True)
    parser.add_argument("--local-gate-run", type=int, required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    local = json.loads((ROOT / "reports/public/full-local-exact-image-smoke.json").read_text(encoding="utf-8"))
    pareto = json.loads((ROOT / "reports/public/final-pareto-calibration.json").read_text(encoding="utf-8"))
    checks = {
        "candidate_is_immutable_version_tag": ":v" in args.candidate and "latest" not in args.candidate,
        "rollback_is_distinct_version_tag": ":v" in args.rollback and args.rollback != args.candidate,
        "revision_is_sha40": len(args.revision) == 40 and all(char in "0123456789abcdef" for char in args.revision),
        "manifest_digest_is_sha256": _digest(args.manifest_digest),
        "platform_digest_is_sha256": _digest(args.platform_digest),
        "compressed_size_below_10gb": args.compressed_size_bytes < 10_000_000_000,
        "exact_local_gate_passed": local.get("passed") is True,
        "pareto_gate_passed": pareto.get("passed") is True,
        "release_run_recorded": args.release_run > 0,
        "local_gate_run_recorded": args.local_gate_run > 0,
    }
    passed = all(checks.values())
    payload = {
        "schema_version": "final-release-decision-v1",
        "passed": passed,
        "decision": "promote_full_hybrid" if passed else "use_compact_rollback",
        "candidate": args.candidate,
        "rollback": args.rollback,
        "revision": args.revision,
        "manifest_digest": args.manifest_digest,
        "platform_digest": args.platform_digest,
        "compressed_size_bytes": args.compressed_size_bytes,
        "release_run": {
            "id": args.release_run,
            "url": f"https://github.com/rvbernucci/track1-token-router/actions/runs/{args.release_run}",
        },
        "exact_local_gate_run": {
            "id": args.local_gate_run,
            "url": f"https://github.com/rvbernucci/track1-token-router/actions/runs/{args.local_gate_run}",
        },
        "checks": checks,
        "accepted_risks": [
            "The 80-row arena is a frozen replay plus exact-image envelope projection, not a live 80-row image run.",
            "The 23-task Fireworks microbench is deterministic-validator evidence, not hidden-evaluator accuracy.",
            "The final lablab.ai form and screenshot require manual confirmation outside this repository.",
        ],
        "submission_action": f"Set the Docker Image field to {args.candidate}",
        "rollback_action": f"Replace only the Docker Image field with {args.rollback}",
    }
    final_dir = ROOT / "submission/final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "final-release-decision.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit = {
        "schema_version": "final-image-audit-v1",
        "image": args.candidate,
        "manifest_digest": args.manifest_digest,
        "platform": "linux/amd64",
        "platform_digest": args.platform_digest,
        "revision": args.revision,
        "version": args.candidate.rsplit(":", 1)[-1],
        "compressed_size_bytes": args.compressed_size_bytes,
        "resource_gate": {"memory": "4g", "cpus": 2, "network": "none", "maximum_runtime_seconds": 600},
        "real_local_inference": local,
        "passed": passed,
    }
    (final_dir / "final-image-audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (final_dir / "submission-lock-checklist.md").write_text(_checklist(payload), encoding="utf-8")
    (ROOT / "reports/public/final-hybrid-scorecard.md").write_text(_scorecard(payload, local, pareto), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    if args.strict and not passed:
        return 1
    return 0


def _digest(value: str) -> bool:
    return value.startswith("sha256:") and len(value) == 71 and all(char in "0123456789abcdef" for char in value[7:])


def _checklist(payload):
    return "\n".join(
        [
            "# Submission Lock Checklist",
            "",
            f"- [x] Public image: `{payload['candidate']}`",
            f"- [x] Manifest digest: `{payload['manifest_digest']}`",
            f"- [x] Platform digest: `{payload['platform_digest']}`",
            f"- [x] Source revision: `{payload['revision']}`",
            f"- [x] Compressed size: `{payload['compressed_size_bytes']}` bytes, below 10 GB.",
            f"- [x] Release run: `{payload['release_run']['id']}`.",
            f"- [x] Exact local inference run: `{payload['exact_local_gate_run']['id']}`.",
            f"- [x] Rollback image: `{payload['rollback']}`.",
            "- [ ] Confirm the Docker Image field in lablab.ai uses the final tag.",
            "- [ ] Capture/export the final submitted form.",
            "",
        ]
    )


def _scorecard(payload, local, pareto):
    selected = pareto["candidates"]["intent_policy"]
    baseline = pareto["candidates"]["always_minimax"]
    return "\n".join(
        [
            "# Final Hybrid Scorecard",
            "",
            f"Decision: `{'PROMOTE' if payload['passed'] else 'ROLL BACK'}`",
            "",
            f"- Image: `{payload['candidate']}`.",
            f"- OCI manifest: `{payload['manifest_digest']}`.",
            f"- Compressed size: `{payload['compressed_size_bytes'] / 1_000_000_000:.3f} GB`.",
            f"- Exact-image cold/warm: `{local['metrics']['cold_seconds']}` / `{local['metrics']['warm_seconds']}` seconds.",
            f"- Exact-image sampled peak memory: `{local['metrics']['sampled_peak_memory_mib']}` MiB.",
            "- Exact-image local probes: two E2B routes, zero Fireworks tokens.",
            f"- Fireworks Pareto: `{selected['correct']}/{selected['rows']}` valid with `{selected['tokens']}` tokens.",
            f"- MiniMax baseline: `{baseline['correct']}/{baseline['rows']}` valid with `{baseline['tokens']}` tokens.",
            f"- E2B OOF threshold: `{pareto['selected_e2b_threshold']['threshold']}` at `{pareto['selected_e2b_threshold']['precision']:.2%}` precision.",
            f"- Rollback: `{payload['rollback']}`.",
            "",
            "The promotion is accuracy-first. Claims distinguish live Fireworks calibration, frozen holdout replay and exact-image local inference.",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
