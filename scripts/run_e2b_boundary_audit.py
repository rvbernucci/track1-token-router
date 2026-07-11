#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import signal
import subprocess
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.core.e2b_runner import GemmaE2BRunner
from router.core.model_client import LocalModelClient
from router.functiongemma.calibration import load_calibration
from router.functiongemma.provider import FunctionGemmaAssessmentProvider, FunctionGemmaProviderError
from router.orchestration.e2b_matrix_gate import E2BMatrixGate
from router.orchestration.final_validator import validate_or_safely_repair_final_answer


ROOT = Path(__file__).resolve().parents[1]
BANDS = ((0.0, .65), (.65, .70), (.70, .75), (.75, .80), (.80, .90), (.90, 1.01))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the real local Sprint 65 E2B boundary audit.")
    parser.add_argument("--threshold", type=float, default=.75)
    parser.add_argument("--tasks", type=Path, default=Path("evals/e2b-boundary-v1/sealed/tasks.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated/e2b-boundary-v1"))
    parser.add_argument("--public-report", type=Path, default=Path("reports/public/e2b-boundary-audit.md"))
    parser.add_argument("--start-local", action="store_true")
    parser.add_argument("--relabel-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.relabel_only:
        result = relabel(ROOT / args.tasks, ROOT / args.output_dir, threshold=args.threshold)
        report = ROOT / args.public_report
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(_markdown(result), encoding="utf-8")
        if args.json:
            print(json.dumps(result, sort_keys=True))
        return 0 if result["passed"] or not args.check else 1
    processes = _start_local() if args.start_local else []
    try:
        result = run(ROOT / args.tasks, ROOT / args.output_dir, threshold=args.threshold)
    finally:
        for process in reversed(processes):
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill()
    report = ROOT / args.public_report
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_markdown(result), encoding="utf-8")
    if args.json: print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] or not args.check else 1


