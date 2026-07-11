#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run exact-image live three-route arena.")
    parser.add_argument("--image", default="ghcr.io/rvbernucci/track1-token-router:v3.4.1-full-hybrid")
    parser.add_argument("--tasks", type=Path, default=Path("evals/live-three-route-v1/tasks.json"))
    parser.add_argument("--memory", default="4g")
    parser.add_argument("--cpus", default="2")
    parser.add_argument("--deadline-seconds", type=int, default=570)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated/live-three-route-v1"))
    parser.add_argument("--report", type=Path, default=Path("reports/public/live-three-route-arena.md"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _load_env()
    if not os.getenv("FIREWORKS_API_KEY"):
        raise SystemExit("FIREWORKS_API_KEY is not set")
    result = run(args)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] or not args.check else 1


def run(args):
    tasks = json.loads((ROOT / args.tasks).read_text())
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    image = _image_audit(args.image)
    _command(["docker", "pull", "--platform", "linux/amd64", image["digest_reference"]])
    with tempfile.TemporaryDirectory(prefix="proofroute-live-") as raw:
        root = Path(raw); input_dir = root/"input"; output_dir = root/"output"
        input_dir.mkdir(); output_dir.mkdir()
        official = [{"task_id": row["task_id"], "prompt": row["prompt"]} for row in tasks]
        (input_dir/"tasks.json").write_text(json.dumps(official), encoding="utf-8")
        execution = _run_container(
            image["digest_reference"], input_dir, output_dir,
            memory=args.memory, cpus=args.cpus, deadline=args.deadline_seconds,
            extra_env={}, network="bridge",
        )
        results = json.loads((output_dir/"results.json").read_text()) if (output_dir/"results.json").exists() else []
        logs = _jsonl(output_dir/"run.jsonl")
        scored = _score(tasks, results, logs)
        baseline = _always_fireworks(tasks)
        e2b_failure = _failure_probe(image["digest_reference"], "e2b", real_fireworks=True)
        terminal_failure = _failure_probe(image["digest_reference"], "terminal", real_fireworks=False)
        routes = Counter(row["route_class"] for row in scored)
        remote_tokens = sum(row["remote_tokens"] for row in scored)
        baseline_tokens = sum(row["usage"]["total"] for row in baseline)
        checks = {
            "all_three_routes_have_witnesses": all(routes.get(name, 0) > 0 for name in ("deterministic", "e2b", "fireworks")),
            "output_order_and_ids_match": [row.get("task_id") for row in results] == [row["task_id"] for row in tasks],
            "answer_contract_valid_100pct": len(results) == len(tasks) and all(set(row) == {"task_id", "answer"} and isinstance(row["answer"], str) and row["answer"] for row in results),
            "runtime_failures_at_most_2pct": execution["exit_code"] == 0 and len(logs) == len(tasks),
            "batch_within_570_seconds": execution["wall_seconds"] <= args.deadline_seconds,
            "peak_memory_at_most_3584_mib": execution["peak_memory_mib"] <= 3584,
            "authorized_fireworks_only": all(not row["model"] or row["model"] in _allowed_models() for row in scored),
            "remote_tokens_below_always_fireworks": remote_tokens < baseline_tokens,
            "raw_prompt_envelope_separation": all(row["input_sha256"] == task["prompt_sha256"] and task["task_id"] not in task["prompt"] for row, task in zip(logs, tasks, strict=True)),
            "e2b_failure_falls_through": e2b_failure["exit_code"] == 0 and e2b_failure["route_class"] == "fireworks",
            "terminal_remote_failure_nonzero_no_output": terminal_failure["exit_code"] != 0 and not terminal_failure["results_exists"],
        }
        result = {
            "schema_version": "live-three-route-arena-v1", "passed": all(checks.values()),
            "image": image, "tasks": len(tasks), "routes": dict(routes),
            "correct": sum(row["correct"] for row in scored), "accuracy": sum(row["correct"] for row in scored)/len(scored),
            "remote_tokens": remote_tokens, "always_fireworks_tokens": baseline_tokens,
            "execution": execution, "e2b_failure_probe": e2b_failure,
            "terminal_failure_probe": terminal_failure, "checks": checks,
        }
        (output/"results.jsonl").write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in scored), encoding="utf-8")
        (output/"resources.json").write_text(json.dumps(execution, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        (output/"baseline.jsonl").write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in baseline), encoding="utf-8")
        public = ROOT / args.report; public.parent.mkdir(parents=True, exist_ok=True); public.write_text(_markdown(result), encoding="utf-8")
        audit = ROOT/"submission/final/live-three-route-image-audit.json"; audit.parent.mkdir(parents=True, exist_ok=True); audit.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        return result


