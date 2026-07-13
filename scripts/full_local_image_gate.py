#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Sequence
import uuid


FUNCTIONGEMMA_SHA256 = "74625dd27cf25d54018fa17328a1b1b43f1f09c179e1e4edfaeeffc0c05d9b77"
FUNCTIONGEMMA_PLANNER_SHA256 = "ec412795782acd3ed836ac35e058099bfdb1c3218a1ee86aef32905377dbddaf"
E2B_SHA256 = "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c"
DEFAULT_IMAGE = "ghcr.io/rvbernucci/track1-token-router:v3.0.0-full-local"
PROBES = (
    {
        "task_id": "sprint60-cold",
        "prompt": (
            "Read the following movie review and classify its overall sentiment as exactly one of: "
            "positive, negative, or neutral.\n\nReview:\n\"This film is a masterpiece. The "
            "cinematography is breathtaking, the performances are deeply moving, and the score "
            "perfectly complements every scene. I was completely absorbed from start to finish and "
            "will definitely watch it again.\"\n\nRespond with only the single word: positive, negative, or neutral."
        ),
    },
    {
        "task_id": "sprint60-warm",
        "prompt": (
            "Read the following restaurant review and classify its overall sentiment as exactly one of: "
            "positive, negative, or neutral.\n\nReview:\n\"The food arrived cold, the order was "
            "missing two items, and the driver did not respond to calls. I will not be ordering from "
            "here again.\"\n\nRespond with only one word: positive, negative, or neutral."
        ),
    },
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Gate real local inference in the exact public championship image.")
    root.add_argument("--image", default=DEFAULT_IMAGE)
    root.add_argument("--memory", default="4g")
    root.add_argument("--cpus", default="2")
    root.add_argument("--network", default="none")
    root.add_argument("--output-dir", type=Path, default=Path("reports/generated/full-local"))
    root.add_argument("--skip-clean-pull", action="store_true")
    root.add_argument("--json", action="store_true")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if shutil.which("docker") is None:
        raise SystemExit("docker is required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.skip_clean_pull:
        _run(["docker", "image", "rm", args.image], check=False)
        _run(["docker", "pull", "--platform", "linux/amd64", args.image])
    platform = _capture(["docker", "image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", args.image]).strip()
    if platform != "linux/amd64":
        raise SystemExit(f"expected linux/amd64, received {platform}")
    hashes = _model_hashes(args.image)
    expected_hashes = {
        "functiongemma": FUNCTIONGEMMA_SHA256,
        "functiongemma_planner": FUNCTIONGEMMA_PLANNER_SHA256,
        "e2b": E2B_SHA256,
    }
    if hashes != expected_hashes:
        raise SystemExit(f"model hash mismatch: {hashes}")

    with tempfile.TemporaryDirectory(prefix="proofroute-sprint60-") as raw:
        temporary = Path(raw)
        input_dir, output_dir = temporary / "input", temporary / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        (input_dir / "tasks.json").write_text(json.dumps(PROBES, ensure_ascii=False), encoding="utf-8")
        name = "proofroute-sprint60-" + uuid.uuid4().hex[:10]
        command = [
            "docker", "run", "--name", name,
            "--memory", args.memory, "--cpus", str(args.cpus), "--network", args.network,
            "-e", "FIREWORKS_API_KEY=sprint60-local-only",
            "-e", "FIREWORKS_BASE_URL=http://127.0.0.1:9/v1",
            "-e", "ALLOWED_MODELS=accounts/fireworks/models/kimi-k2p7-code",
            "-e", "ROUTER_LOG_PATH=/output/run.jsonl",
            "-v", f"{input_dir}:/input:ro",
            "-v", f"{output_dir}:/output",
            args.image,
        ]
        started = time.time()
        process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        samples: list[dict[str, Any]] = []
        stop = threading.Event()
        sampler = threading.Thread(target=_sample_memory, args=(name, started, samples, stop), daemon=True)
        sampler.start()
        stdout, stderr = process.communicate(timeout=300)
        stop.set()
        sampler.join(timeout=5)
        finished = time.time()
        inspect = json.loads(_capture(["docker", "inspect", name]))[0]
        internal_logs = temporary / "container-logs"
        _run(["docker", "cp", f"{name}:/app/logs", str(internal_logs)], check=False)
        if internal_logs.is_dir():
            for source in internal_logs.rglob("*"):
                if source.is_file():
                    target = args.output_dir / ("runtime-" + source.name)
                    target.write_bytes(source.read_bytes())
        _run(["docker", "rm", name], check=False)
        (args.output_dir / "container.stdout.log").write_text(stdout, encoding="utf-8")
        (args.output_dir / "container.stderr.log").write_text(stderr, encoding="utf-8")
        if process.returncode != 0:
            raise SystemExit(f"container failed with exit {process.returncode}: {stderr[-2000:]}")
        results = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
        logs = [json.loads(line) for line in (output_dir / "run.jsonl").read_text(encoding="utf-8").splitlines() if line]
        (args.output_dir / "run.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in logs),
            encoding="utf-8",
        )
        report = _report(args, platform, hashes, started, finished, inspect, results, logs, samples)
        (args.output_dir / "exact-image-smoke.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (args.output_dir / "process-memory.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in samples), encoding="utf-8")
        (args.output_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True) if args.json else _markdown(report))
        return 0 if report["passed"] else 1


