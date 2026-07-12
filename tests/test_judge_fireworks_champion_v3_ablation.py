import json
from scripts.judge_fireworks_champion_v3_ablation import rows, write


def test_champion_v3_ablation_jsonl_write_is_atomic_and_roundtrips(tmp_path):
    path=tmp_path/"rows.jsonl"; expected=[{"task_id":"a","correct":True},{"task_id":"b","correct":False}]
    write(path,expected)
    assert rows(path)==expected
    assert not path.with_suffix(".jsonl.tmp").exists()
