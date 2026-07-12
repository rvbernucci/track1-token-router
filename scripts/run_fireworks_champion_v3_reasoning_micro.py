#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, os, sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from router.core.fireworks import FireworksClient
from router.core.model_client import ModelClientError
from scripts.fireworks_microbench import _load_env_files
from scripts.run_fireworks_champion_v3 import AtomicLedger, Budget, MODELS
from scripts.run_fireworks_champion_v3_ablation import SYSTEM, challenger_cap
OUT=ROOT/"reports/generated/fireworks-champion-v3-reasoning-micro"; KIMI,MINIMAX=MODELS
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(p).exists() else []
def subset():
    root=ROOT/"reports/generated/fireworks-champion-v3-ablation"; tasks={x["task_id"]:x for x in rows(root/"tasks.jsonl")}; final={x["task_id"]:x for x in rows(root/"final-verdicts.jsonl")}; none={x["task_id"]:x for x in rows(root/"challenger-responses.jsonl")}; selected=[]
    for category in ("logic_puzzle","math_reasoning"):
        candidates=[tasks[i] for i,x in final.items() if x["category"]==category and x["challenger_correct"] is False]
        candidates.sort(key=lambda x:hashlib.sha256(f"reasoning-low-v1:{x['lineage']}:{x['task_id']}".encode()).hexdigest())
        for x in candidates[:5]:selected.append({**x,"current_answer":none[x["task_id"]]["answer"],"none_usage":none[x["task_id"]]["usage"]})
    return selected
def call(task,key,base):
    client=FireworksClient(base_url=base,model=task["model"],api_key=key,timeout_s=120,max_retries=1); start=perf_counter(); cap=challenger_cap(task)
    try:
        r=client.complete([{"role":"system","content":SYSTEM},{"role":"user","content":task["prompt"]}],temperature=0,max_tokens=cap,extra_body={"reasoning_effort":"low","user":"proofroute-reasoning-micro-v1"})
        return {"task_id":task["task_id"],"model":task["model"],"answer":r.text,"ok":bool(r.text.strip()),"finish_reason":r.raw.get("choices",[{}])[0].get("finish_reason"),"usage":r.usage.to_dict(),"latency_ms":round((perf_counter()-start)*1000,2),"max_tokens":cap,"protocol":"reasoning-low-v1"}
    except ModelClientError as e:return {"task_id":task["task_id"],"model":task["model"],"answer":"","ok":False,"usage":{"prompt":0,"completion":0,"total":0},"error":str(e)[:500],"protocol":"reasoning-low-v1"}
def main():
    p=argparse.ArgumentParser();p.add_argument("--available-credit-usd",type=float,required=True);p.add_argument("--prior-combined-spend-usd",type=float,default=.063982);p.add_argument("--dry-run",action="store_true");a=p.parse_args();ts=subset();OUT.mkdir(parents=True,exist_ok=True);(OUT/"tasks.jsonl").write_text("".join(json.dumps(x,sort_keys=True,ensure_ascii=False)+"\n" for x in ts))
    budget=Budget(1,10,a.available_credit_usd,{KIMI:(.95,4),MINIMAX:(.3,1.2)});out=OUT/"challenger-responses.jsonl";prior=rows(out);done={x["task_id"] for x in prior if x.get("ok")};pending=[x for x in ts if x["task_id"] not in done];spent=sum(budget.cost(x["model"],x["usage"]["prompt"],x["usage"]["completion"]) for x in prior); projected=a.prior_combined_spend_usd+spent+sum(budget.cost(x["model"],math.ceil((len(SYSTEM)+len(x["prompt"]))/3),challenger_cap(x)) for x in pending);print(json.dumps({"tasks":len(ts),"pending":len(pending),"combined_projected_usd":round(projected,6),"hard_cap":1}),flush=True)
    if projected>1:raise SystemExit("combined cap exceeded")
    if a.dry_run:return 0
    _load_env_files((ROOT/".env.fireworks",ROOT/".env.fireworks.local"));key=os.getenv("FIREWORKS_API_KEY");base=os.getenv("FIREWORKS_BASE_URL") or "https://api.fireworks.ai/inference/v1";ledger=AtomicLedger(out)
    for index,task in enumerate(pending):
        result=call(task,key,base)
        if index==0 and not result["ok"]:
            (OUT/"unsupported.json").write_text(json.dumps({"supported":False,"error":result.get("error")},indent=2)+"\n");print("reasoning_effort=low unsupported; stopped after probe");return 3
        ledger.append(result);spent+=budget.cost(result["model"],result["usage"]["prompt"],result["usage"]["completion"]);print(json.dumps({"task_id":result["task_id"],"ok":result["ok"],"combined_spend_usd":round(a.prior_combined_spend_usd+spent,6)}),flush=True)
    (OUT/"unsupported.json").write_text(json.dumps({"supported":True},indent=2)+"\n");return 0
if __name__=="__main__":raise SystemExit(main())
