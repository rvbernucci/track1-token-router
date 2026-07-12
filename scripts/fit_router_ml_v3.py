#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
EPS = 1e-7


def _rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-min(value, 40.0)); return 1.0 / (1.0 + z)
    z = math.exp(max(value, -40.0)); return z / (1.0 + z)


def _hash_fold(value: str, folds: int) -> int:
    return int(hashlib.sha256(value.encode()).hexdigest()[:12], 16) % folds


def _wilson(correct: int, total: int, z: float = 1.6448536269514722) -> float:
    if not total: return 0.0
    p = correct / total; d = 1 + z * z / total
    return (p + z*z/(2*total) - z*math.sqrt((p*(1-p)+z*z/(4*total))/total)) / d


def _metrics(y: Sequence[int], p: Sequence[float]) -> dict[str, float]:
    if not y: return {name: 0.0 for name in ("brier", "log_loss", "auroc", "average_precision", "ece")}
    brier = sum((a-b)**2 for a,b in zip(y,p,strict=True))/len(y)
    loss = -sum(a*math.log(max(EPS,b))+(1-a)*math.log(max(EPS,1-b)) for a,b in zip(y,p,strict=True))/len(y)
    order = sorted(range(len(y)), key=lambda i: p[i], reverse=True)
    positives=sum(y); negatives=len(y)-positives; tp=fp=0; prev_tp=prev_fp=0; auc=0.0; ap=0.0
    for i in order:
        if y[i]: tp+=1; ap += tp/(tp+fp)
        else: fp+=1; auc += tp
    auroc=auc/(positives*negatives) if positives and negatives else 0.5
    ap=ap/positives if positives else 0.0
    bins=[[] for _ in range(10)]
    for a,b in zip(y,p,strict=True): bins[min(9,int(b*10))].append((a,b))
    ece=sum(len(bucket)/len(y)*abs(sum(a for a,_ in bucket)/len(bucket)-sum(b for _,b in bucket)/len(bucket)) for bucket in bins if bucket)
    return {"brier":brier,"log_loss":loss,"auroc":auroc,"average_precision":ap,"ece":ece}


class Standardizer:
    def fit(self, x: Sequence[Sequence[float]]) -> "Standardizer":
        self.mean=[sum(row[j] for row in x)/len(x) for j in range(len(x[0]))]
        self.scale=[max(math.sqrt(sum((row[j]-self.mean[j])**2 for row in x)/len(x)),1e-6) for j in range(len(x[0]))]
        return self
    def transform(self, x: Sequence[Sequence[float]]) -> list[list[float]]:
        return [[(v-m)/s for v,m,s in zip(row,self.mean,self.scale,strict=True)] for row in x]


class Logistic:
    def __init__(self, dimensions: int): self.weights=[0.0]*(dimensions+1)
    def fit(self,x:Sequence[Sequence[float]],y:Sequence[int],epochs:int=350,lr:float=.08,l2:float=.01)->"Logistic":
        pos=max(1,sum(y)); neg=max(1,len(y)-sum(y))
        for epoch in range(epochs):
            grad=[0.0]*len(self.weights)
            for row,target in zip(x,y,strict=True):
                prob=self.predict_one(row); weight=(len(y)/(2*pos) if target else len(y)/(2*neg)); error=(prob-target)*weight
                grad[0]+=error
                for j,v in enumerate(row,1): grad[j]+=error*v
            rate=lr/math.sqrt(1+epoch/50)
            for j in range(len(self.weights)): self.weights[j]-=rate*(grad[j]/len(y)+(l2*self.weights[j] if j else 0))
        return self
    def predict_one(self,row:Sequence[float])->float:return _sigmoid(self.weights[0]+sum(w*v for w,v in zip(self.weights[1:],row,strict=True)))
    def predict(self,x:Sequence[Sequence[float]])->list[float]:return [self.predict_one(row) for row in x]
    def export(self)->dict[str,Any]:return {"kind":"logistic","weights":self.weights}


