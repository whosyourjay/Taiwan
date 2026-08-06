import unittest

from ceec_score import ScoreDistributions, calibrate_fallbacks
from parse_ceec import mark_midpoint


def score_rows(year, exam, subject, scores):
    return [
        {
            "year": year,
            "exam": exam,
            "subject": subject,
            "score": score,
            "seats": seats,
        }
        for score, seats in scores
    ]


class TestScoreDistributions(unittest.TestCase):
    def setUp(self):
        rows = score_rows("114", "xuece", "國文", [(0, 10), (10, 10)])
        rows += score_rows("114", "xuece", "英文", [(0, 10), (20, 10)])
        rows += score_rows("114", "zhikao", "數學甲", [(0, 10), (30, 10)])
        self.scores = ScoreDistributions(rows)

    def test_quantiles_use_tied_midrank_and_interpolate(self):
        key = self.scores.subject_key("114", "國")
        self.assertAlmostEqual(self.scores.subject_score(key, 0.25), 0)
        self.assertAlmostEqual(self.scores.subject_score(key, 0.50), 5)
        self.assertAlmostEqual(self.scores.subject_score(key, 0.75), 10)

    def test_formula_recovers_equal_subject_percentile(self):
        # At p=.5 the interpolated scores are 國=5 and 英=10.
        got = self.scores.formula_percentile("114", "國x1.00 英x1.00", 15)
        self.assertAlmostEqual(got, 0.5, places=9)

    def test_routes_xuece_and_zhikao_subjects_separately(self):
        self.assertEqual(self.scores.subject_key("114", "國")[1], "xuece")
        self.assertEqual(self.scores.subject_key("114", "數甲")[1], "zhikao")

    def test_missing_art_distribution_returns_none(self):
        self.assertIsNone(
            self.scores.formula_percentile("114", "國x1.00 術x2.00", 100)
        )


class TestParseMarks(unittest.TestCase):
    def test_score_band_uses_its_midpoint(self):
        self.assertAlmostEqual(mark_midpoint("49.00 - 49.99"), 49.495)
        self.assertAlmostEqual(mark_midpoint("100.00"), 100.0)
        self.assertIsNone(mark_midpoint("分數"))


class TestFallbackCalibration(unittest.TestCase):
    def test_preserves_raw_position_on_ceec_scale(self):
        rows = [
            {
                "year": "114", "norm": 0.2, "basis": 0.1,
                "ceec_percentile": 0.1, "seats": 10,
            },
            {
                "year": "114", "norm": 0.8, "basis": 0.9,
                "ceec_percentile": 0.9, "seats": 10,
            },
            {"year": "114", "norm": 0.5, "basis": 0.5, "seats": 5},
        ]
        self.assertEqual(calibrate_fallbacks(rows), 1)
        self.assertAlmostEqual(rows[-1]["basis"], 0.5)
        self.assertTrue(rows[-1]["ceec_fallback"])


if __name__ == "__main__":
    unittest.main()
