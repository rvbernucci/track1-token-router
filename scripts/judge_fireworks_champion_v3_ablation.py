#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, random, sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"reports/generated/fireworks-champion-v3-ablation"
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.judge_fireworks_champion_v3 import _references, deterministic_verdict

def rows(path:Path)->list[dict[str,Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []
def write(path:Path,data:list[dict[str,Any]]):
    tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text("".join(json.dumps(x,sort_keys=True,ensure_ascii=False)+"\n" for x in data),encoding="utf-8"); tmp.replace(path)

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--codex-judgments",type=Path); p.add_argument("--output-root",type=Path,default=OUT); p.add_argument("--frozen-baseline-correct",action="store_true"); a=p.parse_args(); out=a.output_root if a.output_root.is_absolute() else ROOT/a.output_root
    tasks={x["task_id"]:x for x in rows(out/"tasks.jsonl")}; challengers={x["task_id"]:x for x in rows(out/"challenger-responses.jsonl")}
    refs=_references(); rng=random.Random(760760); queue=[]; key={}; mechanical=[]
    for task_id in sorted(tasks):
        task=tasks[task_id]; response=challengers[task_id]; verdict=deterministic_verdict(task,response,refs[task_id]); mechanical.append({"task_id":task_id,**verdict})
        if verdict["hard"]: continue
        candidates=[("current",task["current_answer"]),("challenger",response["answer"])]; rng.shuffle(candidates)
        blind_id=hashlib.sha256(f"ablation-v1:{task_id}".encode()).hexdigest()[:20]
        queue.append({"schema_version":"fireworks-champion-v3-blind-judge-v1","blind_id":blind_id,"task_id":task_id,"category":task["category"],"split":task["split"],
          "prompt":task["prompt"],"reference_answer":refs[task_id].get("reference_answer"),"reference_rubric":refs[task_id].get("reference_rubric"),
          "candidate_a":candidates[0][1],"candidate_b":candidates[1][1],"instruction":"Judge each candidate independently."})
        key[blind_id]={"candidate_a":candidates[0][0],"candidate_b":candidates[1][0]}
    write(out/"mechanical-verdicts.jsonl",mechanical); write(out/"codex-blind-queue.jsonl",queue); (out/"blind-key.json").write_text(json.dumps(key,indent=2,sort_keys=True)+"\n")
    judgments={x["blind_id"]:x for x in rows(a.codex_judgments) } if a.codex_judgments else {}
    final=[]
    for task_id in sorted(tasks):
        mech=next(x for x in mechanical if x["task_id"]==task_id); current=False
        if mech["hard"]: challenger=mech["verdict"]=="correct"; evidence="mechanical"
        else:
            blind=next(x for x in queue if x["task_id"]==task_id); judgment=judgments.get(blind["blind_id"])
            if not judgment: challenger=None; evidence="pending_codex"
            else:
                side="a" if key[blind["blind_id"]]["candidate_a"]=="challenger" else "b"; challenger=bool(judgment[f"valid_{side}"]); evidence="blind_codex"
                current_side="b" if side=="a" else "a"; current=bool(judgment[f"valid_{current_side}"])
        frozen_correct = bool(tasks[task_id].get("current_frozen_correct", a.frozen_baseline_correct))
        final.append({"task_id":task_id,"category":tasks[task_id]["category"],"current_frozen_correct":frozen_correct,"current_rejudged_correct":current,"challenger_correct":challenger,"evidence":evidence})
    write(out/"final-verdicts.jsonl",final)
    complete=all(x["challenger_correct"] is not None for x in final); bycat={}
    for cat in sorted({x["category"] for x in final}):
        group=[x for x in final if x["category"]==cat]; bycat[cat]={"tasks":len(group),"challenger_correct":sum(x["challenger_correct"] is True for x in group),"frozen_baseline_correct":sum(x["current_frozen_correct"] is True for x in group),"regressions_vs_frozen_baseline":sum(x["challenger_correct"] is False and x["current_frozen_correct"] for x in group)}
    responses=list(challengers.values()); summary={"complete":complete,"tasks":len(final),"codex_queue":len(queue),"codex_completed":len(judgments),"challenger_correct":sum(x["challenger_correct"] is True for x in final),"current_frozen_correct":sum(x["current_frozen_correct"] is True for x in final),"current_rejudged_correct":sum(x["current_rejudged_correct"] is True for x in final),"by_category":bycat,"challenger_tokens":sum(x["usage"]["total"] for x in responses),"challenger_prompt_tokens":sum(x["usage"]["prompt"] for x in responses),"challenger_completion_tokens":sum(x["usage"]["completion"] for x in responses)}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n"); print(json.dumps(summary,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
