#!/usr/bin/env sh
set -eu

scripts/verify.sh
python3 scripts/list_test_coverage.py --check
python3 playground/test_policy_logic.py >/dev/null
python3 playground/test_adapter_logic.py >/dev/null
python3 playground/test_prompt_packets.py >/dev/null
python3 scripts/offline_score_simulator.py >/dev/null
python3 scripts/prompt_ablation.py --check >/dev/null
python3 scripts/analyze_traces.py --logs fixtures/logs/sample-run.jsonl >/dev/null
python3 scripts/state_machine_report.py >/dev/null
python3 scripts/generate_release_notes.py --tag offline-dry-run --output reports/generated/release-notes.md >/dev/null
python3 scripts/secret_scan.py
