import unittest

from scripts.analyze_e2b_boundary_evidence import _cohort, _length_band, _normalized_hash


class E2BBoundaryEvidenceAnalysisTests(unittest.TestCase):
    def test_normalized_hash_ignores_case_unicode_form_and_whitespace(self):
        self.assertEqual(_normalized_hash(" Cafe\u0301  TEST "), _normalized_hash("caf\u00e9 test"))

    def test_cohort_reports_false_positive_risk(self):
        result = _cohort([{"correct": True}, {"correct": False}])
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["precision"], .5)

    def test_length_bands_are_stable(self):
        self.assertEqual(_length_band(159), "short_lt_160")
        self.assertEqual(_length_band(160), "medium_160_499")
        self.assertEqual(_length_band(500), "long_gte_500")


if __name__ == "__main__":
    unittest.main()
