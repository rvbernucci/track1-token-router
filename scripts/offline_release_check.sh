#!/usr/bin/env sh
set -eu

scripts/verify.sh
python3 scripts/secret_scan.py
