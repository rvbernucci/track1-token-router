import unittest

from scripts.analyze_functiongemma_score_collapse import analyze


class FunctionGemmaScoreCollapseTests(unittest.TestCase):
    def test_detects_dominant_score_vector(self) -> None:
        rows = [{
            "assessment_valid": True, "predicted_intent": "factual_qa",
            "scores": {"deterministic_fit": 1, "reasoning_demand": 1, "knowledge_uncertainty": 1, "generation_demand": 1, "format_complexity": 1},
        } for _ in range(10)]
        result = analyze(rows)
        self.assertTrue(result["retraining_indicated"])
        self.assertEqual(result["by_intent"]["factual_qa"]["dominant_vector_share"], 1.0)


if __name__ == "__main__":
    unittest.main()
