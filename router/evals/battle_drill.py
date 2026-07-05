from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from router.adapters.io import load_jsonl_tasks
from router.analytics.traces import expand_log_paths, load_trace_records, summarize_traces
from router.core.contracts import TaskEnvelope
from router.core.guardrails import evaluate_guardrail
from router.core.mock_runner import MockCascadeRunner
from router.core.policy import POLICIES
from router.evals.fuzz_dataset import run_fuzz_pack, validate_fuzz_dataset
from router.evals.policy_ablation import run_policy_ablation
from router.evals.policy_compare import compare_policies
from router.evals.prompt_ablation import analyze_prompt_manifest
from router.evals.scoring import ScoringWeights, build_scoreboard
from router.orchestration.budget import TaskBudget
from router.orchestration.competition import CompetitionRunner
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
    competition_probe = _run_competition_mode_probes()
    fuzz_probe = _run_fuzz_pack_probe()
    candidate = scoreboard["rows"][0] if scoreboard["rows"] else {}
    risks = _remaining_risks(scoreboard, prompt_ablation, trace_summary, competition_probe, fuzz_probe)
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
        "competition_probe": competition_probe,
        "fuzz_probe": fuzz_probe,
        "readiness": _readiness(candidate, prompt_ablation, trace_summary, guardrail_probe, competition_probe, fuzz_probe),
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
    lines.extend(["", "## Competition Mode Probe", ""])
    lines.append("| input | route | action | remote_would_call | repaired |")
    lines.append("|---|---|---|---:|---:|")
    for row in report.get("competition_probe", {}).get("probes", []):
        lines.append(
            "| "
            f"{row['input']} | "
            f"{row['route']} | "
            f"{row['action']} | "
            f"{row['remote_would_call']} | "
            f"{row['final_answer_repaired']} |"
        )
    fuzz_probe = report.get("fuzz_probe", {})
    lines.extend(
        [
            "",
            "## Fuzz Pack",
            "",
            f"- contract_success: `{fuzz_probe.get('contract_success')}`",
            f"- exact_match_rate: `{fuzz_probe.get('exact_match_rate')}`",
            f"- classes: `{len(fuzz_probe.get('classes') or {})}`",
        ]
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


def _run_competition_mode_probes() -> dict[str, Any]:
    runner = CompetitionRunner(MockCascadeRunner(), dry_run=True)
    probes = [
        TaskEnvelope(input_text="What is 10 + 5? Return only the number."),
        TaskEnvelope(input_text="Return exactly SAFE_OUTPUT and nothing else."),
        TaskEnvelope(input_text="Who is the CEO of AMD today?"),
    ]
    rows = []
    for task in probes:
        result = runner.run(task)
        decision = result.metadata["competition_trace"]["decision"]
        rows.append(
            {
                "input": task.input_text,
                "route": result.route,
                "answer": result.answer,
                "action": decision["action"],
                "remote_packet_tokens": decision["remote_packet_tokens"],
                "remote_would_call": decision["remote_would_call"],
                "dry_run": decision["dry_run"],
                "final_answer_repaired": decision["final_answer_repaired"],
                "has_policy": bool(decision.get("policy_decision")),
                "has_budget": bool(decision.get("budget_decision")),
                "has_validation": bool(decision.get("final_validation")),
            }
        )
    return {
        "probes": rows,
        "dry_run": all(row["dry_run"] for row in rows),
        "actual_remote_calls": 0,
        "traces_complete": all(row["has_policy"] and row["has_budget"] and row["has_validation"] for row in rows),
        "remote_would_call": sum(1 for row in rows if row["remote_would_call"]),
    }


def _run_fuzz_pack_probe() -> dict[str, Any]:
    errors = validate_fuzz_dataset(Path("evals/fuzz"), fixtures_root=Path("fixtures/fuzz"))
    if errors:
        return {
            "contract_success": False,
            "errors": errors,
            "classes": {},
            "exact_match_rate": 0.0,
        }
    return run_fuzz_pack(root=Path("evals/fuzz"))


def _readiness(
    candidate: dict[str, Any],
    prompt_ablation: dict[str, Any],
    trace_summary: dict[str, Any],
    guardrail_probe: dict[str, Any],
    competition_probe: dict[str, Any],
    fuzz_probe: dict[str, Any],
) -> dict[str, bool]:
    return {
        "candidate_selected": bool(candidate.get("policy")),
        "candidate_has_full_accuracy": float(candidate.get("exact_match_rate") or 0.0) >= 1.0,
        "budget_clean": int(candidate.get("budget_violations") or 0) == 0,
        "prompt_manifest_clean": not prompt_ablation.get("errors"),
        "trace_fixture_loaded": int(trace_summary.get("records") or 0) > 0,
        "guardrails_probe_safe": guardrail_probe.get("matched") == 4 and guardrail_probe.get("unmatched") == 1,
        "competition_mode_ready": bool(competition_probe.get("dry_run"))
        and int(competition_probe.get("actual_remote_calls") or 0) == 0
        and bool(competition_probe.get("traces_complete")),
        "fuzz_pack_ready": bool(fuzz_probe.get("contract_success"))
        and len(fuzz_probe.get("classes") or {}) >= 10,
    }


def _remaining_risks(
    scoreboard: dict[str, Any],
    prompt_ablation: dict[str, Any],
    trace_summary: dict[str, Any],
    competition_probe: dict[str, Any],
    fuzz_probe: dict[str, Any],
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
    if not competition_probe.get("traces_complete"):
        risks.append("Competition mode probe is missing decision, budget, or validation trace fields.")
    if not fuzz_probe.get("contract_success"):
        risks.append("Fuzz pack contract probe is not clean.")
    if not risks:
        risks.append("No offline blocker found; next risk is real runtime calibration.")
    return risks
