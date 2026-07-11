#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    tasks = {row["task_id"]: row for row in json.loads((ROOT/"evals/live-three-route-v1/tasks.json").read_text())}
    current = {row["task_id"]: row for row in _jsonl(ROOT/"reports/generated/live-three-route-v1/results.jsonl")}
    runtime = {row["task_id"]: row for row in _jsonl(ROOT/"reports/generated/live-three-route-v1/run-s69.jsonl")}
    baseline = {row["id"]: row for row in _jsonl(ROOT/"reports/generated/live-three-route-v1/baseline.jsonl")}
    if set(tasks) != set(current) or set(tasks) != set(runtime) or set(tasks) != set(baseline):
        raise SystemExit("live task, current and baseline IDs differ")
    rows=[]
    for task_id in tasks:
        task=tasks[task_id];cur=current[task_id];run=runtime[task_id];base=baseline[task_id];offset=int(task_id.rsplit("_",1)[1]);usage=run["remote_tokens"]
        rows.append({"schema_version":"distribution-shift-ledger-v1","task_id":task_id,"category":task["category"],"difficulty":task["difficulty"],"prompt_chars":len(task["prompt"]),"prompt_sha256":task["prompt_sha256"],"mutation_lineage":f"live-{task['category']}-{offset//3}","route_class":cur["route_class"],"current_correct":bool(cur["correct"]),"current_prompt_tokens":int(usage["prompt"]),"current_completion_tokens":int(usage["completion"]),"current_total_tokens":int(usage["total"]),"current_remote_latency_ms":int(cur["latency_fireworks_ms"]),"baseline_correct":bool(base["valid"]),"baseline_prompt_tokens":int(base["usage"]["prompt"]),"baseline_completion_tokens":int(base["usage"]["completion"]),"baseline_total_tokens":int(base["usage"]["total"]),"baseline_latency_ms":int(base["latency_ms"])})
    target=ROOT/"evals/distribution-shift-v1/ledger.jsonl";target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text("".join(json.dumps(row,sort_keys=True)+"\n" for row in rows),encoding="utf-8")
    manifest={"schema_version":"distribution-shift-v1-manifest","rows":len(rows),"ledger_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"source_image_digest":"sha256:6bdf4fcfe5e99181b033a5926208c4e8627fd36e24225c920ae278918ba2ff58","source_arena":"submission/final/live-three-route-image-audit.json","policy":"frozen observed ledger; scenario analysis may only reweight rows"}
    (target.parent/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(manifest,sort_keys=True));return 0


def _jsonl(path): return [json.loads(line) for line in path.read_text().splitlines() if line]
if __name__=="__main__":raise SystemExit(main())
