from __future__ import annotations

import unittest

from router.core.contracts import AssessmentScores, Intent, TaskAssessment
from scripts.score_shift_stress import PERTURBATION_VALUES, SCORE_NAMES, perturb_assessment


class ScoreShiftStressTests(unittest.TestCase):
    def test_perturbs_every_dimension_across_the_frozen_grid(self) -> None:
        assessment = TaskAssessment(
            intent=Intent.MATH_REASONING,
            scores=AssessmentScores(
                deterministic_fit=5,
                reasoning_demand=5,
                knowledge_uncertainty=5,
                generation_demand=5,
                format_complexity=5,
            ),
        )
        variants = perturb_assessment(assessment)

        self.assertEqual(len(variants), len(SCORE_NAMES) * len(PERTURBATION_VALUES))
        for name in SCORE_NAMES:
            self.assertEqual(
                {variant.scores.to_dict()[name] for variant in variants},
                set(PERTURBATION_VALUES) | {5},
            )


if __name__ == "__main__":
    unittest.main()
