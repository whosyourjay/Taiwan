import unittest

import numpy as np

from rank.ceec_score import ScoreDistributions, calibrate_fallbacks
from parse.ceec import exam_of, mark_midpoint


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


class TestExamName(unittest.TestCase):
    def test_115_underscore_still_identifies_distribution_scale_gsat(self):
        path = "ceec/zhikao/115學測_使用於分發入學採計_各科級分人數累計表.xls"
        self.assertEqual(exam_of(path), "xuece")


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

    def test_formula_buckets_keep_discrete_equal_quantile_totals(self):
        got = self.scores.formula_buckets("114", "國x1.00 英x1.00")
        self.assertEqual(got, [(0.0, 0.5, 0.0, 0.5),
                               (0.5, 1.0, 30.0, 0.5)])

    def test_routes_xuece_and_zhikao_subjects_separately(self):
        self.assertEqual(self.scores.subject_key("114", "國")[1], "xuece")
        self.assertEqual(self.scores.subject_key("114", "數甲")[1], "zhikao")

    def test_missing_art_distribution_returns_none(self):
        self.assertIsNone(
            self.scores.formula_percentile("114", "國x1.00 術x2.00", 100)
        )

    def test_native_gsat_formula_uses_gsat_distributions(self):
        rows = score_rows("110", "gsat", "國文", [(0, 10), (10, 10)])
        rows += score_rows("110", "gsat", "英文", [(0, 10), (20, 10)])
        scores = ScoreDistributions(rows)
        got = scores.gsat_percentile("110", "國文x1.00 英文x1.00", 15)
        self.assertAlmostEqual(got, 0.5, places=9)

    def test_native_gsat_formula_does_not_fall_back_to_other_exam(self):
        self.assertIsNone(
            self.scores.gsat_percentile("114", "國文x1.00", 10)
        )


def bisect_percentile(scores, subjects, cutoff):
    """The bisection that `solve` replaced, kept as an independent answer."""
    low, high = 0.0, 1.0
    for _ in range(60):
        middle = (low + high) / 2
        total = sum(w * scores.subject_score(k, middle) for k, w in subjects)
        low, high = (middle, high) if total < cutoff else (low, middle)
    return (low + high) / 2


class TestSolve(unittest.TestCase):
    """`solve` inverts the weighted total exactly instead of bisecting for it."""

    def random_scores(self, rng, names):
        rows = []
        for name in names:
            marks = sorted(rng.integers(0, 100, int(rng.integers(2, 12))).tolist())
            seats = rng.integers(1, 500, len(marks)).tolist()
            rows += score_rows("114", "zhikao", name, list(zip(marks, seats)))
        return ScoreDistributions(rows)

    def test_matches_bisection_on_random_distributions(self):
        rng = np.random.default_rng(20260809)
        for _ in range(300):
            names = ["a", "b", "c"][: int(rng.integers(1, 4))]
            scores = self.random_scores(rng, names)
            subjects = [
                (("114", "zhikao", name), round(float(rng.uniform(0.5, 3)), 2))
                for name in names
            ]
            grid, table = scores.score_table(tuple(k for k, _ in subjects))
            totals = np.array([w for _, w in subjects]) @ table
            cutoff = float(rng.uniform(totals.min() - 5, totals.max() + 5))
            got = scores.solve(subjects, cutoff)
            self.assertAlmostEqual(
                got, bisect_percentile(scores, subjects, cutoff), places=6
            )

    def test_reproduces_the_cutoff_it_was_given(self):
        scores = self.random_scores(np.random.default_rng(7), ["a", "b"])
        subjects = [(("114", "zhikao", "a"), 1.0), (("114", "zhikao", "b"), 2.0)]
        _, table = scores.score_table(tuple(k for k, _ in subjects))
        totals = np.array([w for _, w in subjects]) @ table
        for cutoff in np.linspace(totals[0], totals[-1], 25):
            percentile = scores.solve(subjects, float(cutoff))
            total = sum(w * scores.subject_score(k, percentile) for k, w in subjects)
            self.assertAlmostEqual(total, float(cutoff), places=6)


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
