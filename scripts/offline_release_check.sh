#!/usr/bin/env sh
set -eu

scripts/verify.sh
python3 scripts/list_test_coverage.py --check
python3 playground/test_policy_logic.py >/dev/null
python3 playground/test_adapter_logic.py >/dev/null
python3 playground/test_prompt_packets.py >/dev/null
python3 scripts/offline_score_simulator.py >/dev/null
python3 scripts/policy_ablation.py >/dev/null
python3 scripts/prompt_ablation.py --check >/dev/null
python3 scripts/generate_fuzz_eval.py --check >/dev/null
python3 scripts/run_fuzz_eval.py --check >/dev/null
python3 scripts/check_runtime_profiles.py >/dev/null
python3 scripts/build_submission_artifacts.py --check >/dev/null
python3 scripts/submission_readiness_check.py >/dev/null
python3 scripts/analyze_traces.py --logs fixtures/logs/sample-run.jsonl >/dev/null
python3 scripts/latency_drill.py --check >/dev/null
python3 scripts/token_envelope.py --check >/dev/null
python3 scripts/optimize_policy.py --check >/dev/null
python3 scripts/replay_decision.py --text "What is 6 * 7? Return only the number." >/dev/null
python3 scripts/state_machine_report.py >/dev/null
python3 scripts/generate_release_notes.py --tag offline-dry-run --output reports/generated/release-notes.md >/dev/null
python3 scripts/adapter_drill.py --check >/dev/null
python3 scripts/battle_drill.py >/dev/null
python3 scripts/bad_local_model_drill.py --check >/dev/null
python3 scripts/export_public_report.py --check >/dev/null
python3 scripts/check_demo_site.py --check >/dev/null
python3 scripts/secret_scan.py
