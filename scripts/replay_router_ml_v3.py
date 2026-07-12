#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]


def score(features: Mapping[str, Any], intent: str, artifact: Mapping[str, Any]) -> dict[str, Any]:
    if intent not in artifact.get("thresholds", {}): return {"route":"fireworks","reason":"unknown_intent","probability":0.0}
    values=[]
    for name,mean,scale in zip(artifact["feature_names"],artifact["normalization"]["mean"],artifact["normalization"]["scale"],strict=True):
        if name not in features: return {"route":"fireworks","reason":"missing_feature","probability":0.0}
        value=float(features[name])
        if not math.isfinite(value): return {"route":"fireworks","reason":"non_finite","probability":0.0}
        values.append((value-float(mean))/float(scale))
    model=artifact["model"]
    if model["kind"]=="logistic": raw=_sigmoid(float(model["weights"][0])+sum(float(w)*v for w,v in zip(model["weights"][1:],values,strict=True)))
    elif model["kind"]=="mlp_tanh":
        hidden=[math.tanh(float(b)+sum(float(w)*v for w,v in zip(weights,values,strict=True))) for weights,b in zip(model["w1"],model["b1"],strict=True)]
        raw=_sigmoid(float(model["b2"])+sum(float(w)*v for w,v in zip(model["w2"],hidden,strict=True)))
    elif model["kind"]=="mlp_dense": raw=_dense(model,values)
    elif model["kind"]=="ensemble": raw=sum(_dense(member,values) for member in model["members"])/len(model["members"])
    else: return {"route":"fireworks","reason":"unknown_model","probability":0.0}
    raw=min(max(raw,1e-7),1-1e-7); cal=artifact["calibration"]
    probability=_sigmoid(float(cal["slope"])*math.log(raw/(1-raw))+float(cal["intercept"]))
    threshold=float(artifact["thresholds"][intent]["threshold"])
    return {"route":"e2b" if probability>=threshold and threshold<1.0 else "fireworks","reason":"selected" if probability>=threshold and threshold<1.0 else "below_threshold","probability":probability,"threshold":threshold}


def _sigmoid(value:float)->float:
    if value>=0: z=math.exp(-min(value,40)); return 1/(1+z)
    z=math.exp(max(value,-40)); return z/(1+z)


def _dense(model:Mapping[str,Any],row:Sequence[float])->float:
    values=list(row)
    for index,layer in enumerate(model["layers"]):
        values=[float(b)+sum(float(w)*value for w,value in zip(weights,values,strict=True)) for weights,b in zip(layer["weights"],layer["bias"],strict=True)]
        if index<len(model["layers"])-1:
            if model["activation"]=="tanh": values=[math.tanh(value) for value in values]
            elif model["activation"]=="relu": values=[max(0.0,value) for value in values]
            else: values=[0.5*value*(1+math.erf(value/math.sqrt(2))) for value in values]
    return _sigmoid(values[0])


def _jsonl(path:Path)->list[dict[str,Any]]:
    with path.open(encoding="utf-8") as handle:return [json.loads(line) for line in handle if line.strip()]


def _summary(rows:Sequence[Mapping[str,Any]],decisions:Sequence[Mapping[str,Any]])->dict[str,Any]:
    result={}
    cohorts={"uniform":list(range(len(rows)))}
    for category in sorted({str(row["category"]) for row in rows}): cohorts[category]=[i for i,row in enumerate(rows) if row["category"]==category]
    for name,indexes in cohorts.items():
        selected=[i for i in indexes if decisions[i]["route"]=="e2b"]; labelled=[i for i in selected if rows[i]["targets"]["e2b"] is not None]; correct=sum(int(rows[i]["targets"]["e2b"]) for i in labelled)
        result[name]={"population":len(indexes),"selected":len(selected),"coverage":len(selected)/len(indexes) if indexes else 0.0,"labelled_selected":len(labelled),"precision":correct/len(labelled) if labelled else None,"estimated_fireworks_tokens_saved":sum(max(1,int(math.exp(float(rows[i]["features"].get("mechanical.prompt_tokens_log",0)))-1))+96 for i in selected)}
    return result


def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--ledger",type=Path,default=ROOT/"evals/router-ml-v3/ledger.jsonl"); parser.add_argument("--model",type=Path,default=ROOT/"evals/router-ml-v3/candidate.json"); parser.add_argument("--role",choices=("fit","calibration","protected_holdout","development"),default="development"); parser.add_argument("--output",type=Path,default=ROOT/"reports/generated/router-ml-v3/replay.json"); parser.add_argument("--protected-labels",type=Path,nargs="*")
    args=parser.parse_args(); rows=_jsonl(args.ledger); artifact=json.loads(args.model.read_text())
    selected=[row for row in rows if (row["role"] in {"fit","calibration"} if args.role=="development" else row["role"]==args.role)]
    if args.protected_labels:
        if args.role!="protected_holdout": raise ValueError("external protected labels may only be opened for protected_holdout replay")
        labels={str(row["task_id"]):int(row["binary_label"]) for path in args.protected_labels for row in _jsonl(path)}
        if set(labels)!={str(row["task_id"]) for row in selected}: raise ValueError("protected label IDs do not exactly match the protected ledger cohort")
        selected=[{**row,"targets":{**row["targets"],"e2b":labels[str(row["task_id"])]}} for row in selected]
    decisions=[score(row["features"],row["intent"],artifact) if row["assessment_valid"] else {"route":"fireworks","reason":"missing_assessment","probability":0.0} for row in selected]
    report={"schema_version":"router-ml-v3-replay-v1","role":args.role,"protected_labels_opened":bool(args.protected_labels),"rows":len(selected),"cohorts":_summary(selected,decisions),"fail_closed":{reason:sum(item["reason"]==reason for item in decisions) for reason in sorted({item["reason"] for item in decisions})}}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps(report["cohorts"]["uniform"],sort_keys=True)); return 0


if __name__=="__main__":raise SystemExit(main())