class MLP:
    def __init__(self, dimensions:int, hidden:int, seed:int=77):
        rng=random.Random(seed); scale=math.sqrt(2/max(1,dimensions))
        self.w1=[[rng.uniform(-scale,scale) for _ in range(dimensions)] for _ in range(hidden)]; self.b1=[0.0]*hidden
        self.w2=[rng.uniform(-.1,.1) for _ in range(hidden)]; self.b2=0.0
    def _forward(self,row:Sequence[float])->tuple[list[float],float]:
        hidden=[math.tanh(b+sum(w*v for w,v in zip(weights,row,strict=True))) for weights,b in zip(self.w1,self.b1,strict=True)]
        return hidden,_sigmoid(self.b2+sum(w*v for w,v in zip(self.w2,hidden,strict=True)))
    def fit(self,x:Sequence[Sequence[float]],y:Sequence[int],epochs:int=180,lr:float=.025,l2:float=.002)->"MLP":
        pos=max(1,sum(y)); neg=max(1,len(y)-sum(y))
        for epoch in range(epochs):
            gw1=[[0.0]*len(x[0]) for _ in self.w1]; gb1=[0.0]*len(self.b1); gw2=[0.0]*len(self.w2); gb2=0.0
            for row,target in zip(x,y,strict=True):
                hidden,prob=self._forward(row); sample=(len(y)/(2*pos) if target else len(y)/(2*neg)); dz=(prob-target)*sample; gb2+=dz
                old_w2=self.w2[:]
                for h,value in enumerate(hidden): gw2[h]+=dz*value
                for h,value in enumerate(hidden):
                    dh=dz*old_w2[h]*(1-value*value); gb1[h]+=dh
                    for j,v in enumerate(row): gw1[h][j]+=dh*v
            rate=lr/math.sqrt(1+epoch/40); n=len(y)
            self.b2-=rate*gb2/n
            for h in range(len(self.w2)):
                self.w2[h]-=rate*(gw2[h]/n+l2*self.w2[h]); self.b1[h]-=rate*gb1[h]/n
                for j in range(len(self.w1[h])): self.w1[h][j]-=rate*(gw1[h][j]/n+l2*self.w1[h][j])
        return self
    def predict(self,x:Sequence[Sequence[float]])->list[float]:return [self._forward(row)[1] for row in x]
    def export(self)->dict[str,Any]:return {"kind":"mlp_tanh","w1":self.w1,"b1":self.b1,"w2":self.w2,"b2":self.b2}


def _platt(raw:Sequence[float],y:Sequence[int])->tuple[float,float]:
    logits=[math.log(max(EPS,p)/max(EPS,1-p)) for p in raw]; model=Logistic(1).fit([[v] for v in logits],y,epochs=500,lr=.04,l2=.001)
    return model.weights[1],model.weights[0]


def _calibrate(raw:Sequence[float],cal:tuple[float,float])->list[float]:
    a,b=cal; return [_sigmoid(a*math.log(max(EPS,p)/max(EPS,1-p))+b) for p in raw]


def _thresholds(
    rows: Sequence[Mapping[str, Any]],
    probabilities: Sequence[float],
    *,
    minimum_support: int = 15,
    minimum_precision: float = 0.95,
    minimum_wilson: float = 0.85,
) -> dict[str, Any]:
    result={}
    for intent in sorted({str(row["intent"]) for row in rows}):
        pairs=[(row,p) for row,p in zip(rows,probabilities,strict=True) if row["intent"]==intent]
        best=None
        for threshold in sorted({round(p,6) for _,p in pairs}):
            chosen=[row for row,p in pairs if p>=threshold]; total=len(chosen); correct=sum(int(row["targets"]["e2b"]) for row in chosen)
            candidate={"threshold":threshold,"selected":total,"correct":correct,"precision":correct/total if total else 0.0,"coverage":total/len(pairs),"wilson_lower_90":_wilson(correct,total)}
            eligible=(
                total >= minimum_support
                and candidate["precision"] >= minimum_precision
                and candidate["wilson_lower_90"] >= minimum_wilson
            )
            if eligible and (best is None or (total,candidate["precision"])>(best["selected"],best["precision"])): best=candidate
        result[intent]=best or {"threshold":1.0,"selected":0,"correct":0,"precision":0.0,"coverage":0.0,"wilson_lower_90":0.0}
    return result


