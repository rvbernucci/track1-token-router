import json
import random
import unittest

from scripts.run_distribution_shift_arena import _metrics, _sample


class DistributionShiftArenaTests(unittest.TestCase):
    def test_metrics_separate_token_classes(self):
        row={"route_class":"deterministic","current_correct":True,"baseline_correct":True,"current_prompt_tokens":0,"current_completion_tokens":0,"baseline_prompt_tokens":10,"baseline_completion_tokens":2,"current_remote_latency_ms":0}
        result=_metrics([row],7000)
        self.assertEqual(result["token_savings"],12)
        self.assertEqual(result["local_precision"],1)

    def test_sampling_preserves_frozen_rows(self):
        ledger=[{"category":"a","mutation_lineage":"a1","prompt_chars":10},{"category":"b","mutation_lineage":"b1","prompt_chars":20}]
        sampled=_sample(ledger,{"weights":{"a":1,"b":1}},20,random.Random(1),15)
        self.assertTrue(all(row in ledger for row in sampled))


if __name__=="__main__":unittest.main()
