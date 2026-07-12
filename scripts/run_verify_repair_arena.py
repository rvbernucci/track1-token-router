#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.core.fireworks_verify_repair import build_verify_repair_messages, parse_verify_repair
from router.core.model_client import LocalModelClient
from router.core.prompts import build_answer_messages
from router.orchestration.final_validator import validate_or_safely_repair_final_answer


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a paired direct versus verify-or-repair Fireworks arena.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="accounts/fireworks/models/kimi-k2p7-code")
    parser.add_argument("--judge-model", default="accounts/fireworks/models/minimax-m3")
    parser.add_argument("--per-intent", type=int, default=4)
    parser.add_argument("--max-cost-usd", type=float, default=6.0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    key = os.getenv("FIREWORKS_API_KEY", "")
    base = os.getenv("FIREWORKS_BASE_URL", "")
    if not key or not base:
        raise SystemExit("FIREWORKS_API_KEY and FIREWORKS_BASE_URL are required.")
    allowed = {value.strip() for value in os.getenv("ALLOWED_MODELS", "").split(",") if value.strip()}
    if allowed and ({args.model, args.judge_model} - allowed):
        raise SystemExit("Arena models must be present in ALLOWED_MODELS.")

    answer_client = LocalModelClient(base_url=base, api_key=key, model=args.model, timeout_s=90, max_retries=1)
    judge_client = LocalModelClient(base_url=base, api_key=key, model=args.judge_model, timeout_s=90, max_retries=1)
    tasks = _sample(args.per_intent)
    existing = json.loads(_absolute(args.output).read_text()) if args.resume and _absolute(args.output).is_file() else {}
    rows = list(existing.get("rows", []))
    completed = {str(row["task_id"]) for row in rows}
    spent = sum(float(row.get("estimated_cost_usd", 0.0)) for row in rows)
    for item in tasks:
        if item["task_id"] in completed:
            continue
        if spent >= args.max_cost_usd:
            break
        task = TaskEnvelope(id=item["task_id"], input_text=item["task_text"])
        direct = answer_client.complete(build_answer_messages(task), temperature=0, max_tokens=192)
        direct_validation = validate_or_safely_repair_final_answer(task, direct.text)
        direct_answer = direct_validation.repaired_answer or direct.text
        direct_correct, direct_judge = _judge_with_fallback(
            judge_client, answer_client, item["task_text"], direct_answer,
        )

        review = answer_client.complete(
            build_verify_repair_messages(item["task_text"], item["candidate"]),
            temperature=0, max_tokens=256,
            extra_body={"reasoning_effort": "none"},
        )
        malformed = False
        try:
            decision = parse_verify_repair(review.text)
            reviewed_answer = item["candidate"] if decision.approved else decision.answer
            reviewed_validation = validate_or_safely_repair_final_answer(task, reviewed_answer)
            reviewed_answer = reviewed_validation.repaired_answer or reviewed_answer
            if decision.approved:
                reviewed_correct, review_judge = item["candidate_correct"], None
            else:
                reviewed_correct, review_judge = _judge_with_fallback(
                    judge_client, answer_client, item["task_text"], reviewed_answer,
                )
        except ValueError:
            malformed = True
            decision = None
            reviewed_validation = None
            reviewed_correct = False
            reviewed_answer = ""
            review_judge = None

        usage = {
            "direct": direct.usage.to_dict(), "review": review.usage.to_dict(),
            "direct_judge": direct_judge["usage"],
            "review_judge": review_judge["usage"] if review_judge else {"prompt": 0, "completion": 0, "total": 0},
        }
        spent += _estimated_cost(usage)
        row = {
            **{key: item[key] for key in (
                "task_id", "intent", "candidate_correct", "candidate_length", "strict_format",
            )},
            "prompt_sha256": hashlib.sha256(item["task_text"].encode()).hexdigest(),
            "direct_answer": direct_answer,
            "direct_correct": direct_correct,
            "direct_contract_valid": direct_validation.valid,
            "review_approved": decision.approved if decision else None,
            "review_answer": reviewed_answer,
            "review_correct": reviewed_correct,
            "review_contract_valid": reviewed_validation.valid if reviewed_validation else False,
            "review_malformed": malformed,
            "false_approval": bool(decision and decision.approved and not item["candidate_correct"]),
            "false_rejection": bool(decision and not decision.approved and item["candidate_correct"]),
            "usage": usage,
            "request_ids": {
                "direct": _request_id(direct.raw), "review": _request_id(review.raw),
                "direct_judge": direct_judge["request_id"],
                "review_judge": review_judge["request_id"] if review_judge else None,
            },
            "estimated_cost_usd": _estimated_cost(usage),
        }
        rows.append(row)
        _write(args.output, rows, spent, args)
    result = _write(args.output, rows, spent, args)
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


def _sample(per_intent: int) -> list[dict[str, Any]]:
    if per_intent != 4:
        raise ValueError("Frozen arena requires exactly four rows per intent.")
    candidates = {str(row["task_id"]): row for row in _rows(ROOT / "reports/generated/amd-pod-e2b-regression-2000/e2b-candidates-96-contract-v2.jsonl")}
    outcomes = {str(row["task_id"]): row for row in _rows(ROOT / "reports/generated/amd-pod-e2b-regression-2000/e2b-outcome-matrix-contract-v2.jsonl")}
    grouped: dict[tuple[str, bool], list[dict[str, Any]]] = {}
    for task_id, candidate in candidates.items():
        outcome = outcomes.get(task_id)
        if outcome is None or outcome.get("correct") not in {True, False}:
            continue
        intent = str(candidate["functiongemma_assessment"]["intent"])
        contract = candidate.get("answer_contract", {}).get("contract", {})
        grouped.setdefault((intent, bool(outcome["correct"])), []).append({
            "task_id": task_id, "intent": intent, "task_text": candidate["task_text"],
            "candidate": candidate["answer"], "candidate_correct": bool(outcome["correct"]),
            "candidate_length": "long" if len(candidate["answer"]) > 160 else "short",
            "strict_format": bool(contract.get("strict")),
        })
    selected = []
    for intent in sorted({key[0] for key in grouped}):
        for correct in (True, False):
            population = sorted(grouped[(intent, correct)], key=lambda row: (len(row["task_text"]) + len(row["candidate"]), row["task_id"]))
            if len(population) < 2:
                raise ValueError(f"Insufficient arena support for {intent}/{correct}.")
            selected.extend((population[0], population[-1]))
    return selected


def _judge(client: LocalModelClient, task: str, answer: str) -> tuple[bool, dict[str, Any]]:
    messages = [
        {"role": "system", "content": "Judge whether the answer fully and correctly satisfies the task. Return exactly CORRECT or INCORRECT and nothing else."},
        {"role": "user", "content": "<task>\n" + task + "\n</task>\n<answer>\n" + answer + "\n</answer>"},
    ]
    response = client.complete(
        messages, temperature=0, max_tokens=256,
        extra_body={
            "response_format": {"type": "json_object"},
            "reasoning_effort": "none",
        },
    )
    verdict = _judge_verdict(response.text)
    return verdict, {
        "usage": response.usage.to_dict(), "request_id": _request_id(response.raw),
        "model": client.model,
    }


def _judge_with_fallback(
    primary: LocalModelClient, fallback: LocalModelClient, task: str, answer: str,
) -> tuple[bool, dict[str, Any]]:
    try:
        return _judge(primary, task, answer)
    except ValueError:
        verdict, trace = _judge(fallback, task, answer)
        return verdict, {**trace, "fallback_from": primary.model}


def _judge_verdict(value: str) -> bool:
    stripped = value.strip()
    start = stripped.find("{")
    if start >= 0:
        try:
            payload, _ = json.JSONDecoder().raw_decode(stripped[start:])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, Mapping) and isinstance(payload.get("correct"), bool):
            return bool(payload["correct"])
    normalized = stripped.upper().strip("` .!:\n\t")
    matches = re.findall(r"(?<![A-Z])(?:INCORRECT|CORRECT)(?![A-Z])", normalized)
    if len(matches) == 1:
        return matches[0] == "CORRECT"
    raise ValueError("Judge returned an invalid control contract.")


