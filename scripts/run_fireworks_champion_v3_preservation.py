#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.fireworks_microbench import _load_env_files
from scripts.run_fireworks_champion_v3 import AtomicLedger, Budget, MODELS
from scripts.run_fireworks_champion_v3_ablation import SYSTEM, _call, challenger_cap

OUT=ROOT/"reports/generated/fireworks-champion-v3-preservation"
KIMI,MINIMAX=MODELS
CHAMPIONS={"code_debugging":KIMI,"code_generation":KIMI,"factual_qa":KIMI,"logic_puzzle":MINIMAX,"math_reasoning":MINIMAX,"ner":MINIMAX,"sentiment":MINIMAX,"summarization":MINIMAX}

def rows(path:Path): return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []
def build_subset():
    tasks={x["task_id"]:x for x in rows(ROOT/"evals/fireworks-champion-v3/tasks.jsonl")}; verdicts={(x["task_id"],x["model"]):x for x in rows(ROOT/"reports/generated/fireworks-champion-v3/final-verdicts.jsonl")}; responses={(x["task_id"],x["model"]):x for x in rows(ROOT/"reports/generated/fireworks-champion-v3/responses.jsonl")}
    selected=[]
    for category,model in sorted(CHAMPIONS.items()):
        candidates=[x for x in tasks.values() if x["category"]==category and verdicts[x["task_id"],model]["correct"] is True]
        candidates.sort(key=lambda x:hashlib.sha256(f"preservation-v1:{x['lineage']}:{x['task_id']}".encode()).hexdigest())
        used=set()
        for item in candidates:
            key=(item["source"],item["lineage"])
            if key in used: continue
            used.add(key); selected.append({**item,"model":model,"current_answer":responses[item["task_id"],model]["answer"]})
            if len(used)==10: break
        if len(used)!=10: raise ValueError(f"insufficient baseline-correct lineages: {category}")
    return selected

def main():
    p=argparse.ArgumentParser(); p.add_argument("--available-credit-usd",type=float,required=True); p.add_argument("--prior-combined-spend-usd",type=float,default=.047684); p.add_argument("--hard-combined-budget-usd",type=float,default=1); p.add_argument("--workers",type=int,default=3); p.add_argument("--dry-run",action="store_true"); a=p.parse_args()
    tasks=build_subset(); OUT.mkdir(parents=True,exist_ok=True); (OUT/"tasks.jsonl").write_text("".join(json.dumps(x,sort_keys=True,ensure_ascii=False)+"\n" for x in tasks),encoding="utf-8")
    budget=Budget(a.hard_combined_budget_usd,10,a.available_credit_usd,{KIMI:(.95,4),MINIMAX:(.3,1.2)}); output=OUT/"challenger-responses.jsonl"; prior=rows(output); done={x["task_id"] for x in prior if x.get("ok")}; pending=[x for x in tasks if x["task_id"] not in done]
    preservation_spend=sum(budget.cost(x["model"],x["usage"]["prompt"],x["usage"]["completion"]) for x in prior); projected=a.prior_combined_spend_usd+preservation_spend+sum(budget.cost(x["model"],math.ceil((len(SYSTEM)+len(x["prompt"]))/3),challenger_cap(x)) for x in pending)
    print(json.dumps({"tasks":len(tasks),"pending":len(pending),"prior_combined_spend_usd":a.prior_combined_spend_usd,"preservation_spend_usd":round(preservation_spend,6),"conservative_combined_projected_usd":round(projected,6),"hard_combined_budget_usd":a.hard_combined_budget_usd}),flush=True)
    if projected>a.hard_combined_budget_usd: raise SystemExit("combined preflight exceeds hard cap")
    if a.dry_run:return 0
    _load_env_files((ROOT/".env.fireworks",ROOT/".env.fireworks.local")); key=os.getenv("FIREWORKS_API_KEY"); base=os.getenv("FIREWORKS_BASE_URL") or "https://api.fireworks.ai/inference/v1"
    if not key: raise SystemExit("FIREWORKS_API_KEY not set")
    ledger=AtomicLedger(output)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futures={ex.submit(_call,x,key,base,120):x for x in pending}
        for future in as_completed(futures):
            result=future.result(); cost=budget.cost(result["model"],result["usage"]["prompt"],result["usage"]["completion"])
            preservation_spend+=cost
            if a.prior_combined_spend_usd+preservation_spend>a.hard_combined_budget_usd: raise SystemExit("combined hard cap reached")
            ledger.append(result); print(json.dumps({"task_id":result["task_id"],"ok":result["ok"],"combined_spend_usd":round(a.prior_combined_spend_usd+preservation_spend,6)}),flush=True)
    return 0
if __name__=="__main__":raise SystemExit(main())
