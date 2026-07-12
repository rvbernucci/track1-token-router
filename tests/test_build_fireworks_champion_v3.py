from __future__ import annotations

import hashlib
import json

from scripts.build_fireworks_champion_v3 import build


def test_build_fireworks_champion_v3_freezes_exact_balanced_population(tmp_path):
    manifest = build(tmp_path)
    assert manifest["population_rows"] == 4400
    assert manifest["rows"] == 800
    assert manifest["paired_calls"] == 1600
    assert set(manifest["categories"].values()) == {100}
    assert all(manifest["gates"].values())
    tasks = [json.loads(line) for line in (tmp_path / "tasks.jsonl").read_text().splitlines()]
    assert len({row["task_id"] for row in tasks}) == 800
    assert len({row["prompt_sha256"] for row in tasks}) == 800
    assert all(hashlib.sha256(row["prompt"].encode()).hexdigest() == row["prompt_sha256"] for row in tasks)


def test_build_fireworks_champion_v3_preserves_source_splits_and_lineages(tmp_path):
    build(tmp_path)
    tasks = [json.loads(line) for line in (tmp_path / "tasks.jsonl").read_text().splitlines()]
    lineage_splits = {}
    for row in tasks:
        lineage_splits.setdefault((row["source"], row["lineage"]), set()).add(row["split"])
    assert all(len(splits) == 1 for splits in lineage_splits.values())
    assert {row["source"] for row in tasks} == {"e2b-expansion-v1", "e2b-regression-v2"}
    assert all(sum(row["source"] == source and row["category"] == category for row in tasks) == 50 for source in {"e2b-expansion-v1", "e2b-regression-v2"} for category in {row["category"] for row in tasks})