def _write(path: Path, rows: Sequence[Mapping[str, Any]], spent: float, args: Any) -> dict[str, Any]:
    direct_tokens = [int(row["usage"]["direct"]["total"]) for row in rows]
    review_tokens = [int(row["usage"]["review"]["total"]) for row in rows]
    summary = {
        "tasks": len(rows),
        "direct_correct": sum(bool(row["direct_correct"]) for row in rows),
        "review_correct": sum(bool(row["review_correct"]) for row in rows),
        "approvals": sum(row["review_approved"] is True for row in rows),
        "repairs": sum(row["review_approved"] is False for row in rows),
        "false_approvals": sum(bool(row["false_approval"]) for row in rows),
        "false_rejections": sum(bool(row["false_rejection"]) for row in rows),
        "malformed": sum(bool(row["review_malformed"]) for row in rows),
        "direct_total_tokens": sum(direct_tokens),
        "review_total_tokens": sum(review_tokens),
        "direct_mean_tokens": statistics.fmean(direct_tokens) if direct_tokens else 0.0,
        "review_mean_tokens": statistics.fmean(review_tokens) if review_tokens else 0.0,
        "review_token_savings": sum(direct_tokens) - sum(review_tokens),
        "estimated_cost_usd": spent,
    }
    payload = {
        "schema_version": "verify-repair-arena-v1",
        "models": {"answer_and_review": args.model, "blind_judge": args.judge_model},
        "max_cost_usd": args.max_cost_usd,
        "summary": summary,
        "rows": list(rows),
    }
    target = _absolute(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    return payload


def _estimated_cost(usage: Mapping[str, Mapping[str, int]]) -> float:
    prompt = sum(int(value["prompt"]) for value in usage.values())
    completion = sum(int(value["completion"]) for value in usage.values())
    return prompt / 1_000_000 * 1.0 + completion / 1_000_000 * 3.0


def _request_id(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("id") or payload.get("request_id")
    return str(value) if value else None


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
