from scripts.run_fireworks_champion_v3_reasoning_micro import subset
def test_reasoning_micro_is_ten_unresolved_logic_math_tasks():
    rows=subset();assert len(rows)==10;assert {x["category"] for x in rows}=={"logic_puzzle","math_reasoning"};assert all(sum(y["category"]==x["category"] for y in rows)==5 for x in rows)
