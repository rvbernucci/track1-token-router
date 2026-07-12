from scripts.run_fireworks_champion_v3_preservation import CHAMPIONS, build_subset

def test_preservation_subset_is_exact_balanced_correct_and_lineage_separated():
    rows=build_subset()
    assert len(rows)==80 and len({x["task_id"] for x in rows})==80
    assert all(sum(x["category"]==category for x in rows)==10 for category in CHAMPIONS)
    assert len({(x["source"],x["lineage"]) for x in rows})==80
    assert all(x["model"]==CHAMPIONS[x["category"]] for x in rows)
