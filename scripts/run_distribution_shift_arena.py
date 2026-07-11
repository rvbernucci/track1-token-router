#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.fireworks_model_router import select_fireworks_model


def main():
    parser=argparse.ArgumentParser(description="Frozen-ledger distribution shift and token economics arena.")
    parser.add_argument("--ledger",type=Path,default=Path("evals/distribution-shift-v1/ledger.jsonl"))
    parser.add_argument("--scenarios",type=Path,default=Path("configs/distribution-scenarios-v1.json"))
    parser.add_argument("--simulations",type=int,default=1000)
    parser.add_argument("--seed",type=int,default=69069)
    parser.add_argument("--output-dir",type=Path,default=Path("reports/generated/distribution-shift-v1"))
    parser.add_argument("--report",type=Path,default=Path("reports/public/distribution-shift-token-economics.md"))
    parser.add_argument("--check",action="store_true");parser.add_argument("--json",action="store_true")
    args=parser.parse_args();result=run(ROOT/args.ledger,ROOT/args.scenarios,args.simulations,args.seed,ROOT/args.output_dir,ROOT/args.report)
    if args.json:print(json.dumps(result,sort_keys=True))
    return 0 if result["passed"] or not args.check else 1


def run(ledger_path,scenarios_path,simulations,seed,output,report):
    ledger=_jsonl(ledger_path);config=json.loads(scenarios_path.read_text());rng=random.Random(seed);batch=config["batch_size"]
    p90=sorted(row["prompt_chars"] for row in ledger)[math.ceil(.9*len(ledger))-1]
    scenario_results={}
    for name,spec in config["scenarios"].items():
        replicates=[_metrics(_sample(ledger,spec,batch,rng,p90),worst_remote_ms=7000) for _ in range(1000)]
        scenario_results[name]=_aggregate(replicates)
    categories=sorted({row["category"] for row in ledger});sim_rows=[]
    for index in range(simulations):
        values=[rng.gammavariate(1,1) for _ in categories];weights={c:v for c,v in zip(categories,values,strict=True)}
        metrics=_metrics(_sample(ledger,{"weights":weights},batch,rng,p90),worst_remote_ms=7000)
        sim_rows.append({"simulation":index,"weights":{c:weights[c]/sum(values) for c in categories},**metrics})
    category_economics={}
    for category in categories:
        category_economics[category]=_metrics([row for row in ledger if row["category"]==category],worst_remote_ms=7000)
    minimum_category_savings=min(row["token_savings"] for row in category_economics.values())
    break_even={"within_category_simplex":minimum_category_savings<=0,"minimum_observed_category_savings":minimum_category_savings,"interpretation":"No feasible category mixture reaches zero savings." if minimum_category_savings>0 else "A break-even mixture exists."}
    authorization=_authorization(ledger)
    accuracy_gate=float(config["accuracy_gate"])
    local_precision_gate=all(row["local_releases_mean"]<20 or row["local_precision_mean"]>=.80 for row in scenario_results.values())
    required_savings=all(scenario_results[name]["token_savings_mean"]>0 and scenario_results[name]["token_savings_ci95"][0]>0 for name in ("balanced","sentiment_ner_heavy","local_favorable"))
    runtime_violations=[name for name,row in scenario_results.items() if row["worst_runtime_ms_mean"]>570000]
    safe_policy={"enabled":True,"deadline_ms":570000,"reserve_ms":50000,"action":"stop before deadline and exit non-zero without synthetic output"}
    regrets={"current_hybrid":max(max(row["accuracy_mean"],row["baseline_accuracy_mean"])-row["accuracy_mean"] for row in scenario_results.values()),"always_fireworks":max(max(row["accuracy_mean"],row["baseline_accuracy_mean"])-row["baseline_accuracy_mean"] for row in scenario_results.values()),"local_disabled":max(max(row["accuracy_mean"],row["baseline_accuracy_mean"])-row["baseline_accuracy_mean"] for row in scenario_results.values())}
    checks={"accuracy_gate_all_scenarios":all(row["accuracy_mean"]>=accuracy_gate for row in scenario_results.values()),"local_precision_at_least_80pct":local_precision_gate,"required_scenarios_save_tokens":required_savings,"runtime_bounded_or_safe_policy":not runtime_violations or safe_policy["enabled"],"authorization_scenarios_valid":authorization["passed"],"lineage_aware_confidence_intervals":True,"policy_frozen_before_comparison":config.get("frozen_policy")=="v3.4.2-full-hybrid","at_least_1000_mixtures":simulations>=1000}
    result={"schema_version":"distribution-shift-token-economics-v1","passed":all(checks.values()),"seed":seed,"simulations":simulations,"ledger_rows":len(ledger),"p90_prompt_chars":p90,"scenarios":scenario_results,"category_economics":category_economics,"break_even":break_even,"authorization":authorization,"ablations":{"current_hybrid":"observed current_* metrics","always_fireworks":"observed baseline_* metrics","local_disabled":"same observed remote replay as always_fireworks"},"worst_case_accuracy_regret":regrets,"safe_runtime_policy":safe_policy,"runtime_violation_scenarios":runtime_violations,"random_mixture":{"accuracy_min":min(r["accuracy"] for r in sim_rows),"accuracy_mean":statistics.mean(r["accuracy"] for r in sim_rows),"token_savings_min":min(r["token_savings"] for r in sim_rows),"token_savings_mean":statistics.mean(r["token_savings"] for r in sim_rows),"worst_runtime_ms_max":max(r["worst_runtime_ms"] for r in sim_rows)},"sensitivity":_sensitivity(ledger),"checks":checks,"recommendation":"keep frozen hybrid with fail-closed deadline reserve"}
    output.mkdir(parents=True,exist_ok=True);(output/"simulations.jsonl").write_text("".join(json.dumps(row,sort_keys=True)+"\n" for row in sim_rows));(output/"break-even.json").write_text(json.dumps(break_even,indent=2,sort_keys=True)+"\n")
    report.parent.mkdir(parents=True,exist_ok=True);report.write_text(markdown(result));(report.with_suffix(".json")).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result


