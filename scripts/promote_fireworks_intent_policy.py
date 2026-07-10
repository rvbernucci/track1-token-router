#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


INTENT_TO_DOMAIN = {
    "factual_qa": "current_factual",
    "math_reasoning": "math_reasoning",
    "sentiment": "classification",
    "summarization": "summarization",
    "ner": "extraction",
    "code_debugging": "code_debug",
    "logic_puzzle": "logic",
    "code_generation": "code_generation",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote a validation-only Fireworks intent policy.")
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--accuracy-gate", type=float, default=0.60)
    args = parser.parse_args(argv)
    artifact = promote(args.comparison, accuracy_gate=args.accuracy_gate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(hashlib.sha256(args.output.read_bytes()).hexdigest())
    return 0


def promote(comparison_path: Path, *, accuracy_gate: float = 0.60) -> dict[str, Any]:
    raw = comparison_path.read_bytes()
    report = json.loads(raw)
    if not isinstance(report, Mapping) or report.get("schema_version") != "fireworks-baseline-comparison-v1":
        raise ValueError("Unsupported Fireworks comparison report.")
    choices = report.get("validation_selected_model_by_intent")
    summaries = report.get("model_summary")
    if not isinstance(choices, Mapping) or set(choices) != set(INTENT_TO_DOMAIN):
        raise ValueError("Comparison report does not cover all eight Track 1 intents.")
    if not isinstance(summaries, Mapping) or not summaries:
        raise ValueError("Comparison report has no model summary.")
    if not 0.0 < accuracy_gate <= 1.0:
        raise ValueError("accuracy_gate must be in (0, 1].")
    locked_test = report.get("locked_test_policy")
    if not isinstance(locked_test, Mapping):
        raise ValueError("Comparison report has no locked-test promotion evidence.")
    locked_accuracy = float(locked_test.get("conservative_accuracy") or 0.0)

    models = sorted(str(model) for model in summaries)
    default_model = max(
        models,
        key=lambda model: (
            float(summaries[model]["validation"]["conservative_accuracy"]),
            -float(summaries[model]["validation"]["average_tokens"]),
            model,
        ),
    )
    intent_models = {str(intent): str(model) for intent, model in sorted(choices.items())}
    if not {default_model, *intent_models.values()}.issubset(set(models)):
        raise ValueError("Comparison choices reference an unknown model.")
    return {
        "schema_version": "fireworks-intent-policy-v1",
        "default_enabled": locked_accuracy >= accuracy_gate,
        "selection_split": "validation",
        "locked_test_used_for_selection": False,
        "selection_rule": "maximize conservative accuracy; break ties with lower average total tokens",
        "default_model": default_model,
        "allowed_models": models,
        "intent_models": intent_models,
        "intent_to_runtime_domain": INTENT_TO_DOMAIN,
        "promotion_gate": {
            "metric": "locked_test_conservative_accuracy",
            "required": accuracy_gate,
            "observed": locked_accuracy,
            "passed": locked_accuracy >= accuracy_gate,
        },
        "source": {
            "comparison_report": comparison_path.name,
            "comparison_report_sha256": hashlib.sha256(raw).hexdigest(),
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
