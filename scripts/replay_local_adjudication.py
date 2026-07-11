#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskAssessment, TaskEnvelope
from router.orchestration.assessment import build_feature_vector, compute_structural_features
from router.orchestration.local_adjudication import (
    LocalAdjudicationPolicy,
    build_local_adjudication_evidence,
    combine_adjudication_features,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay exact local-adjudication routes and proof evidence.")
    parser.add_argument("--policy", type=Path, default=Path("configs/local-adjudication-policy-v1.json"))
    parser.add_argument("--dataset", type=Path, default=Path("evals/local-adjudication/adjudication-dataset.jsonl"))
    parser.add_argument("--split", default="fresh_holdout")
    parser.add_argument("--output", type=Path, default=Path("reports/generated/local-adjudication-replay.jsonl"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    policy = LocalAdjudicationPolicy.load(_absolute(args.policy))
    rows = [row for row in _jsonl(_absolute(args.dataset)) if row["regression_split"] == args.split]
    replayed: list[dict[str, Any]] = []
    false_local = 0
    for row in rows:
        task = TaskEnvelope(id=str(row["task_id"]), input_text=str(row["prompt"]))
        assessment = TaskAssessment.from_mapping(row["assessment"])
        task_features = build_feature_vector(assessment, compute_structural_features(task))
        evidence = build_local_adjudication_evidence(task, str(row["candidate"]))
        combined = combine_adjudication_features(task_features, evidence)
        mapping = dict(zip(combined.names, combined.values, strict=True))
        post_probability = policy.post_model.predict(mapping)
        decision = policy.adjudicate(
            task,
            str(row["candidate"]),
            task_features,
            deadline_remaining_ms=600_000,
        )
        false_local += int(decision.accepted and row["correct"] is not True)
        replayed.append(
            {
                "id": row["id"],
                "expected_correct": row["correct"],
                "route": decision.route,
                "reason": decision.reason,
                "pre_probability": decision.pre_probability,
                "post_probability": post_probability,
                "policy_sha256": policy.artifact_sha256,
                "proof": evidence.to_dict(),
            }
        )
    output = _absolute(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in replayed), encoding="utf-8")
    summary = {"rows": len(replayed), "local_releases": sum(row["route"] == "local" for row in replayed), "false_local_releases": false_local, "policy_enabled": policy.enabled}
    print(json.dumps(summary, sort_keys=True))
    return 0 if not args.check or false_local == 0 else 1


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