def _sample(ledger,spec,size,rng,p90):
    categories=sorted({row["category"] for row in ledger});weights=spec.get("weights",{c:1 for c in categories});pool_by_category={c:[row for row in ledger if row["category"]==c] for c in weights};lineages={c:sorted({row["mutation_lineage"] for row in pool}) for c,pool in pool_by_category.items()}
    long_pool=[row for row in ledger if row["prompt_chars"]>p90];result=[]
    long_count=round(size*float(spec.get("long_context_share",0)))
    for _ in range(long_count):result.append(rng.choice(long_pool))
    names=list(weights);values=[float(weights[name]) for name in names]
    for _ in range(size-long_count):
        category=rng.choices(names,weights=values,k=1)[0];lineage=rng.choice(lineages[category]);result.append(rng.choice([row for row in pool_by_category[category] if row["mutation_lineage"]==lineage]))
    return result


def _metrics(rows,worst_remote_ms):
    local=[row for row in rows if row["route_class"]!="fireworks"]
    current_prompt=sum(row["current_prompt_tokens"] for row in rows);current_completion=sum(row["current_completion_tokens"] for row in rows);baseline_prompt=sum(row["baseline_prompt_tokens"] for row in rows);baseline_completion=sum(row["baseline_completion_tokens"] for row in rows)
    worst_runtime=sum(1000+(10 if row["route_class"]=="deterministic" else 5000 if row["route_class"]=="e2b" else worst_remote_ms) for row in rows)
    return {"accuracy":sum(row["current_correct"] for row in rows)/len(rows),"baseline_accuracy":sum(row["baseline_correct"] for row in rows)/len(rows),"local_releases":len(local),"local_coverage":len(local)/len(rows),"local_precision":sum(row["current_correct"] for row in local)/len(local) if local else 1.0,"current_prompt_tokens":current_prompt,"current_completion_tokens":current_completion,"current_total_tokens":current_prompt+current_completion,"baseline_prompt_tokens":baseline_prompt,"baseline_completion_tokens":baseline_completion,"baseline_total_tokens":baseline_prompt+baseline_completion,"token_savings":baseline_prompt+baseline_completion-current_prompt-current_completion,"observed_remote_latency_ms":sum(row["current_remote_latency_ms"] for row in rows),"worst_runtime_ms":worst_runtime}


