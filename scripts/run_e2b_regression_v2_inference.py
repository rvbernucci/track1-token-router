#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Mapping, Sequence
import urllib.request
from contextlib import contextmanager

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.functiongemma_openai_evaluate import assessment_from_openai_response, request_assessment


SCHEMA = "e2b-regression-v2-inference-v1"
SPLITS = ("train", "validation", "final_holdout")
FUNCTIONGEMMA_SHA256 = "74625dd27cf25d54018fa17328a1b1b43f1f09c179e1e4edfaeeffc0c05d9b77"
E2B_SHA256 = "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run canonical FunctionGemma and E2B inference over corpus V2.")
    parser.add_argument("--corpus", type=Path, default=Path("evals/e2b-regression-v2"))
    parser.add_argument("--output", type=Path, default=Path("evals/e2b-regression-v2-inference"))
    parser.add_argument("--config", type=Path, default=Path("configs/e2b-regression-v2-runtime.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/e2b-regression-v2-inference.md"))
    parser.add_argument("--functiongemma-base-url", default="http://127.0.0.1:8091/v1")
    parser.add_argument("--functiongemma-model", default="functiongemma-q8")
    parser.add_argument("--e2b-base-url", default="http://127.0.0.1:9379/v1")
    parser.add_argument("--e2b-model", default="gemma-4-E2B-it")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--pilot", type=int, default=0)
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--only", choices=("functiongemma", "e2b"))
    args = parser.parse_args(argv)
    corpus, output, config, report = map(_absolute, (args.corpus, args.output, args.config, args.report))
    tasks = _load_tasks(corpus)
    expected_count = _expected_count(corpus)
    if args.pilot:
        tasks = _balanced_pilot(tasks, corpus / "metadata.jsonl", args.pilot)
    if not args.check:
        with _exclusive_run(output):
            _run(
                tasks, output, args.functiongemma_base_url, args.functiongemma_model,
                args.e2b_base_url, args.e2b_model, args.timeout_s, args.resume, args.only,
            )
    result = _verify(tasks, output, expected_count=expected_count if not args.pilot else None, only=args.only)
    if not args.pilot and args.only is None and result["passed"]:
        _write_outputs(result, corpus, output, config, report, args)
    print(json.dumps(result, sort_keys=True))
    return 0


