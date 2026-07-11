#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and score the Sprint 62 eight-category arena.")
    parser.add_argument("--image", default="ghcr.io/rvbernucci/track1-token-router:v3.2.0-full-hybrid")
    parser.add_argument("--tasks", type=Path, default=Path("evals/full-local-arena/tasks.json"))
    parser.add_argument("--deadline-seconds", type=float, default=570.0)
    parser.add_argument("--output", type=Path, default=Path("reports/generated/full-local/arena-summary.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/public/full-local-arena.md"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    subprocess.run([sys.executable, "scripts/offline_shadow_championship.py", "--check"], cwd=ROOT, check=True, capture_output=True)
    shadow = _read_json(ROOT / "reports/generated/offline-shadow-championship.json")
    exact = _read_json(ROOT / "reports/public/full-local-exact-image-smoke.json")
    manifest = _read_json(ROOT / "evals/shadow-championship/manifest.json")
    inputs_path = ROOT / "evals/shadow-championship/inputs.jsonl"
    labels_path = ROOT / "evals/shadow-championship/labels.jsonl"
    if _sha256(inputs_path) != manifest["inputs_sha256"] or _sha256(labels_path) != manifest["labels_sha256"]:
        raise ValueError("Arena lineage hashes do not match the frozen manifest.")

    inputs = [row for row in _jsonl(inputs_path) if row["regression_split"] == "final_holdout"]
    labels = [row for row in _jsonl(labels_path) if row["regression_split"] == "final_holdout"]
    arena_tasks = [{"task_id": row["task_id"], "prompt": row["prompt"]} for row in inputs]
    tasks_path = ROOT / args.tasks
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(json.dumps(arena_tasks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    selected_name = shadow["decision"]["selected_runtime_variant"]
    selected = shadow["variants"][selected_name]
    baseline = shadow["variants"]["fireworks_only"]
    exact_metrics = exact["metrics"]
    local_rows = int(selected["local_releases"])
    local_correct = round(float(selected["local_precision"]) * local_rows)
    projected_local_seconds = float(exact_metrics["cold_seconds"]) + max(0, len(inputs) - 1) * float(exact_metrics["warm_seconds"])
    remote_rows = len(inputs) - local_rows
    projected_remote_seconds = remote_rows * float(selected["simulated_p95_latency_ms"]) / 1000.0
    projected_seconds = projected_local_seconds + projected_remote_seconds
    checks = {
        "lineage_hashes_valid": True,
        "balanced_eight_categories": len(selected["by_category"]) == 8 and all(v["rows"] == 10 for v in selected["by_category"].values()),
        "deadline_projection_below_570_seconds": projected_seconds < args.deadline_seconds,
        "peak_memory_at_most_3584_mib": float(exact_metrics["sampled_peak_memory_mib"]) <= 3584.0,
        "answer_contract_validity_100pct": int(selected["output_schema_failures"]) == 0,
        "local_precision_at_least_80pct": float(selected["local_precision"]) >= 0.80,
        "runtime_failure_rate_at_most_2pct": int(selected["errors"]) / len(inputs) <= 0.02,
        "all_categories_successful": all(v["correct"] > 0 for v in selected["by_category"].values()),
        "remote_tokens_below_always_fireworks": int(selected["remote_tokens"]) < int(baseline["remote_tokens"]),
    }
    payload = {
        "schema_version": "full-local-arena-v1",
        "passed": all(checks.values()),
        "evidence_mode": "frozen_holdout_plus_exact_image_envelope_projection",
        "image": args.image,
        "rows": len(inputs),
        "tasks_sha256": _sha256(tasks_path),
        "labels_sha256": manifest["labels_sha256"],
        "checks": checks,
        "holdout": selected,
        "always_fireworks": baseline,
        "token_savings": int(baseline["remote_tokens"]) - int(selected["remote_tokens"]),
        "token_savings_rate": 1.0 - int(selected["remote_tokens"]) / int(baseline["remote_tokens"]),
        "local_wilson_lower_95": _wilson_lower(local_correct, local_rows),
        "exact_image_envelope": exact,
        "runtime_projection": {
            "local_seconds": round(projected_local_seconds, 3),
            "remote_seconds_at_frozen_p95": round(projected_remote_seconds, 3),
            "total_seconds": round(projected_seconds, 3),
            "deadline_seconds": args.deadline_seconds,
            "reserve_seconds": round(args.deadline_seconds - projected_seconds, 3),
        },
        "limitations": [
            "The full 80-row batch is a frozen replay, not a live execution of all rows in the public image.",
            "The exact image measurements are real two-probe container measurements and are used conservatively for projection.",
        ],
    }
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path = ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_markdown(payload), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    return 0 if payload["passed"] else 1


def _markdown(payload: dict[str, object]) -> str:
    holdout = payload["holdout"]
    runtime = payload["runtime_projection"]
    checks = payload["checks"]
    assert isinstance(holdout, dict) and isinstance(runtime, dict) and isinstance(checks, dict)
    lines = [
        "# Full Local Eight-Category Arena",
        "",
        f"Decision: `{'PASS' if payload['passed'] else 'FAIL'}`",
        "",
        "## Results",
        "",
        f"- Frozen final holdout: `{payload['rows']}` rows, 10 per Track 1 category.",
        f"- Accuracy: `{float(holdout['accuracy']):.2%}`.",
        f"- Local precision: `{float(holdout['local_precision']):.2%}`; Wilson 95% lower bound `{float(payload['local_wilson_lower_95']):.2%}`.",
        f"- Local coverage: `{float(holdout['local_coverage']):.2%}`.",
        f"- Remote tokens: `{holdout['remote_tokens']}` versus `{payload['always_fireworks']['remote_tokens']}` always-Fireworks.",
        f"- Token reduction: `{float(payload['token_savings_rate']):.2%}`.",
        f"- Runtime projection: `{runtime['total_seconds']}` seconds with `{runtime['reserve_seconds']}` seconds reserve.",
        f"- Exact-image sampled peak memory: `{payload['exact_image_envelope']['metrics']['sampled_peak_memory_mib']}` MiB.",
        "",
        "## Gates",
        "",
    ]
    lines.extend(f"- [{'x' if value else ' '}] `{name}`" for name, value in checks.items())
    lines.extend(
        [
            "",
            "## Evidence Boundary",
            "",
            "The 80-row accuracy and token results are a lineage-separated frozen replay. The container timing and memory figures come from the exact public image gate. Runtime is a conservative projection that charges one warm local inference per remaining row plus frozen Fireworks p95 latency; it is not represented as a live 80-row image run.",
            "",
        ]
    )
    return "\n".join(lines)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wilson_lower(successes: int, total: int) -> float:
    if total == 0:
        return 0.0
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


if __name__ == "__main__":
    raise SystemExit(main())
