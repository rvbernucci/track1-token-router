#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evals/fireworks-champion-v3"
SELECTION_SEED = "fireworks-champion-v3-800-v1"

SOURCES = (
    {
        "name": "e2b-expansion-v1",
        "metadata": ROOT / "evals/e2b-expansion-v1/metadata.jsonl",
        "inputs": {
            "train": ROOT / "evals/e2b-expansion-v1/splits/train.jsonl",
            "calibration": ROOT / "evals/e2b-expansion-v1/splits/calibration.jsonl",
            "final_holdout": ROOT / "evals/e2b-expansion-v1/sealed/tasks/final_holdout.jsonl",
        },
    },
    {
        "name": "e2b-regression-v2",
        "metadata": ROOT / "evals/e2b-regression-v2/metadata.jsonl",
        "inputs": {
            "train": ROOT / "evals/e2b-regression-v2/inputs/train.jsonl",
            "validation": ROOT / "evals/e2b-regression-v2/inputs/validation.jsonl",
            "final_holdout": ROOT / "evals/e2b-regression-v2/inputs/final_holdout.jsonl",
        },
    },
)


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prompt_sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _rank(row: dict[str, Any]) -> str:
    payload = f"{SELECTION_SEED}:{row['source']}:{row['category']}:{row['lineage']}:{row['task_id']}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _select_arena(population: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for category in sorted({row["category"] for row in population}):
        for source in ("e2b-expansion-v1", "e2b-regression-v2"):
            candidates = [row for row in population if row["category"] == category and row["source"] == source]
            # Regression mutations share lineages; retain one deterministic representative.
            by_lineage: dict[str, dict[str, Any]] = {}
            for row in sorted(candidates, key=_rank):
                by_lineage.setdefault(row["lineage"], row)
            candidates = list(by_lineage.values())
            if source == "e2b-expansion-v1":
                quotas = {"easy": 17, "moderate": 17, "hard": 16}
                chosen = []
                for difficulty, quota in quotas.items():
                    pool = sorted((row for row in candidates if row["difficulty"] == difficulty), key=_rank)
                    if len(pool) < quota:
                        raise ValueError(f"insufficient {category}/{source}/{difficulty}: {len(pool)}")
                    chosen.extend(pool[:quota])
            else:
                chosen = sorted(candidates, key=_rank)[:50]
            if len(chosen) != 50:
                raise ValueError(f"insufficient {category}/{source}: {len(chosen)}")
            selected.extend(chosen)
    if len({(row["source"], row["lineage"]) for row in selected}) != len(selected):
        raise ValueError("selected rows are not lineage-separated")
    return sorted(selected, key=lambda row: (row["category"], row["source"], row["difficulty"], row["task_id"]))


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build(output_dir: Path = OUT) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    seen_ids: set[str] = set()
    seen_prompts: set[str] = set()
    lineage_splits: dict[tuple[str, str], set[str]] = defaultdict(set)

    for source in SOURCES:
        metadata_path = source["metadata"]
        metadata_rows = _rows(metadata_path)
        metadata = {row["task_id"]: row for row in metadata_rows}
        if len(metadata) != len(metadata_rows):
            raise ValueError(f"duplicate metadata task_id in {metadata_path}")
        source_hashes[str(metadata_path.relative_to(ROOT))] = _sha(metadata_path)
        joined: set[str] = set()
        for split, input_path in source["inputs"].items():
            source_hashes[str(input_path.relative_to(ROOT))] = _sha(input_path)
            for item in _rows(input_path):
                task_id = item["task_id"]
                if task_id in seen_ids:
                    raise ValueError(f"duplicate task_id: {task_id}")
                meta = metadata.get(task_id)
                if meta is None:
                    raise ValueError(f"missing metadata join: {source['name']}:{task_id}")
                prompt = item.get("prompt")
                if not isinstance(prompt, str) or not prompt.strip():
                    raise ValueError(f"empty prompt: {task_id}")
                digest = _prompt_sha(prompt)
                if meta.get("prompt_sha256") != digest:
                    raise ValueError(f"divergent prompt hash: {task_id}")
                if digest in seen_prompts:
                    raise ValueError(f"duplicate prompt hash: {digest}")
                if meta.get("split") != split:
                    raise ValueError(f"split mismatch: {task_id}")
                lineage = str(meta.get("mutation_lineage") or meta.get("semantic_seed") or task_id)
                lineage_splits[(source["name"], lineage)].add(split)
                tasks.append({
                    "schema_version": "fireworks-champion-v3-task-v1",
                    "task_id": task_id,
                    "prompt": prompt,
                    "prompt_sha256": digest,
                    "category": meta["category"],
                    "difficulty": meta.get("difficulty", "unspecified"),
                    "split": split,
                    "source": source["name"],
                    "lineage": lineage,
                    "semantic_seed": meta.get("semantic_seed"),
                    "evidence_mode": meta.get("evidence_mode", "semantic"),
                    "output_shape": meta.get("output_shape"),
                    "language": meta.get("language", "en"),
                })
                seen_ids.add(task_id)
                seen_prompts.add(digest)
                joined.add(task_id)
        missing = set(metadata) - joined
        if missing:
            raise ValueError(f"unjoined metadata in {source['name']}: {len(missing)}")

    population = tasks
    population_categories = Counter(row["category"] for row in population)
    if len(population) != 4400 or set(population_categories.values()) != {550} or len(population_categories) != 8:
        raise ValueError(f"unexpected population: rows={len(population)}, categories={dict(population_categories)}")
    leaking = {key: splits for key, splits in lineage_splits.items() if len(splits) > 1}
    if leaking:
        raise ValueError(f"lineage split leakage: {len(leaking)}")

    tasks = _select_arena(population)
    categories = Counter(row["category"] for row in tasks)
    sources = Counter(row["source"] for row in tasks)
    task_path = output_dir / "tasks.jsonl"
    _atomic_jsonl(task_path, tasks)
    manifest = {
        "schema_version": "fireworks-champion-v3-manifest-v1",
        "population_rows": len(population),
        "rows": len(tasks),
        "paired_calls": len(tasks) * 2,
        "categories": dict(sorted(categories.items())),
        "splits": dict(sorted(Counter(row["split"] for row in tasks).items())),
        "sources": dict(sorted(sources.items())),
        "lineages": len({(row["source"], row["lineage"]) for row in tasks}),
        "selection_seed": SELECTION_SEED,
        "selection_policy": "100/category; 50/source/category; one row/lineage; expansion difficulty 17/17/16",
        "task_file": {"path": _display_path(task_path), "sha256": _sha(task_path), "bytes": task_path.stat().st_size},
        "source_files": source_hashes,
        "gates": {
            "exact_population": len(population) == 4400,
            "exact_arena": len(tasks) == 800,
            "balanced_categories": all(value == 100 for value in categories.values()),
            "balanced_sources": sources == {"e2b-expansion-v1": 400, "e2b-regression-v2": 400},
            "unique_task_ids": len({row["task_id"] for row in tasks}) == len(tasks),
            "unique_prompt_hashes": len({row["prompt_sha256"] for row in tasks}) == len(tasks),
            "selected_lineage_isolation": len({(row["source"], row["lineage"]) for row in tasks}) == len(tasks),
            "lineage_split_isolation": not leaking,
            "prompt_hash_join_verified": True,
        },
    }
    _atomic_json(output_dir / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    manifest = build(args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
