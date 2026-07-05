#!/usr/bin/env sh
set -eu

scripts/verify.sh
python3 scripts/list_test_coverage.py --check
python3 playground/test_policy_logic.py >/dev/null
python3 playground/test_adapter_logic.py >/dev/null
python3 playground/test_prompt_packets.py >/dev/null
python3 scripts/offline_score_simulator.py >/dev/null
python3 scripts/secret_scan.py