def _run_container(image, input_dir, output_dir, *, memory, cpus, deadline, extra_env, network):
    name="proofroute-live-"+uuid.uuid4().hex[:10]
    command=["docker","run","--name",name,"--platform","linux/amd64","--memory",memory,"--cpus",str(cpus),"--network",network,
             "-e","FIREWORKS_API_KEY","-e",f"FIREWORKS_BASE_URL={os.getenv('FIREWORKS_BASE_URL','https://api.fireworks.ai/inference/v1')}",
             "-e",f"ALLOWED_MODELS={','.join(_allowed_models())}","-e","ROUTER_LOG_PATH=/output/run.jsonl"]
    for key,value in extra_env.items(): command.extend(["-e",f"{key}={value}"])
    command.extend(["-v",f"{input_dir}:/input:ro","-v",f"{output_dir}:/output",image])
    started=time.monotonic(); process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    samples=[]; stop=threading.Event(); thread=threading.Thread(target=_sample,args=(name,samples,stop),daemon=True);thread.start()
    try: stdout,stderr=process.communicate(timeout=deadline)
    except subprocess.TimeoutExpired: process.kill();stdout,stderr=process.communicate()
    stop.set();thread.join(timeout=2);wall=time.monotonic()-started
    inspect=_capture(["docker","inspect",name]); state=json.loads(inspect)[0]["State"] if inspect else {}
    _command(["docker","rm","-f",name],check=False)
    return {"exit_code":process.returncode,"wall_seconds":wall,"peak_memory_mib":max(samples,default=0),"oom_killed":state.get("OOMKilled"),"stderr_tail":stderr[-1000:]}


def _failure_probe(image, kind, *, real_fireworks):
    with tempfile.TemporaryDirectory(prefix="proofroute-failure-") as raw:
        root=Path(raw);(root/"input").mkdir();(root/"output").mkdir()
        prompt=("Classify sentiment: The component is excellent. Return exactly positive, negative, or neutral." if kind=="e2b" else "Explain the significance of an unknown future event.")
        (root/"input/tasks.json").write_text(json.dumps([{"task_id":f"{kind}-probe","prompt":prompt}]))
        extra={"E2B_BASE_URL":"http://127.0.0.1:9/v1"} if kind=="e2b" else {"FUNCTIONGEMMA_BASE_URL":"http://127.0.0.1:9/v1","FIREWORKS_BASE_URL":"http://127.0.0.1:9/v1"}
        execution=_run_container(image,root/"input",root/"output",memory="4g",cpus="2",deadline=180,extra_env=extra,network="bridge" if real_fireworks else "none")
        logs=_jsonl(root/"output/run.jsonl");route=_route_class(logs[0]["route"]) if logs else "none"
        return {"exit_code":execution["exit_code"],"route_class":route,"results_exists":(root/"output/results.json").exists(),"wall_seconds":execution["wall_seconds"]}


def _always_fireworks(tasks):
    from scripts.fireworks_microbench import BenchTask, _run_case
    model="accounts/fireworks/models/kimi-k2p7-code"; rows=[]
    for task in tasks:
        bench=BenchTask(task["task_id"],task["category"],"balanced",task["prompt"],task["validator"])
        row=_run_case(base_url=os.getenv("FIREWORKS_BASE_URL","https://api.fireworks.ai/inference/v1"),api_key=os.environ["FIREWORKS_API_KEY"],model=model,task=bench,temperature=0,max_tokens=96,timeout_s=90,max_retries=1,reasoning_effort_override="none")
        rows.append(row)
    return rows


