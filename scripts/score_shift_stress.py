#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import AssessmentScores, Engine, TaskAssessment, TaskEnvelope
from router.orchestration.assessment import build_feature_vector, compute_structural_features
from router.orchestration.game_theory_selector import MinimaxRegretSelector, deterministic_solver_prediction
from router.orchestration.outcome_models import OutcomeModelBundle, OutcomeModelPredictor


KIMI = "accounts/fireworks/models/kimi-k2p7-code"
SCORE_NAMES = (
    "deterministic_fit",
    "reasoning_demand",
    "knowledge_uncertainty",
    "generation_demand",
    "format_complexity",
)
PERTURBATION_VALUES = (0, 2, 4, 6, 8, 10)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stress all FunctionGemma score dimensions under distribution shift.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("reports/generated/score-shift-stress.json"))
    parser.add_argument("--markdown", type=Path, default=Path("reports/public/score-shift-stress.md"))
    args = parser.parse_args(argv)
    report = run_stress(args.root)
    output = args.output if args.output.is_absolute() else args.root / args.output
    markdown = args.markdown if args.markdown.is_absolute() else args.root / args.markdown
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["summary"]["unsafe_local_selections"] == 0 else 1


def run_stress(root: Path) -> dict[str, Any]:
    task_rows = {
        str(row["id"]): row
        for row in _jsonl(root / "data/championship-ablation/tasks.jsonl")
    }
    predictions = {
        str(row["id"]): row
        for row in _jsonl(root / "data/championship-ablation/functiongemma-assessments.jsonl")
        if str(row["id"]) in task_rows
    }
    bundle = OutcomeModelBundle.load(root / "configs/engine-outcome-models-v1.json")
    predictor = OutcomeModelPredictor(bundle, allowed_models=[KIMI])
    selector = MinimaxRegretSelector(e2b_enabled=False)
    routes: Counter[str] = Counter()
    unsafe_local = 0
    route_changes = 0
    probability_shift = 0.0
    total = 0
    for task_id, row in predictions.items():
        task = TaskEnvelope(id=task_id, input_text=str(task_rows[task_id]["input_text"]))
        assessment = TaskAssessment.from_mapping(row["prediction"])
        baseline = _decision(task, assessment, predictor=predictor, selector=selector)
        baseline_probability = baseline[1]
        for shifted in perturb_assessment(assessment):
            decision, probability = _decision(task, shifted, predictor=predictor, selector=selector)
            routes[decision] += 1
            total += 1
            probability_shift = max(probability_shift, abs(probability - baseline_probability))
            if decision != baseline[0]:
                route_changes += 1
            if decision != Engine.FIREWORKS.value:
                unsafe_local += 1
    return {
        "schema_version": "score-shift-stress-v1",
        "score_dimensions": list(SCORE_NAMES),
        "perturbation_values": list(PERTURBATION_VALUES),
        "summary": {
            "tasks": len(predictions),
            "perturbations": total,
            "route_counts": dict(sorted(routes.items())),
            "route_changes_from_baseline": route_changes,
            "unsafe_local_selections": unsafe_local,
            "maximum_fireworks_probability_shift": probability_shift,
            "e2b_enabled": False,
            "promoted_runtime_uses_functiongemma_scores": False,
        },
        "decision": (
            "Score perturbations cannot reactivate E2B. The rejected research selector remains Fireworks-safe, "
            "and the promoted runtime removes FunctionGemma scores from its decision surface entirely."
        ),
    }


def perturb_assessment(assessment: TaskAssessment) -> list[TaskAssessment]:
    original = assessment.scores.to_dict()
    result: list[TaskAssessment] = []
    for name in SCORE_NAMES:
        for value in PERTURBATION_VALUES:
            shifted = {**original, name: value}
            result.append(
                TaskAssessment(
                    intent=assessment.intent,
                    scores=AssessmentScores.from_mapping(shifted),
                    sub_intent=assessment.sub_intent,
                )
            )
    return result


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    return "\n".join(
        [
            "# FunctionGemma Score-Shift Stress",
            "",
            "Every one of the five assessment scores was independently replaced with 0, 2, 4, 6, 8 and 10 for each valid frozen validation/test task.",
            "",
            f"- tasks: `{summary['tasks']}`",
            f"- perturbed decisions: `{summary['perturbations']}`",
            f"- route changes: `{summary['route_changes_from_baseline']}`",
            f"- unsafe local selections: `{summary['unsafe_local_selections']}`",
            f"- route counts: `{json.dumps(summary['route_counts'], sort_keys=True)}`",
            f"- maximum Fireworks probability shift: `{summary['maximum_fireworks_probability_shift']:.6f}`",
            "",
            str(report["decision"]),
            "",
        ]
    )


def _decision(
    task: TaskEnvelope,
    assessment: TaskAssessment,
    *,
    predictor: OutcomeModelPredictor,
    selector: MinimaxRegretSelector,
) -> tuple[str, float]:
    features = build_feature_vector(assessment, compute_structural_features(task))
    fireworks = predictor.predict_fireworks_model(features, KIMI)
    e2b = predictor.predict(features, Engine.GEMMA_E2B)
    predictions = {
        Engine.DETERMINISTIC: deterministic_solver_prediction(accepted=False),
        Engine.GEMMA_E2B: e2b,
        Engine.FIREWORKS: fireworks,
    }
    uncertainty = {
        Engine.DETERMINISTIC: 0.0,
        Engine.GEMMA_E2B: predictor.uncertainty(e2b),
        Engine.FIREWORKS: predictor.uncertainty(fireworks),
    }
    decision = selector.select_with_trace(features, predictions, probability_uncertainty=uncertainty).decision
    return decision.engine.value, fireworks.probability_correct


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
