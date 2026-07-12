from scripts.run_fireworks_champion_v3_ablation import SYSTEM, build_subset, challenger_cap


def test_champion_v3_ablation_is_compact_stratified_failure_subset():
    rows=build_subset()
    assert len(rows)==80
    assert all(sum(item["category"]==row["category"] for item in rows)==10 for row in rows)
    assert len({row["task_id"] for row in rows})==80


def test_champion_v3_ablation_caps_json_and_code_without_expanding_short_tasks():
    assert challenger_cap({"task_id":"n","prompt":"Return JSON entities", "category":"ner"})>=384
    assert challenger_cap({"task_id":"c","prompt":"Write Python code", "category":"code_generation"})==512
    assert "untrusted data" in SYSTEM