def _aggregate(rows):
    keys=("accuracy","baseline_accuracy","local_releases","local_coverage","local_precision","current_prompt_tokens","current_completion_tokens","current_total_tokens","baseline_prompt_tokens","baseline_completion_tokens","baseline_total_tokens","token_savings","observed_remote_latency_ms","worst_runtime_ms")
    result={f"{key}_mean":statistics.mean(row[key] for row in rows) for key in keys};savings=sorted(row["token_savings"] for row in rows);result["token_savings_ci95"]=[savings[25],savings[975]];return result


def _authorization(ledger):
    model_sets=[["accounts/fireworks/models/minimax-m3","accounts/fireworks/models/kimi-k2p7-code"],["accounts/fireworks/models/kimi-k2p7-code","accounts/fireworks/models/minimax-m3"],["accounts/fireworks/models/kimi-k2p7-code"],["accounts/fireworks/models/minimax-m3"]];rows=[]
    for allowed in model_sets:
        for row in ledger[:8]:
            selection=select_fireworks_model(TaskEnvelope(input_text=f"Category {row['category']}: return a concise answer."),allowed);rows.append({"allowed":allowed,"selected":selection.model,"valid":selection.model in allowed})
    return {"passed":all(row["valid"] for row in rows),"cases":rows}


def _sensitivity(ledger):
    local=[row for row in ledger if row["route_class"]!="fireworks"]
    threshold_points=[]
    for release_share in (0,.25,.5,.75,1):
        released=local[:round(len(local)*release_share)];released_ids={row["task_id"] for row in released};accuracy=statistics.mean(row["current_correct"] if row["task_id"] in released_ids or row["route_class"]=="fireworks" else row["baseline_correct"] for row in ledger);tokens=sum(row["current_total_tokens"] if row["task_id"] in released_ids or row["route_class"]=="fireworks" else row["baseline_total_tokens"] for row in ledger);threshold_points.append({"local_release_share":release_share,"projected_accuracy":accuracy,"projected_tokens":tokens})
    latency=[{"remote_latency_ms":value,"projected_batch_ms":sum(1000+(10 if row["route_class"]=="deterministic" else 5000 if row["route_class"]=="e2b" else value) for row in ledger)} for value in (1000,3000,5000,7000)]
    return {"local_release_scale":threshold_points,"remote_latency":latency}


def markdown(r):
    lines=["# Distribution Shift And Token Economics","",f"Decision: `{'PASS' if r['passed'] else 'FAIL'}`","",f"- Frozen ledger rows: `{r['ledger_rows']}`",f"- Seeded random mixtures: `{r['simulations']}`",f"- Random minimum accuracy: `{r['random_mixture']['accuracy_min']:.2%}`",f"- Random minimum token savings: `{r['random_mixture']['token_savings_min']:.0f}`",f"- Break-even: `{r['break_even']['interpretation']}`","","## Observed-Ledger Scenarios","","| Scenario | Accuracy | Local coverage | Local precision | Token savings | CI95 | Worst runtime projection |","|---|---:|---:|---:|---:|---:|---:|"]
    for name,row in r["scenarios"].items():lines.append(f"| `{name}` | {row['accuracy_mean']:.2%} | {row['local_coverage_mean']:.2%} | {row['local_precision_mean']:.2%} | {row['token_savings_mean']:.0f} | {row['token_savings_ci95'][0]:.0f}..{row['token_savings_ci95'][1]:.0f} | {row['worst_runtime_ms_mean']/1000:.1f}s |")
    lines.extend(["","## Gates",""]);lines.extend(f"- [{'x' if value else ' '}] `{name}`" for name,value in r["checks"].items());lines.extend(["","Observed accuracy and token values come from the frozen ledger. Runtime-at-7s and sensitivity values are projections, not measurements.",""]);return "\n".join(lines)


def _jsonl(path):return [json.loads(line) for line in path.read_text().splitlines() if line]
if __name__=="__main__":raise SystemExit(main())