def _category_coverage(rows:Sequence[Mapping[str,Any]],probabilities:Sequence[float],thresholds:Mapping[str,Mapping[str,Any]])->dict[str,Any]:
    result={}
    for category in sorted({str(row["category"]) for row in rows}):
        pairs=[(row,p) for row,p in zip(rows,probabilities,strict=True) if row["category"]==category]
        selected=[row for row,p in pairs if p>=float(thresholds[str(row["intent"])]["threshold"]) and float(thresholds[str(row["intent"])]["threshold"])<1.0]
        correct=sum(int(row["targets"]["e2b"]) for row in selected)
        result[category]={"population":len(pairs),"selected":len(selected),"coverage":len(selected)/len(pairs) if pairs else 0.0,"precision":correct/len(selected) if selected else None}
    return result


def _matrix(rows:Sequence[Mapping[str,Any]],names:Sequence[str])->list[list[float]]: return [[float(row["features"].get(name,0.0)) for name in names] for row in rows]


def _fit_candidate(kind:str,x:list[list[float]],y:list[int],hidden:int,epochs:int):
    return (Logistic(len(x[0])).fit(x,y) if kind=="logistic" else MLP(len(x[0]),hidden).fit(x,y,epochs=epochs))


class TorchMLP:
    def __init__(self, dimensions:int, hidden:int, device:str, *, activation:str="tanh", layers:int=1, dropout:float=0.0, seed:int=77):
        import torch
        torch.manual_seed(seed); self.torch=torch; self.device=torch.device(device); self.activation=activation
        activation_factory={"tanh":torch.nn.Tanh,"relu":torch.nn.ReLU,"gelu":torch.nn.GELU}[activation]
        modules=[]; width=dimensions
        for _ in range(layers):
            modules.extend((torch.nn.Linear(width,hidden),activation_factory()))
            if dropout: modules.append(torch.nn.Dropout(dropout))
            width=hidden
        modules.append(torch.nn.Linear(width,1)); self.network=torch.nn.Sequential(*modules).to(self.device)
    def fit(self,x:Sequence[Sequence[float]],y:Sequence[int],epochs:int=500,lr:float=.01,l2:float=.002)->"TorchMLP":
        torch=self.torch; inputs=torch.tensor(x,dtype=torch.float32,device=self.device); targets=torch.tensor(y,dtype=torch.float32,device=self.device).reshape(-1,1)
        positives=max(1,sum(y)); negatives=max(1,len(y)-sum(y)); weights=torch.where(targets>0,len(y)/(2*positives),len(y)/(2*negatives))
        optimizer=torch.optim.AdamW(self.network.parameters(),lr=lr,weight_decay=l2)
        best=None; stale=0
        for _ in range(epochs):
            optimizer.zero_grad(set_to_none=True); logits=self.network(inputs); loss=torch.nn.functional.binary_cross_entropy_with_logits(logits,targets,weight=weights); loss.backward(); optimizer.step()
            value=float(loss.detach().cpu())
            if best is None or value<best-1e-6: best=value; stale=0
            else: stale+=1
            if stale>=40: break
        self.network.eval(); return self
    def predict(self,x:Sequence[Sequence[float]])->list[float]:
        torch=self.torch
        with torch.no_grad(): return torch.sigmoid(self.network(torch.tensor(x,dtype=torch.float32,device=self.device))).flatten().cpu().tolist()
    def export(self)->dict[str,Any]:
        layers=[]
        for module in self.network:
            if module.__class__.__name__=="Linear": layers.append({"weights":module.weight.detach().cpu().tolist(),"bias":module.bias.detach().cpu().tolist()})
        return {"kind":"mlp_dense","activation":self.activation,"layers":layers}