def _model_hashes(image: str) -> dict[str, str]:
    output = _capture([
        "docker", "run", "--rm", "--network", "none", "--entrypoint", "sha256sum", image,
        "/app/artifacts/functiongemma-scale789/functiongemma-scale789-q8_0.gguf",
        "/app/artifacts/functiongemma-tool-planner/functiongemma-tool-planner-q8_0.gguf",
        "/opt/litert/models/gemma4-e2b/model.litertlm",
    ])
    values = [line.split()[0] for line in output.splitlines() if line.strip()]
    if len(values) != 3:
        raise SystemExit("could not inspect embedded model hashes")
    return {"functiongemma": values[0], "functiongemma_planner": values[1], "e2b": values[2]}


def _sample_memory(name: str, started: float, samples: list[dict[str, Any]], stop: threading.Event) -> None:
    while not stop.wait(0.2):
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", name],
            text=True, capture_output=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            continue
        usage = result.stdout.split("/", 1)[0].strip()
        try:
            mib = memory_to_mib(usage)
        except ValueError:
            continue
        samples.append({"elapsed_ms": round((time.time() - started) * 1000), "memory_mib": round(mib, 3)})


def memory_to_mib(value: str) -> float:
    match = re.fullmatch(r"([0-9.]+)\s*([KMG]i?B)", value.strip(), flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"unsupported memory value: {value}")
    number, unit = float(match.group(1)), match.group(2).lower()
    factors = {"kib": 1 / 1024, "kb": 1 / 1000, "mib": 1, "mb": 1 / 1.048576, "gib": 1024, "gb": 953.674316}
    return number * factors[unit]


def _report(args, platform, hashes, started, finished, inspect, results, logs, samples) -> dict[str, Any]:
    timestamps = [datetime.fromisoformat(row["ts"]).timestamp() for row in logs]
    cold_seconds = timestamps[0] - started if timestamps else finished - started
    warm_seconds = timestamps[1] - timestamps[0] if len(timestamps) > 1 else None
    routes = [row.get("route", "") for row in logs]
    remote = [row.get("remote_tokens", {}) for row in logs]
    traces = [row.get("extra", {}).get("routing_trace", {}) for row in logs]
    result_contract = (
        isinstance(results, list) and len(results) == len(PROBES)
        and all(isinstance(row, dict) and set(row) == {"task_id", "answer"} and all(isinstance(value, str) and value for value in row.values()) for row in results)
    )
    peak_mib = max((row["memory_mib"] for row in samples), default=0.0)
    checks = {
        "platform_linux_amd64": platform == "linux/amd64",
        "model_hashes": hashes == {
            "functiongemma": FUNCTIONGEMMA_SHA256,
            "functiongemma_planner": FUNCTIONGEMMA_PLANNER_SHA256,
            "e2b": E2B_SHA256,
        },
        "container_exit_zero": int(inspect["State"]["ExitCode"]) == 0,
        "not_oom_killed": inspect["State"].get("OOMKilled") is False,
        "two_local_routes": len(routes) == 2 and all(route.startswith("e2b_local") for route in routes),
        "zero_fireworks_tokens": len(remote) == 2 and all(int(row.get("prompt", 0)) == 0 and int(row.get("completion", 0)) == 0 for row in remote),
        "official_output_contract": result_contract,
        "peak_memory_at_most_3584_mib": peak_mib <= 3584,
        "cold_at_most_120_seconds": cold_seconds <= 120,
        "warm_at_most_30_seconds": warm_seconds is not None and warm_seconds <= 30,
        "network_disabled": args.network == "none",
    }
    return {
        "schema_version": "full-local-exact-image-smoke-v1",
        "passed": all(checks.values()),
        "image": args.image,
        "platform": platform,
        "limits": {"memory": args.memory, "cpus": str(args.cpus), "network": args.network},
        "model_sha256": hashes,
        "routes": routes,
        "routing_traces": traces,
        "remote_tokens": remote,
        "results": results,
        "metrics": {
            "wall_seconds": round(finished - started, 3),
            "cold_seconds": round(cold_seconds, 3),
            "warm_seconds": round(warm_seconds, 3) if warm_seconds is not None else None,
            "sampled_peak_memory_mib": round(peak_mib, 3),
            "memory_samples": len(samples),
        },
        "checks": checks,
    }


def _markdown(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def _capture(command: list[str]) -> str:
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True)


if __name__ == "__main__":
    raise SystemExit(main())
