from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from router.adapters.io import load_jsonl_tasks
from router.analytics.traces import expand_log_paths, load_trace_records, summarize_traces
from router.core.contracts import TaskEnvelope
from router.core.guardrails import evaluate_guardrail
from router.core.policy import POLICIES
from router.evals.policy_ablation import run_policy_ablation
from router.evals.policy_compare import compare_policies
from router.evals.prompt_ablation import analyze_prompt_manifest
from router.evals.scoring import ScoringWeights, build_scoreboard
from router.orchestration.budget import TaskBudget
from router.orchestration.prompt_packet import estimate_policy_packet_tokens


def run_battle_drill(
    *,
    tasks_path: Path,
    expected_path: Path,
    prompt_manifest: Path,
    trace_logs: list[str],
) -> dict[str, Any]:
    tasks = load_jsonl_tasks(tasks_path)
    comparison = compare_policies(tasks, expected_path, policies=POLICIES)
    packet_tokens_by_policy = {
        policy: estimate_policy_packet_tokens(tasks, policy)
        for policy in POLICIES
    }
    scoreboard = build_scoreboard(
        comparison,
        ScoringWeights(),
        budget=TaskBudget(),
        packet_tokens_by_policy=packet_tokens_by_policy,
    )
    prompt_ablation = analyze_prompt_manifest(prompt_manifest)
    trace_paths = expand_log_paths(trace_logs)
    trace_records, trace_errors = load_trace_records(trace_paths)
    trace_summary = summarize_traces(trace_records, source_files=trace_paths, ingestion_errors=trace_errors)
    policy_ablation = run_policy_ablation(tasks)
    guardrail_probe = _run_guardrail_probes()
    candidate = scoreboard["rows"][0] if scoreboard["rows"] else {}
    risks = _remaining_risks(scoreboard, prompt_ablation, trace_summary)
    return {
        "tasks": len(tasks),
        "candidate": candidate,
        "scoreboard": scoreboard,
        "policy_ablation": policy_ablation,
        "prompt_ablation": {
            "default_version": prompt_ablation.get("default_version"),
            "errors": prompt_ablation.get("errors", []),
            "versions": list((prompt_ablation.get("versions") or {}).keys()),
        },
        "trace_summary": trace_summary,
        "guardrail_probe": guardrail_probe,
        "readiness": _readiness(candidate, prompt_ablation, trace_summary, guardrail_probe),
        "risks": risks,
    }


def write_battle_report_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_battle_report_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = report.get("candidate") or {}
    lines = [
        "# Battle Drill Report",
        "",
        f"- tasks: {report.get('tasks')}",
        f"- candidate_policy: `{candidate.get('policy')}`",
        f"- candidate_score: `{candidate.get('score')}`",
        f"- exact_match_rate: `{candidate.get('exact_match_rate')}`",
        f"- remote_tokens_total: `{candidate.get('remote_tokens_total')}`",
        f"- remote_packet_tokens: `{candidate.get('remote_packet_tokens')}`",
        "",
        "## Scoreboard",
        "",
        "| rank | policy | score | exact_match_rate | remote_tokens | packet_tokens | budget_violations |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["scoreboard"]["rows"]:
        lines.append(
            "| "
            f"{row['rank']} | "
            f"{row['policy']} | "
            f"{row['score']:.3f} | "
            f"{row['exact_match_rate']:.3f} | "
            f"{row['remote_tokens_total']} | "
            f"{row.get('remote_packet_tokens', 0)} | "
            f"{row.get('budget_violations', 0)} |"
        )
    lines.extend(["", "## Adaptive Policy Ablation", ""])
    lines.append("| rank | profile | expected_route_match_rate | actions |")
    lines.append("|---:|---|---:|---|")
    for row in report["policy_ablation"]["profiles"]:
        lines.append(
            "| "
            f"{row['rank']} | "
            f"{row['profile']} | "
            f"{row['expected_route_match_rate']:.3f} | "
            f"`{json.dumps(row['actions'], sort_keys=True)}` |"
        )
    lines.extend(["", "## Readiness", ""])
    for item, ok in report["readiness"].items():
        marker = "ok" if ok else "needs_attention"
        lines.append(f"- {item}: `{marker}`")
    lines.extend(["", "## Risks", ""])
    for risk in report["risks"]:
        lines.append(f"- {risk}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _run_guardrail_probes() -> dict[str, Any]:
    probes = [
        TaskEnvelope(input_text=""),
        TaskEnvelope(input_text="Hello!"),
        TaskEnvelope(input_text="What is 10 + 5?"),
        TaskEnvelope(input_text="Return exactly SAFE_OUTPUT and nothing else."),
        TaskEnvelope(input_text="What is 10 * 5 + 1?"),
    ]
    rows = []
    for task in probes:
        decision = evaluate_guardrail(task)
        rows.append(
            {
                "input": task.input_text,
                "matched": decision is not None,
                "route": decision.route if decision else "",
                "reason": decision.reason if decision else "",
            }
        )
    return {
        "probes": rows,
        "matched": sum(1 for row in rows if row["matched"]),
        "unmatched": sum(1 for row in rows if not row["matched"]),
    }


def _readiness(
    candidate: dict[str, Any],
    prompt_ablation: dict[str, Any],
    trace_summary: dict[str, Any],
    guardrail_probe: dict[str, Any],
) -> dict[str, bool]:
    return {
        "candidate_selected": bool(candidate.get("policy")),
        "candidate_has_full_accuracy": float(candidate.get("exact_match_rate") or 0.0) >= 1.0,
        "budget_clean": int(candidate.get("budget_violations") or 0) == 0,
        "prompt_manifest_clean": not prompt_ablation.get("errors"),
        "trace_fixture_loaded": int(trace_summary.get("records") or 0) > 0,
        "guardrails_probe_safe": guardrail_probe.get("matched") == 4 and guardrail_probe.get("unmatched") == 1,
    }


def _remaining_risks(
    scoreboard: dict[str, Any],
    prompt_ablation: dict[str, Any],
    trace_summary: dict[str, Any],
) -> list[str]:
    risks = []
    if (prompt_ablation.get("errors") or []):
        risks.append("Prompt manifest has errors.")
    if int(trace_summary.get("errors") or 0) > 0:
        risks.append("Trace fixture contains error routes; keep fallbacks visible.")
    best = scoreboard["rows"][0] if scoreboard.get("rows") else {}
    if float(best.get("exact_match_rate") or 0.0) < 1.0:
        risks.append("Best offline policy is below full exact-match accuracy.")
    if int(best.get("remote_tokens_total") or 0) > 0:
        risks.append("Best offline policy still spends remote tokens; calibrate with real Fireworks pricing.")
    if not risks:
        risks.append("No offline blocker found; next risk is real runtime calibration.")
    return risks