def _candidate(kind:str,x:list[list[float]],y:list[int],hidden:int,epochs:int,backend:str,device:str):
    if kind=="logistic": return Logistic(len(x[0])).fit(x,y)
    if backend=="torch": return TorchMLP(len(x[0]),hidden,device).fit(x,y,epochs=epochs)
    return MLP(len(x[0]),hidden).fit(x,y,epochs=epochs)


def _sweep_configs(limit:int)->list[dict[str,Any]]:
    values=[]
    for index in range(max(limit,24)):
        values.append({"hidden":(8,16,32,64)[index%4],"activation":("tanh","relu","gelu")[index%3],"layers":(1,2)[index%2],"lr":(1e-3,3e-3,1e-2)[(index//2)%3],"weight_decay":(1e-4,1e-3,3e-3)[(index//3)%3],"dropout":(0.0,0.1,0.2)[(index//4)%3]})
    unique=[]
    for item in values:
        if item not in unique: unique.append(item)
    return unique[:limit]


def _score_export(model:Mapping[str,Any],row:Sequence[float])->float:
    values=list(row)
    for index,layer in enumerate(model["layers"]):
        values=[float(b)+sum(float(w)*value for w,value in zip(weights,values,strict=True)) for weights,b in zip(layer["weights"],layer["bias"],strict=True)]
        if index<len(model["layers"])-1:
            activation=model["activation"]
            if activation=="tanh": values=[math.tanh(value) for value in values]
            elif activation=="relu": values=[max(0.0,value) for value in values]
            else: values=[0.5*value*(1.0+math.erf(value/math.sqrt(2.0))) for value in values]
    return _sigmoid(values[0])


def _torch_sweep(x:list[list[float]],y:list[int],rows:Sequence[Mapping[str,Any]],folds:int,epochs:int,device:str,configs:int,seeds:int,checkpoint:Path)->tuple[dict[str,Any],dict[str,Any]]:
    completed=[]
    if checkpoint.exists():
        try: completed=json.loads(checkpoint.read_text()).get("completed",[])
        except (ValueError,OSError): completed=[]
    seen={json.dumps(item["config"],sort_keys=True) for item in completed}
    for config in _sweep_configs(configs):
        key=json.dumps(config,sort_keys=True)
        if key in seen: continue
        predictions=[]
        for seed in range(77,77+seeds):
            oof=[0.0]*len(rows)
            for fold in range(folds):
                train_idx=[i for i,row in enumerate(rows) if _hash_fold(row["lineage"],folds)!=fold]; test_idx=[i for i,row in enumerate(rows) if _hash_fold(row["lineage"],folds)==fold]
                model=TorchMLP(len(x[0]),config["hidden"],device,activation=config["activation"],layers=config["layers"],dropout=config["dropout"],seed=seed).fit([x[i] for i in train_idx],[y[i] for i in train_idx],epochs=epochs,lr=config["lr"],l2=config["weight_decay"])
                for i,p in zip(test_idx,model.predict([x[i] for i in test_idx]),strict=True):oof[i]=p
            predictions.append(oof)
        ensemble=[sum(run[i] for run in predictions)/len(predictions) for i in range(len(rows))]
        completed.append({"config":config,"seeds":seeds,"grouped_oof":_metrics(y,ensemble)}); checkpoint.parent.mkdir(parents=True,exist_ok=True); checkpoint.write_text(json.dumps({"completed":completed},indent=2,sort_keys=True)+"\n")
    best=min(completed,key=lambda item:(item["grouped_oof"]["brier"],item["grouped_oof"]["log_loss"]))
    exports=[]
    for seed in range(77,77+seeds):
        config=best["config"]; model=TorchMLP(len(x[0]),config["hidden"],device,activation=config["activation"],layers=config["layers"],dropout=config["dropout"],seed=seed).fit(x,y,epochs=epochs,lr=config["lr"],l2=config["weight_decay"]); exports.append(model.export())
    return {"kind":"ensemble","members":exports}, {"completed":completed,"best":best}


def _torch_intent_sweep(x:list[list[float]],y:list[int],rows:Sequence[Mapping[str,Any]],folds:int,epochs:int,device:str,configs:int,seeds:int,checkpoint:Path)->tuple[dict[str,Any],dict[str,Any],list[float]]:
    state={"intents":{}}
    if checkpoint.exists():
        try: state=json.loads(checkpoint.read_text())
        except (ValueError,OSError): state={"intents":{}}
    all_oof=[0.0]*len(rows); exports={}; diagnostics={}
    for intent in sorted({str(row["intent"]) for row in rows}):
        indexes=[i for i,row in enumerate(rows) if row["intent"]==intent]; local_rows=[rows[i] for i in indexes]; local_x=[x[i] for i in indexes]; local_y=[y[i] for i in indexes]
        completed=state.setdefault("intents",{}).setdefault(intent,[]); seen={json.dumps(item["config"],sort_keys=True) for item in completed}
        for config in _sweep_configs(configs):
            key=json.dumps(config,sort_keys=True)
            if key in seen: continue
            predictions=[]
            for seed in range(177,177+seeds):
                oof=[0.0]*len(local_rows)
                for fold in range(folds):
                    train_idx=[i for i,row in enumerate(local_rows) if _hash_fold(row["lineage"],folds)!=fold]; test_idx=[i for i,row in enumerate(local_rows) if _hash_fold(row["lineage"],folds)==fold]
                    if len(set(local_y[i] for i in train_idx))<2: continue
                    model=TorchMLP(len(x[0]),config["hidden"],device,activation=config["activation"],layers=config["layers"],dropout=config["dropout"],seed=seed).fit([local_x[i] for i in train_idx],[local_y[i] for i in train_idx],epochs=epochs,lr=config["lr"],l2=config["weight_decay"])
                    for i,p in zip(test_idx,model.predict([local_x[i] for i in test_idx]),strict=True):oof[i]=p
                predictions.append(oof)
            ensemble=[sum(run[i] for run in predictions)/len(predictions) for i in range(len(local_rows))]
            completed.append({"config":config,"seeds":seeds,"grouped_oof":_metrics(local_y,ensemble),"oof":ensemble}); checkpoint.parent.mkdir(parents=True,exist_ok=True); checkpoint.write_text(json.dumps(state,indent=2,sort_keys=True)+"\n")
        best=min(completed,key=lambda item:(item["grouped_oof"]["brier"],item["grouped_oof"]["log_loss"])); config=best["config"]
        for local_index,global_index in enumerate(indexes): all_oof[global_index]=best["oof"][local_index]
        members=[]
        for seed in range(177,177+seeds): members.append(TorchMLP(len(x[0]),config["hidden"],device,activation=config["activation"],layers=config["layers"],dropout=config["dropout"],seed=seed).fit(local_x,local_y,epochs=epochs,lr=config["lr"],l2=config["weight_decay"]).export())
        exports[intent]={"kind":"ensemble","members":members}; diagnostics[intent]={"rows":len(indexes),"best_config":config,"grouped_oof":best["grouped_oof"]}
    return {"kind":"intent_ensembles","models":exports},{"by_intent":diagnostics,"grouped_oof":_metrics(y,all_oof)},all_oof


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--ledger",type=Path,default=ROOT/"evals/router-ml-v3/ledger.jsonl")
    parser.add_argument("--output",type=Path,default=ROOT/"evals/router-ml-v3/candidate.json")
    parser.add_argument("--report",type=Path,default=ROOT/"reports/generated/router-ml-v3/fit-report.json")
    parser.add_argument("--hidden",type=int,default=16); parser.add_argument("--epochs",type=int,default=500); parser.add_argument("--folds",type=int,default=5)
    parser.add_argument("--backend",choices=("auto","stdlib","torch"),default="auto"); parser.add_argument("--device",default="cuda")
    parser.add_argument("--sweep",action="store_true"); parser.add_argument("--intent-challenger",action="store_true"); parser.add_argument("--sweep-configs",type=int,default=24); parser.add_argument("--intent-configs",type=int,default=8); parser.add_argument("--seeds",type=int,default=5); parser.add_argument("--checkpoint",type=Path,default=ROOT/"reports/generated/router-ml-v3/sweep-checkpoint.json"); parser.add_argument("--intent-checkpoint",type=Path,default=ROOT/"reports/generated/router-ml-v3/intent-sweep-checkpoint.json")
    parser.add_argument("--minimum-support",type=int,default=15); parser.add_argument("--minimum-precision",type=float,default=.95); parser.add_argument("--minimum-wilson",type=float,default=.85)
    args=parser.parse_args(); rows=_rows(args.ledger)
    if any(row["targets"]["e2b"] is not None for row in rows if row["role"]=="protected_holdout"): raise ValueError("protected labels leaked into training ledger")
    fit=[row for row in rows if row["role"]=="fit" and row["assessment_valid"]]; calibration=[row for row in rows if row["role"]=="calibration" and row["assessment_valid"]]
    cal_fit=[row for row in calibration if _hash_fold(row["lineage"],2)==0]; threshold_rows=[row for row in calibration if _hash_fold(row["lineage"],2)==1]
    names=sorted(set.intersection(*(set(row["features"]) for row in fit+calibration)))
    scaler=Standardizer().fit(_matrix(fit,names)); xfit=scaler.transform(_matrix(fit,names)); yfit=[int(row["targets"]["e2b"]) for row in fit]
    backend=args.backend
    if backend=="auto":
        try:
            import torch
            backend="torch" if torch.cuda.is_available() else "stdlib"
        except ImportError: backend="stdlib"
    comparisons={}; models={}
    for kind in ("logistic","mlp"):
        oof=[0.0]*len(fit)
        for fold in range(args.folds):
            train_idx=[i for i,row in enumerate(fit) if _hash_fold(row["lineage"],args.folds)!=fold]; test_idx=[i for i,row in enumerate(fit) if _hash_fold(row["lineage"],args.folds)==fold]
            model=_candidate(kind,[xfit[i] for i in train_idx],[yfit[i] for i in train_idx],args.hidden,args.epochs,backend,args.device)
            for i,p in zip(test_idx,model.predict([xfit[i] for i in test_idx]),strict=True):oof[i]=p
        comparisons[kind]={"grouped_oof":_metrics(yfit,oof)}
        models[kind]=_candidate(kind,xfit,yfit,args.hidden,args.epochs,backend,args.device)
    try:
        from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
        for name,factory in (
            ("extra_trees",lambda:ExtraTreesClassifier(n_estimators=300,min_samples_leaf=8,class_weight="balanced",n_jobs=-1,random_state=77)),
            ("hist_gradient_boosting",lambda:HistGradientBoostingClassifier(max_iter=250,max_leaf_nodes=15,l2_regularization=.1,random_state=77)),
        ):
            oof=[0.0]*len(fit)
            for fold in range(args.folds):
                train_idx=[i for i,row in enumerate(fit) if _hash_fold(row["lineage"],args.folds)!=fold]; test_idx=[i for i,row in enumerate(fit) if _hash_fold(row["lineage"],args.folds)==fold]
                tree=factory().fit([xfit[i] for i in train_idx],[yfit[i] for i in train_idx]); probabilities=tree.predict_proba([xfit[i] for i in test_idx])[:,1]
                for i,p in zip(test_idx,probabilities,strict=True):oof[i]=float(p)
            comparisons[name]={"grouped_oof":_metrics(yfit,oof),"runtime_exportable":False}
    except ImportError:
        comparisons["tree_baselines"]={"available":False,"reason":"scikit-learn unavailable"}
    sweep=None
    if args.sweep:
        if backend!="torch": raise ValueError("--sweep requires the torch backend")
        export,sweep=_torch_sweep(xfit,yfit,fit,args.folds,args.epochs,args.device,args.sweep_configs,args.seeds,args.checkpoint)
        comparisons["neural_sweep"]={"grouped_oof":sweep["best"]["grouped_oof"],"best_config":sweep["best"]["config"],"configs":len(sweep["completed"]),"seeds":args.seeds}
    intent_sweep=None
    if args.intent_challenger:
        if backend!="torch": raise ValueError("--intent-challenger requires the torch backend")
        intent_export,intent_sweep,_=_torch_intent_sweep(xfit,yfit,fit,args.folds,args.epochs,args.device,args.intent_configs,args.seeds,args.intent_checkpoint)
        comparisons["intent_ensembles"]={**intent_sweep,"configs_per_intent":args.intent_configs,"seeds":args.seeds}
    choices=["logistic","mlp"]+(["neural_sweep"] if sweep else [])+(["intent_ensembles"] if intent_sweep else [])
    champion=min(choices,key=lambda name:(comparisons[name]["grouped_oof"]["brier"],comparisons[name]["grouped_oof"]["log_loss"]))
    model=models["logistic" if champion=="logistic" else "mlp"]
    runtime_model=intent_export if champion=="intent_ensembles" else (export if champion=="neural_sweep" else model.export())
    def predict(population:list[list[float]],population_rows:Sequence[Mapping[str,Any]])->list[float]:
        if champion!="neural_sweep": return model.predict(population)
        return [sum(_score_export(member,row) for member in runtime_model["members"])/len(runtime_model["members"]) for row in population]
    def predict_runtime(population:list[list[float]],population_rows:Sequence[Mapping[str,Any]])->list[float]:
        if champion=="intent_ensembles": return [sum(_score_export(member,row) for member in runtime_model["models"][str(meta["intent"])]["members"])/len(runtime_model["models"][str(meta["intent"])]["members"]) for row,meta in zip(population,population_rows,strict=True)]
        return predict(population,population_rows)
    raw_cal=predict_runtime(scaler.transform(_matrix(cal_fit,names)),cal_fit); ycal=[int(row["targets"]["e2b"]) for row in cal_fit]; calibration_params=_platt(raw_cal,ycal)
    threshold_probs=_calibrate(predict_runtime(scaler.transform(_matrix(threshold_rows,names)),threshold_rows),calibration_params); thresholds=_thresholds(threshold_rows,threshold_probs,minimum_support=args.minimum_support,minimum_precision=args.minimum_precision,minimum_wilson=args.minimum_wilson)
    artifact={"schema_version":"router-ml-v3-runtime-v1","champion":champion,"feature_names":names,"normalization":{"mean":scaler.mean,"scale":scaler.scale},"model":runtime_model,"calibration":{"slope":calibration_params[0],"intercept":calibration_params[1]},"thresholds":thresholds,"fail_closed":{"missing_assessment":True,"non_finite":True,"unknown_intent":True},"fit":{"rows":len(fit),"calibration_rows":len(cal_fit),"threshold_rows":len(threshold_rows),"protected_rows_accessed":0}}
    report={"schema_version":"router-ml-v3-fit-report-v1","backend":backend,"device":args.device if backend=="torch" else "cpu","rows":{"fit":len(fit),"calibration_fit":len(cal_fit),"threshold_selection":len(threshold_rows),"protected_unopened":sum(row["role"]=="protected_holdout" for row in rows)},"group_split":{"folds":args.folds,"key":"lineage","calibration_partition":"lineage_hash"},"comparison":comparisons,"champion":champion,"thresholds":thresholds,"category_coverage":_category_coverage(threshold_rows,threshold_probs,thresholds),"promotion_ready":any(value["selected"]>=args.minimum_support for value in thresholds.values())}
    for path,payload in ((args.output,artifact),(args.report,report)):
        path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"champion":champion,"rows":report["rows"],"promoted_intents":[k for k,v in thresholds.items() if v["selected"]>=30]},sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
