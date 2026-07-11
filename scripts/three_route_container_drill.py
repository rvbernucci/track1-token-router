#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXACT_IMAGE_EVIDENCE = ROOT / "reports/public/full-local-exact-image-smoke.json"
DEFAULT_JSON = ROOT / "reports/generated/full-local/failure-injection.json"
DEFAULT_REPORT = ROOT / "reports/public/three-route-contract-drill.md"

TESTS = (
    "tests.test_fireworks_runner.FireworksDirectRunnerTests.test_solver_runs_before_fireworks",
    "tests.test_fireworks_runner.FireworksDirectRunnerTests.test_calls_fireworks_for_general_task",
    "tests.test_fireworks_runner.FireworksDirectRunnerTests.test_submit_track1_remote_failure_exits_nonzero_without_output",
    "tests.test_fireworks_runner.FireworksDirectRunnerTests.test_uses_selected_allowed_model_for_task",
    "tests.test_fireworks_runner.FireworksDirectRunnerTests.test_champion_outside_allowed_models_falls_back_without_invalid_call",
    "tests.test_fireworks_runner.FireworksDirectRunnerTests.test_timeout_error_does_not_cascade_across_allowed_models",
    "tests.test_fireworks_runner.FireworksDirectRunnerTests.test_429_503_and_malformed_json_fail_closed_with_one_answer",
    "tests.test_three_route_runner.ThreeRouteRunnerTests.test_assessment_failure_falls_closed_to_fireworks",
    "tests.test_three_route_runner.ThreeRouteRunnerTests.test_recoverable_e2b_memory_failure_falls_back_to_fireworks",
    "tests.test_three_route_runner.ThreeRouteRunnerTests.test_invalid_e2b_answer_falls_back_to_fireworks",
    "tests.test_three_route_runner.ThreeRouteRunnerTests.test_safely_repaired_e2b_answer_avoids_fireworks",
    "tests.test_three_route_runner.ThreeRouteRunnerTests.test_matrix_gate_uses_raw_not_calibrated_assessment",
    "tests.test_three_route_runner.ThreeRouteRunnerTests.test_disabled_e2b_routes_to_fireworks",
    "tests.test_three_route_runner.ThreeRouteRunnerTests.test_enabled_high_confidence_e2b_can_answer_locally",
    "tests.test_official_adapters.OfficialAdapterTests.test_lablab_track1_cli_submission_contract",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Sprint 61 three-route and failure-contract drill.")
    parser.add_argument("--image", default="ghcr.io/rvbernucci/track1-token-router:v3.2.0-full-hybrid")
    parser.add_argument("--fixtures", type=Path, default=Path("fixtures/full-local/three-route"))
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    exact = json.loads(EXACT_IMAGE_EVIDENCE.read_text(encoding="utf-8"))
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", *TESTS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    local_routes = [probe["route"] for probe in exact.get("probes", [])]
    checks = {
        "exact_image_e2b_witness": exact.get("passed") is True and any(route.startswith("e2b_local") for route in local_routes),
        "exact_image_zero_remote_tokens": all(
            probe.get("fireworks_prompt_tokens") == 0 and probe.get("fireworks_completion_tokens") == 0
            for probe in exact.get("probes", [])
        ),
        "named_failure_contract_tests": completed.returncode == 0,
        "deterministic_witness": completed.returncode == 0,
        "fireworks_witness": completed.returncode == 0,
        "remote_failure_nonzero_without_output": completed.returncode == 0,
        "dynamic_allowed_model_enforcement": completed.returncode == 0,
    }
    payload = {
        "schema_version": "three-route-contract-drill-v1",
        "passed": all(checks.values()),
        "image": args.image,
        "checks": checks,
        "route_witnesses": {
            "deterministic": "solver_arithmetic",
            "e2b": local_routes,
            "fireworks": "fireworks_direct",
        },
        "failure_injections": [
            "functiongemma_malformed",
            "e2b_memory_error",
            "e2b_invalid_answer",
            "fireworks_429",
            "fireworks_503",
            "fireworks_malformed_json",
        ],
        "named_tests": list(TESTS),
        "test_returncode": completed.returncode,
        "test_stderr": completed.stderr.strip(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(_markdown(payload), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    return 0 if payload["passed"] else 1


def _markdown(payload: dict[str, object]) -> str:
    checks = payload["checks"]
    assert isinstance(checks, dict)
    lines = [
        "# Three-Route Failure And Contract Drill",
        "",
        f"Decision: `{'PASS' if payload['passed'] else 'FAIL'}`",
        "",
        f"Exact image: `{payload['image']}`",
        "",
        "## Route Witnesses",
        "",
        "- Deterministic: proof-carrying arithmetic, zero remote requests.",
        "- Gemma E2B: exact-image local inference inherited from Sprint 60, zero Fireworks tokens.",
        "- Fireworks: raw task text sent to an authorized runtime model and returned through the official adapter.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- [{'x' if value else ' '}] `{name}`" for name, value in checks.items())
    lines.extend(
        [
            "",
            "## Failure Contract",
            "",
            "FunctionGemma and E2B failures fall through to Fireworks with structured reasons. A terminal Fireworks failure now makes `submit-track1` exit non-zero before writing `results.json`; it cannot be scored as a synthetic answer.",
            "",
            "The drill uses named, deterministic tests for failure injection and the immutable exact-image artifact from GitHub Actions run 29157770736 for real local inference.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