def _score(tasks, results, logs):
    from scripts.fireworks_microbench import _validate
    result_by_id={row["task_id"]:row for row in results};log_by_id={row["task_id"]:row for row in logs};rows=[]
    for task in tasks:
        result=result_by_id.get(task["task_id"],{});log=log_by_id.get(task["task_id"],{});extra=log.get("extra",{})
        validation=_validate(task["validator"],result.get("answer",""))
        rows.append({"task_id":task["task_id"],"category":task["category"],"correct":validation["valid"],"route":log.get("route","missing"),"route_class":_route_class(log.get("route","")),"remote_tokens":log.get("remote_tokens",{}).get("total",0),"model":extra.get("fireworks_model"),"latency_fireworks_ms":extra.get("latency_fireworks_ms",0),"fallback":extra.get("routing_trace",{}).get("fallback")})
    return rows


def _route_class(route):
    if str(route).startswith("solver_"): return "deterministic"
    if str(route).startswith("e2b_"): return "e2b"
    if str(route).startswith("fireworks"): return "fireworks"
    return "other"


def _image_audit(image):
    _command(["docker","pull","--platform","linux/amd64",image])
    inspect=json.loads(_capture(["docker","image","inspect",image]))[0]
    repo_digest=inspect.get("RepoDigests",[])[0]
    labels=inspect.get("Config",{}).get("Labels",{}) or {}
    return {"tag":image,"digest_reference":repo_digest,"platform":f"{inspect['Os']}/{inspect['Architecture']}","revision":labels.get("org.opencontainers.image.revision"),"version":labels.get("org.opencontainers.image.version"),"uncompressed_bytes":inspect.get("Size",0),"compressed_bytes":_compressed_size(repo_digest)}


def _sample(name,samples,stop):
    while not stop.wait(.25):
        result=subprocess.run(["docker","stats","--no-stream","--format","{{.MemUsage}}",name],capture_output=True,text=True)
        if result.returncode==0 and result.stdout.strip():
            value=result.stdout.split("/",1)[0].strip()
            try: samples.append(_memory_mib(value))
            except ValueError: continue


def _memory_mib(value):
    compact=value.replace(" ","")
    for suffix,factor in (("GiB",1024),("MiB",1),("KiB",1/1024),("GB",953.674316),("MB",1/1.048576),("kB",1/1024/1.024),("B",1/1024/1024)):
        if compact.endswith(suffix): return float(compact[:-len(suffix)])*factor
    raise ValueError(f"unsupported memory value: {value}")


def _compressed_size(reference):
    payload=json.loads(_capture(["docker","buildx","imagetools","inspect","--raw",reference]))
    if "manifests" in payload:
        amd=next(item for item in payload["manifests"] if item.get("platform",{}).get("architecture")=="amd64")
        payload=json.loads(_capture(["docker","buildx","imagetools","inspect","--raw",reference.split("@",1)[0]+"@"+amd["digest"]]))
    return sum(int(layer.get("size",0)) for layer in payload.get("layers",[]))


def _allowed_models(): return ["accounts/fireworks/models/minimax-m3","accounts/fireworks/models/kimi-k2p7-code"]


def _load_env():
    from scripts.fireworks_microbench import _load_env_files
    _load_env_files((ROOT/".env.fireworks",ROOT/".env.fireworks.local"))


def _jsonl(path): return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []
def _capture(command): return subprocess.run(command,capture_output=True,text=True,check=True).stdout
def _command(command,check=True): return subprocess.run(command,text=True,check=check,capture_output=True)


def _markdown(r):
    lines=["# Live Three-Route Arena","",f"Decision: `{'PASS' if r['passed'] else 'FAIL'}`","",f"- Image: `{r['image']['digest_reference']}`",f"- Tasks: `{r['tasks']}`",f"- Accuracy: `{r['accuracy']:.2%}`",f"- Routes: `{json.dumps(r['routes'],sort_keys=True)}`",f"- Remote tokens: `{r['remote_tokens']}`",f"- Always-Fireworks tokens: `{r['always_fireworks_tokens']}`",f"- Wall time: `{r['execution']['wall_seconds']:.2f}s`",f"- Peak memory: `{r['execution']['peak_memory_mib']:.2f} MiB`","","## Gates",""]
    lines.extend(f"- [{'x' if value else ' '}] `{name}`" for name,value in r["checks"].items());return "\n".join(lines)+"\n"


if __name__=="__main__": raise SystemExit(main())
