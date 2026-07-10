#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import Engine, FeatureVector
from router.orchestration.outcome_models import OutcomeModelBundle, OutcomeModelPredictor


COPIES = {
    "reports/generated/e2b-2000-baselines/validation-test-tasks.jsonl": "tasks.jsonl",
    "reports/generated/e2b-2000-baselines/deterministic-candidates-v2.jsonl": "deterministic-candidates.jsonl",
    "reports/generated/e2b-2000-baselines/kimi-k2p7-code-runtime-v4-candidates.jsonl": "kimi-candidates.jsonl",
    "reports/generated/e2b-2000-baselines/minimax-m3-runtime-v4-candidates.jsonl": "minimax-candidates.jsonl",
    "reports/generated/e2b-2000-baselines/fireworks-runtime-v4-judgments.jsonl": "fireworks-judgments.jsonl",
    "reports/generated/e2b-2000-baselines/fireworks-baseline-comparison.json": "fireworks-baseline-comparison.json",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze or verify the public Sprint 49 evidence pack.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    destination = args.root / "data/championship-ablation"
    if args.check:
        errors = verify(destination)
        print(json.dumps({"ok": not errors, "errors": errors}, sort_keys=True))
        return 0 if not errors else 1
    manifest = freeze(args.root, destination)
    print(json.dumps({"ok": True, "files": len(manifest["files"])}, sort_keys=True))
    return 0


def freeze(root: Path, destination: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    source_hashes: dict[str, str] = {}
    for source_name, target_name in COPIES.items():
        source = root / source_name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source, destination / target_name)
        source_hashes[source_name] = _sha(source)

    task_ids = {str(row["id"]) for row in _jsonl(destination / "tasks.jsonl")}
    prediction_source = root / "reports/generated/amd-pod-e2b-regression-2000/functiongemma-valid-predictions.jsonl"
    compact_predictions = [
        {"id": row["id"], "prediction": row["prediction"]}
        for row in _jsonl(prediction_source)
        if str(row["id"]) in task_ids
    ]
    _write_jsonl(destination / "functiongemma-assessments.jsonl", compact_predictions)
    source_hashes[str(prediction_source.relative_to(root))] = _sha(prediction_source)

    matrix_source = root / "reports/generated/amd-pod-e2b-regression-2000/e2b-outcome-matrix.jsonl"
    model_source = root / "reports/generated/amd-pod-e2b-regression-2000/e2b-outcome-models.json"
    bundle = OutcomeModelBundle.load(model_source)
    predictor = OutcomeModelPredictor(bundle, allowed_models=[])
    selected: list[dict[str, Any]] = []
    for row in _jsonl(matrix_source):
        if row.get("regression_split") != "test" or str(row.get("task_id")) not in task_ids:
            continue
        prediction = predictor.predict(FeatureVector.from_mapping(row["features"]), Engine.GEMMA_E2B)
        lower = max(0.0, prediction.probability_correct - predictor.uncertainty(prediction))
        if lower >= 0.60:
            selected.append(
                {
                    "task_id": row["task_id"],
                    "correct": row.get("correct"),
                    "consensus": row.get("consensus"),
                    "latency_ms": row.get("latency_ms"),
                    "probability_correct": prediction.probability_correct,
                    "probability_lower_bound": lower,
                }
            )
    _write_jsonl(destination / "e2b-selected-test.jsonl", selected)
    source_hashes[str(matrix_source.relative_to(root))] = _sha(matrix_source)
    source_hashes[str(model_source.relative_to(root))] = _sha(model_source)

    files = {
        path.name: {"sha256": _sha(path), "bytes": path.stat().st_size, "rows": _rows(path)}
        for path in sorted(destination.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    manifest = {
        "schema_version": "championship-evidence-manifest-v1",
        "selection_split": "validation",
        "locked_test_used_for_tuning": False,
        "files": files,
        "source_sha256": dict(sorted(source_hashes.items())),
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify(destination: Path) -> list[str]:
    manifest_path = destination / "manifest.json"
    if not manifest_path.is_file():
        return ["missing manifest.json"]
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "championship-evidence-manifest-v1":
        return ["unsupported manifest schema"]
    errors: list[str] = []
    for name, metadata in payload.get("files", {}).items():
        path = destination / name
        if not path.is_file():
            errors.append(f"missing {name}")
        elif _sha(path) != metadata.get("sha256"):
            errors.append(f"hash mismatch: {name}")
        elif path.stat().st_size != metadata.get("bytes"):
            errors.append(f"size mismatch: {name}")
        elif _rows(path) != metadata.get("rows"):
            errors.append(f"row mismatch: {name}")
    return errors


def _rows(path: Path) -> int | None:
    if path.suffix != ".jsonl":
        return None
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