def _run(
    tasks: list[dict[str, str]], output: Path, fg_url: str, fg_model: str, e2b_url: str, e2b_model: str,
    timeout: float, resume: bool, only: str | None = None,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fg_path, e2b_path = output / "functiongemma.jsonl", output / "e2b.jsonl"
    if not resume:
        for path in (fg_path, e2b_path):
            if path.exists():
                raise ValueError(f"Output exists; use --resume: {path}")
    fg_done, e2b_done = _ids(fg_path), _ids(e2b_path)
    for task in tasks:
        task_id, prompt = task["task_id"], task["prompt"]
        if only != "e2b" and task_id not in fg_done:
            started = time.monotonic()
            error = None
            assessment = None
            try:
                response = request_assessment(
                    base_url=fg_url, model=fg_model, task_text=prompt, max_tokens=64, timeout_s=timeout
                )
                assessment = assessment_from_openai_response(response).to_dict()
            except Exception as exc:  # Runtime failures are data and must remain resumable.
                error = f"{type(exc).__name__}:{exc}"
            record = {
                "schema_version": SCHEMA, "task_id": task_id, "assessment": assessment, "error": error,
                "latency_ms": (time.monotonic() - started) * 1000, "model": fg_model,
                "prompt_sha256": _text_hash(prompt), "protocol": "raw-prompt-v1",
            }
            _append(fg_path if error is None else output / "functiongemma-failures.jsonl", record)
        if only != "functiongemma" and task_id not in e2b_done:
            started = time.monotonic()
            error = None
            answer = None
            try:
                answer = _request_e2b(e2b_url, e2b_model, prompt, timeout)
            except Exception as exc:
                error = f"{type(exc).__name__}:{exc}"
            record = {
                "schema_version": SCHEMA, "task_id": task_id, "answer": answer, "error": error,
                "latency_ms": (time.monotonic() - started) * 1000, "model": e2b_model,
                "prompt_sha256": _text_hash(prompt), "protocol": "raw-prompt-v1", "max_completion_tokens": 96,
            }
            _append(e2b_path if error is None else output / "e2b-failures.jsonl", record)


def _request_e2b(base_url: str, model: str, prompt: str, timeout: float) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 96,
        "max_completion_tokens": 96,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    answer = result["choices"][0]["message"]["content"]
    if not isinstance(answer, str) or not answer:
        raise ValueError("E2B returned an empty answer.")
    return answer


def _verify(
    tasks: list[dict[str, str]], output: Path, *, expected_count: int | None = None,
    only: str | None = None, require_full: bool | None = None,
) -> dict[str, Any]:
    if require_full is not None:
        expected_count = 2000 if require_full else None
    expected = {row["task_id"]: row for row in tasks}
    engines = (only,) if only else ("functiongemma", "e2b")
    ledgers = {name: _rows(output / f"{name}.jsonl") for name in engines}
    checks: dict[str, bool] = {}
    metrics: dict[str, Any] = {}
    for name, all_rows in ledgers.items():
        rows = [row for row in all_rows if row.get("task_id") in expected]
        failures = [
            row for row in _rows(output / f"{name}-failures.jsonl") if row.get("task_id") in expected
        ]
        ids = [str(row.get("task_id") or "") for row in rows]
        failure_ids = {str(row.get("task_id") or "") for row in failures}
        checks[f"{name}_unique"] = len(ids) == len(set(ids))
        checks[f"{name}_outcome_coverage"] = set(ids) | failure_ids == set(expected)
        checks[f"{name}_prompt_hashes"] = all(
            row.get("prompt_sha256") == _text_hash(expected[row["task_id"]]["prompt"]) for row in rows if row.get("task_id") in expected
        ) and all(
            row.get("prompt_sha256") == _text_hash(expected[row["task_id"]]["prompt"])
            for row in failures if row.get("task_id") in expected
        )
        if name == "functiongemma":
            checks["functiongemma_schema_validity"] = len(rows) / len(expected) >= 0.99 if expected else False
        latencies = sorted(float(row["latency_ms"]) for row in rows)
        metrics[name] = {
            "rows": len(rows), "quarantined_attempts": len(failures), "quarantined_task_ids": len(failure_ids),
            "p50_latency_ms": _percentile(latencies, .5), "p95_latency_ms": _percentile(latencies, .95),
            "sha256": _sha256(output / f"{name}.jsonl") if rows else None,
        }
    checks["full_population"] = len(expected) == expected_count if expected_count is not None else bool(expected)
    return {"schema_version": SCHEMA, "passed": all(checks.values()), "checks": checks, "metrics": metrics}


def _load_tasks(corpus: Path) -> list[dict[str, str]]:
    tasks: list[dict[str, str]] = []
    expansion = (corpus / "splits" / "train.jsonl").is_file()
    for split in SPLITS:
        if expansion:
            translated = "calibration" if split == "validation" else split
            directory = "sealed/tasks" if translated == "final_holdout" else "splits"
            path = corpus / directory / f"{translated}.jsonl"
        else:
            path = corpus / "inputs" / f"{split}.jsonl"
        for row in _rows(path):
            allowed = {"schema_version", "task_id", "prompt"}
            if set(row) not in ({"task_id", "prompt"}, allowed):
                raise ValueError("Runtime input contains non-contract fields.")
            tasks.append({"task_id": str(row["task_id"]), "prompt": str(row["prompt"])})
    if len(tasks) != len({row["task_id"] for row in tasks}):
        raise ValueError("Runtime input task IDs are not unique.")
    return tasks


def _expected_count(corpus: Path) -> int:
    manifest = corpus / "manifest.json"
    if not manifest.is_file():
        return 2000
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    rows = payload.get("rows")
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 1:
        raise ValueError("Corpus manifest rows are invalid.")
    return rows


def _balanced_pilot(tasks: list[dict[str, str]], metadata_path: Path, count: int) -> list[dict[str, str]]:
    if count < 8:
        raise ValueError("Pilot count must cover all eight categories.")
    categories = {row["task_id"]: row["category"] for row in _rows(metadata_path)}
    ordered_categories = sorted(set(categories.values()))
    base, remainder = divmod(count, len(ordered_categories))
    limits = {category: base + int(index < remainder) for index, category in enumerate(ordered_categories)}
    chosen: list[dict[str, str]] = []
    quota: dict[str, int] = {}
    for task in tasks:
        category = categories[task["task_id"]]
        if quota.get(category, 0) < limits[category]:
            chosen.append(task)
            quota[category] = quota.get(category, 0) + 1
    if len(chosen) != count:
        raise ValueError("Pilot population cannot satisfy category balance.")
    return chosen


def _write_outputs(result: Mapping[str, Any], corpus: Path, output: Path, config: Path, report: Path, args: Any) -> None:
    peak_pss_kb = _peak_combined_pss(output / "metrics")
    config.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA, "default_enabled": False, "protocol": "raw-prompt-v1", "context_tokens": 2048,
        "e2b_max_completion_tokens": 96, "cpu_threads": 2, "corpus_manifest_sha256": _sha256(corpus / "manifest.json"),
        "functiongemma_ledger_sha256": result["metrics"]["functiongemma"]["sha256"],
        "e2b_ledger_sha256": result["metrics"]["e2b"]["sha256"], "models": [args.functiongemma_model, args.e2b_model],
        "artifacts": {"functiongemma_sha256": FUNCTIONGEMMA_SHA256, "e2b_sha256": E2B_SHA256},
        "runtimes": {"llama_cpp_release": "b9948", "litert_lm": "0.14.0"},
        "combined_peak_pss_kb": peak_pss_kb,
    }
    config.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# E2B Regression V2 Inference", "", "## Gates", ""]
    lines.extend(f"- {name}: `{value}`" for name, value in sorted(result["checks"].items()))
    lines.extend(["", "## Metrics", "", f"- combined peak PSS: `{peak_pss_kb} KB`"])
    for engine, metrics in sorted(result["metrics"].items()):
        lines.append(
            f"- {engine}: rows `{metrics['rows']}`, quarantined task IDs `{metrics['quarantined_task_ids']}`, "
            f"p50 `{metrics['p50_latency_ms']:.2f} ms`, p95 `{metrics['p95_latency_ms']:.2f} ms`, "
            f"ledger `{metrics['sha256']}`"
        )
    report.write_text("\n".join(lines) + "\n")


def _peak_combined_pss(metrics_dir: Path) -> int:
    peak = 0
    for path in metrics_dir.glob("pss*.csv") if metrics_dir.exists() else ():
        import csv
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                value = row.get("combined_pss_kb")
                if value:
                    peak = max(peak, int(value))
    return peak


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _ids(path: Path) -> set[str]:
    rows = _rows(path)
    ids = [str(row.get("task_id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"Invalid resumable ledger: {path}")
    return set(ids)


def _append(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def _exclusive_run(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    with (output / "inference.lock").open("a+") as handle:
        if fcntl is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Another canonical inference process is already running.") from exc
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    return values[min(len(values) - 1, round((len(values) - 1) * fraction))]


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
