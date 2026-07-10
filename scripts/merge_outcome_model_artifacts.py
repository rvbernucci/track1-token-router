#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.orchestration.outcome_models import OutcomeModelBundle


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge SHA-traced outcome model artifacts.")
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--override", type=Path, required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = merge_artifacts(
        base_path=args.base,
        override_path=args.override,
        model_ids=args.model,
        output_path=args.output,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


def merge_artifacts(
    *,
    base_path: Path,
    override_path: Path,
    model_ids: Sequence[str],
    output_path: Path,
) -> dict[str, Any]:
    requested = tuple(dict.fromkeys(model_ids))
    if not requested:
        raise ValueError("At least one override model is required.")
    base_bundle = OutcomeModelBundle.load(base_path)
    override_bundle = OutcomeModelBundle.load(override_path)
    missing = [model for model in requested if model not in override_bundle.models]
    if missing:
        raise ValueError(f"Override artifact is missing models: {missing!r}.")
    models: dict[str, Mapping[str, Any]] = dict(base_bundle.models)
    for model in requested:
        models[model] = override_bundle.models[model]
    source_artifacts = {
        "base": {
            "artifact_sha256": base_bundle.artifact_sha256,
            "matrix_sha256": base_bundle.matrix_sha256,
        },
        "override": {
            "artifact_sha256": override_bundle.artifact_sha256,
            "matrix_sha256": override_bundle.matrix_sha256,
            "models": list(requested),
        },
    }
    combined_lineage = hashlib.sha256(
        json.dumps(source_artifacts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = {
        "schema_version": "engine-outcome-models-v1",
        "matrix_sha256": combined_lineage,
        "source_artifacts": source_artifacts,
        "models": models,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    merged = OutcomeModelBundle.load(output_path)
    return {
        "output": str(output_path),
        "artifact_sha256": merged.artifact_sha256,
        "matrix_sha256": merged.matrix_sha256,
        "models": sorted(merged.models),
        "overridden_models": list(requested),
    }


if __name__ == "__main__":
    raise SystemExit(main())
