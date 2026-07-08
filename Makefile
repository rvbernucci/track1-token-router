PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: setup smoke test official-smoke release-check secret-scan diff-check doctor

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -e .

smoke:
	$(PYTHON) -m router ask "What is 2+2?"

test:
	$(PYTHON) -m unittest discover -s tests

official-smoke:
	ROUTER_MODE=mock $(PYTHON) -m router submit-track1 --input fixtures/official/lablab_track1_tasks.json --output reports/generated/official-smoke-results.json

release-check:
	scripts/offline_release_check.sh

secret-scan:
	$(PYTHON) scripts/secret_scan.py

diff-check:
	git diff --check

doctor: test secret-scan diff-check official-smoke
