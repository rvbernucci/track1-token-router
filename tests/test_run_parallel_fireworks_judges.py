import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from scripts.run_parallel_fireworks_judges import MODEL, _shard, run_parallel


class FakeProvider:
    model = MODEL
    def __init__(self, worker): self.worker=worker; self.calls=0
    def estimate_upper_bound_usd(self, prompt): return 0.01
    def invoke(self, *, prompt, response_schema, role):
        self.calls += 1
        ids=response_schema["properties"]["judgments"]["items"]["properties"]["id"]["enum"]
        payload={"judgments":[{"id":item,"verdict":"correct","confidence":1.0,"format_valid":True,"rationale":"valid"} for item in ids]}
        provenance=SimpleNamespace(model=MODEL,billable_cost_usd=.01,to_dict=lambda:{"model":MODEL,"request_id":f"w{self.worker}-{self.calls}","billable_cost_usd":.01})
        return SimpleNamespace(payload=payload,provenance=provenance)


class ParallelFireworksJudgesTests(unittest.TestCase):
    def test_parallel_resume_and_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); candidates=root/"candidates.jsonl"; output=root/"judgments.jsonl"
            rows=[{"id":f"c-{i:03d}","engine":"e2b","engine_version":"v1","task_text":"task","answer":"answer"} for i in range(80)]
            candidates.write_text("".join(json.dumps(row)+"\n" for row in rows))
            first=run_parallel(candidates_path=candidates,output=output,provider_factory=FakeProvider,workers=4,batch_size=20,budget_usd=.20)
            second=run_parallel(candidates_path=candidates,output=output,provider_factory=FakeProvider,workers=4,batch_size=20,budget_usd=.20)
            self.assertEqual(80,first["written"]); self.assertEqual(0,first["remaining"])
            self.assertEqual(0,second["written"]); self.assertEqual(80,second["already_complete"])
            self.assertLessEqual(first["cumulative_billable_cost_usd"],.20)
            self.assertEqual(80,len(output.read_text().splitlines()))

    def test_sharding_is_deterministic(self):
        self.assertEqual(_shard("candidate",16),_shard("candidate",16))

    def test_batch_bounds_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"empty.jsonl"; path.write_text("")
            with self.assertRaises(ValueError): run_parallel(candidates_path=path,output=path.with_name("out"),provider_factory=FakeProvider,workers=16,batch_size=19,budget_usd=1)


if __name__ == "__main__": unittest.main()
