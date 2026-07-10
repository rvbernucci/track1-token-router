#!/usr/bin/env sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

echo "== AMD Track 1 bootstrap =="
echo "python: $($PYTHON_BIN --version 2>&1)"

$PYTHON_BIN scripts/amd_pod_doctor.py --json

if [ "${SKIP_VENV:-0}" = "1" ]; then
  echo "== Installing package without venv =="
  $PYTHON_BIN -m pip install -e .
  RUN_PYTHON="$PYTHON_BIN"
else
  echo "== Creating virtualenv at $VENV_DIR =="
  if $PYTHON_BIN -m venv "$VENV_DIR"; then
    # shellcheck disable=SC1090
    . "$VENV_DIR/bin/activate"
    python -m pip install --upgrade pip
    python -m pip install -e .
    RUN_PYTHON="python"
  else
    echo "venv creation failed; falling back to user/system install"
    $PYTHON_BIN -m pip install -e .
    RUN_PYTHON="$PYTHON_BIN"
  fi
fi

echo "== Smoke test =="
ROUTER_MODE=mock "$RUN_PYTHON" -m router ask "What is 2+2?"

if [ "${SKIP_TESTS:-0}" != "1" ]; then
  echo "== Unit tests =="
  "$RUN_PYTHON" -m unittest discover -s tests
fi

echo "== Ready =="
echo "Next step: follow docs/FUNCTIONGEMMA_270M_AMD_TRAINING_TUTORIAL.md and persist the trained router artifact."