def run(tasks_path: Path, output: Path, *, threshold: float) -> dict:
    tasks = _jsonl(tasks_path)
    output.mkdir(parents=True, exist_ok=True)
    calibration = load_calibration(ROOT / "configs/functiongemma-scale789-q8-calibration.json")
    provider = FunctionGemmaAssessmentProvider(
        base_url="http://127.0.0.1:8091/v1", model="functiongemma-q8", calibration=calibration,
        timeout_s=15, max_tokens=64,
    )
    gate = E2BMatrixGate.load(ROOT / "configs/e2b-270m-matrix-regression.json")
    e2b = GemmaE2BRunner(LocalModelClient(base_url="http://127.0.0.1:9379/v1", model="gemma4-e2b", timeout_s=45, max_retries=0), max_tokens=96)
    prediction_path = output / "predictions.jsonl"
    adjudication_path = output / "adjudication.jsonl"
    done = {row["task_id"] for row in _jsonl(prediction_path)}
    predictions = _jsonl(prediction_path)
    adjudications = _jsonl(adjudication_path)
    adjudicated = {row["task_id"] for row in adjudications}
    for index, row in enumerate(tasks, start=1):
        if row["task_id"] in done: continue
        task = TaskEnvelope(id=row["task_id"], input_text=row["prompt"])
        started = time.monotonic()
        try:
            invocation = provider.assess_with_trace(task)
            decision = gate.decide(invocation.raw_assessment)
            assessment = invocation.to_dict()
            error = None
        except FunctionGemmaProviderError as exc:
            decision = None; assessment = None; error = type(exc).__name__
        candidate = e2b.run(task)
        contract = validate_or_safely_repair_final_answer(task, candidate.answer)
        answer = contract.repaired_answer if contract.valid and contract.repaired_answer else candidate.answer
        correct = _evaluate(row["evaluation"], answer)
        prediction = {
            "schema_version":"e2b-boundary-prediction-v1", "task_id":row["task_id"], "category":row["category"],
            "language":row["language"], "output_shape":row["output_shape"], "prompt_sha256":row["prompt_sha256"],
            "assessment":assessment, "probability":decision.probability if decision else 0.0,
            "probe":decision.probe if decision else False, "threshold":threshold, "assessment_error":error,
            "answer":answer, "route":candidate.route, "contract":contract.to_dict(),
            "correct":correct, "elapsed_ms":round((time.monotonic()-started)*1000),
        }
        _append(prediction_path,prediction); predictions.append(prediction); done.add(row["task_id"])
        adjudication={"schema_version":"e2b-boundary-adjudication-v1","task_id":row["task_id"],"evaluation":row["evaluation"],"answer":answer,"correct":correct,"policy":"mechanical_gold_fixed_before_inference"}
        _append(adjudication_path,adjudication); adjudications.append(adjudication); adjudicated.add(row["task_id"])
        if index % 20 == 0: print(json.dumps({"completed":len(predictions),"selected":sum(r["probe"] for r in predictions),"correct":sum(r["correct"] for r in predictions)}),flush=True)
    result = _summarize(tasks,predictions,threshold)
    (output/"summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result


def relabel(tasks_path: Path, output: Path, *, threshold: float) -> dict:
    tasks = _jsonl(tasks_path)
    task_by_id = {row["task_id"]: row for row in tasks}
    prediction_path = output / "predictions.jsonl"
    adjudication_path = output / "adjudication.jsonl"
    predictions = _jsonl(prediction_path)
    if len(predictions) != len(tasks):
        raise ValueError(f"cannot relabel incomplete evidence: {len(predictions)}/{len(tasks)}")
    adjudications = []
    for row in predictions:
        task = task_by_id[row["task_id"]]
        row["correct"] = _evaluate(task["evaluation"], row["answer"])
        adjudications.append({
            "schema_version": "e2b-boundary-adjudication-v1",
            "task_id": row["task_id"],
            "evaluation": task["evaluation"],
            "answer": row["answer"],
            "correct": row["correct"],
            "policy": "mechanical_gold_fixed_before_inference",
        })
    prediction_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in predictions), encoding="utf-8")
    adjudication_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in adjudications), encoding="utf-8")
    result = _summarize(tasks, predictions, threshold)
    (output / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _summarize(tasks, rows, threshold):
    selected=[r for r in rows if r["probability"]>=threshold and r["assessment"] is not None]
    correct=sum(r["correct"] for r in selected)
    by_intent={}
    for intent in sorted({r["assessment"]["raw_assessment"]["intent"] for r in rows if r["assessment"]}):
        cohort=[r for r in selected if r["assessment"]["raw_assessment"]["intent"]==intent]
        by_intent[intent]={"selected":len(cohort),"correct":sum(r["correct"] for r in cohort),"precision":sum(r["correct"] for r in cohort)/len(cohort) if cohort else None}
    bands=[]
    for low,high in BANDS:
        cohort=[r for r in rows if low<=r["probability"]<high and r["assessment"]]
        bands.append({"low":low,"high":high,"rows":len(cohort),"correct":sum(r["correct"] for r in cohort),"precision":sum(r["correct"] for r in cohort)/len(cohort) if cohort else None})
    assess_valid=[r for r in rows if r["assessment"]]
    brier=sum((r["probability"]-float(r["correct"]))**2 for r in assess_valid)/len(assess_valid)
    per_intent_gate=all(v["selected"]<20 or v["precision"]>=.70 for v in by_intent.values())
    checks={
        "all_480_rows_evaluated":len(rows)==len(tasks)==480,
        "unique_unseen_prompt_hashes":len({r["prompt_sha256"] for r in rows})==480,
        "at_least_100_selected":len(selected)>=100,
        "precision_at_least_82pct":correct/len(selected)>=.82 if selected else False,
        "wilson_lower_at_least_75pct":_wilson(correct,len(selected))>=.75,
        "intent_precision_floor":per_intent_gate,
        "assessment_validity_at_least_98pct":len(assess_valid)/len(rows)>=.98,
        "invalid_assessment_routes_fireworks":_malformed_fails_closed(),
    }
    return {"schema_version":"e2b-boundary-audit-v1","passed":all(checks.values()),"threshold":threshold,"rows":len(rows),"selected":len(selected),"correct":correct,"precision":correct/len(selected) if selected else 0.0,"coverage":len(selected)/len(rows),"wilson_lower_95":_wilson(correct,len(selected)),"brier":brier,"bands":bands,"by_intent":by_intent,"checks":checks,"decision":"keep_0.75" if all(checks.values()) else "reject_or_restrict_0.75"}


def _evaluate(spec, answer):
    kind=spec["type"]; expected=spec["expected"]
    clean=answer.strip()
    if kind in {"exact","label"}: return clean.casefold()==str(expected).strip().casefold()
    if kind=="number":
        try:return float(clean)==float(expected)
        except ValueError:return False
    if kind=="json":
        try:return json.loads(clean)==expected
        except (ValueError,TypeError):return False
    if kind=="exact_code": return _canonical_code(clean)==_canonical_code(expected)
    return False


def _canonical_code(source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, TypeError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                node.body.pop(0)
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def _malformed_fails_closed():
    try:
        calibration=load_calibration(ROOT/"configs/functiongemma-scale789-q8-calibration.json")
        provider=FunctionGemmaAssessmentProvider(base_url="http://invalid",model="x",calibration=calibration,requester=lambda _: {"choices":[{"message":{"content":"not a call"}}]})
        provider.assess_with_trace(TaskEnvelope(id="malformed",input_text="test"))
    except FunctionGemmaProviderError:return True
    return False


def _start_local():
    logs=ROOT/"reports/generated/e2b-boundary-v1/runtime";logs.mkdir(parents=True,exist_ok=True)
    fg=subprocess.Popen(["/opt/llama/llama-server","--model","/app/artifacts/functiongemma-scale789/functiongemma-scale789-q8_0.gguf","--alias","functiongemma-q8","--ctx-size","2048","--threads","2","--parallel","1","--host","127.0.0.1","--port","8091","--jinja"],stdout=(logs/"functiongemma.log").open("w"),stderr=subprocess.STDOUT)
    e2b=subprocess.Popen(["python","/app/scripts/litert_cpu_server.py","--host","127.0.0.1","--port","9379","--cpu-threads","2","--max-context-tokens","2048"],stdout=(logs/"e2b.log").open("w"),stderr=subprocess.STDOUT)
    _wait("http://127.0.0.1:8091/health",90);_wait("http://127.0.0.1:9379/v1/models",90)
    return [fg,e2b]


def _wait(url,attempts):
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url,timeout=2):return
        except OSError:time.sleep(1)
    raise RuntimeError(f"local endpoint not ready: {url}")


def _wilson(k,n):
    if not n:return 0.0
    z=1.959963984540054;p=k/n;d=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/d


def _jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _append(path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a") as f:f.write(json.dumps(row,sort_keys=True)+"\n");f.flush();os.fsync(f.fileno())


def _markdown(r):
    lines=["# E2B Boundary Audit","",f"Decision: `{r['decision']}`","",f"- Rows: `{r['rows']}`",f"- Selected at 0.75: `{r['selected']}`",f"- Precision: `{r['precision']:.2%}`",f"- Coverage: `{r['coverage']:.2%}`",f"- Wilson lower 95%: `{r['wilson_lower_95']:.2%}`",f"- Brier score: `{r['brier']:.4f}`","","## Gates",""]
    lines.extend(f"- [{'x' if value else ' '}] `{name}`" for name,value in r["checks"].items())
    lines.extend(["","## Probability Bands",""])
    lines.extend(f"- `{b['low']:.2f}-{b['high']:.2f}`: rows `{b['rows']}`, precision `{b['precision']:.2%}`" if b['precision'] is not None else f"- `{b['low']:.2f}-{b['high']:.2f}`: rows `0`" for b in r["bands"])
    return "\n".join(lines)+"\n"


if __name__=="__main__":raise SystemExit(main())
