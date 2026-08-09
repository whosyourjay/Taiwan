"""Tests for the cohort-ability model."""

import unittest

import numpy as np

import pool


class TestAbility(unittest.TestCase):
    def test_uniform_takers_are_their_own_percentile(self):
        # An exam sat by a flat slice of the cohort needs no correction.
        flat = pool.AbilityPool({"e": [1 / 3, 1 / 3, 1 / 3]}, 3)
        for top in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0):
            self.assertAlmostEqual(flat.ability("e", top), 1 - top, places=9)

    def test_top_heavy_exam_pushes_bars_down_the_cohort(self):
        # All takers in the top third: their top 50% is the cohort's top sixth.
        top_third = pool.AbilityPool({"e": [0.0, 0.0, 1.0]}, 3)
        self.assertAlmostEqual(top_third.ability("e", 0.5), 1 - 1 / 6, places=9)
        self.assertAlmostEqual(top_third.ability("e", 1.0), 2 / 3, places=9)

    def test_monotone_and_bounded(self):
        skewed = pool.AbilityPool({"e": [0.5, 0.2, 0.3]}, 3)
        got = [skewed.ability("e", t) for t in np.linspace(0, 1, 21)]
        self.assertEqual(got, sorted(got, reverse=True))
        self.assertTrue(all(0.0 <= g <= 1.0 for g in got))

    def test_clamps_out_of_range_input(self):
        flat = pool.AbilityPool({"e": [0.5, 0.5]}, 2)
        self.assertAlmostEqual(flat.ability("e", -1.0), 1.0)
        self.assertAlmostEqual(flat.ability("e", 2.0), 0.0)


class TestMatched(unittest.TestCase):
    def rows(self):
        return [
            {"year": "110", "school": "A", "dept": "X", "exam": "p", "top": 0.10,
             "seats": 30},
            {"year": "110", "school": "A", "dept": "X", "exam": "q", "top": 0.20,
             "seats": 10},
            {"year": "110", "school": "A", "dept": "Y", "exam": "p", "top": 0.40,
             "seats": 5},
        ]

    def test_pairs_only_departments_in_two_exams(self):
        got = pool.matched(self.rows(), lambda r: r["exam"], lambda r: r["top"])
        self.assertEqual(len(got), 1)
        exam_a, top_a, exam_b, top_b, weight = got[0]
        self.assertEqual((exam_a, exam_b), ("p", "q"))
        self.assertAlmostEqual(top_a, 0.10)
        self.assertAlmostEqual(top_b, 0.20)
        self.assertEqual(weight, 10, "weight is the smaller intake")

    def test_skips_rows_with_no_exam_or_no_bar(self):
        got = pool.matched(self.rows(), lambda r: None, lambda r: r["top"])
        self.assertEqual(got, [])
        got = pool.matched(self.rows(), lambda r: r["exam"], lambda r: None)
        self.assertEqual(got, [])

    def test_several_rows_average_by_seats(self):
        rows = self.rows() + [
            {"year": "110", "school": "A", "dept": "X", "exam": "p", "top": 0.30,
             "seats": 10}
        ]
        got = pool.matched(rows, lambda r: r["exam"], lambda r: r["top"])
        # (0.10*30 + 0.30*10) / 40
        self.assertAlmostEqual(got[0][1], 0.15)


class TestFit(unittest.TestCase):
    def observations_from(self, truth, bars):
        """Bars that agree exactly under `truth`, so a good fit recovers it."""
        out = []
        for top_a in bars:
            ability = truth.ability("a", top_a)
            lo, hi = 0.0, 1.0
            for _ in range(60):
                mid = (lo + hi) / 2
                if truth.ability("b", mid) > ability:
                    lo = mid
                else:
                    hi = mid
            out.append(("a", top_a, "b", (lo + hi) / 2, 1.0))
        return out

    def test_recovers_a_known_warp(self):
        truth = pool.AbilityPool({"a": [1 / 3, 1 / 3, 1 / 3],
                                  "b": [0.15, 0.30, 0.55]}, 3)
        bars = [0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.70]
        observations = self.observations_from(truth, bars)
        self.assertLess(pool.residual(truth, observations), 0.01)

        fitted, error = pool.fit(observations, ["a", "b"], bins=3, smooth=0.0,
                                 restarts=4)
        self.assertLess(error, 0.6, "fit should reproduce agreeing bars")
        for top in (0.05, 0.25, 0.5):
            self.assertAlmostEqual(fitted.ability("a", top),
                                   fitted.ability("b", self.matching(fitted, top)),
                                   places=2)

    def matching(self, fitted, top_a):
        ability = fitted.ability("a", top_a)
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if fitted.ability("b", mid) > ability:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def test_shares_stay_a_distribution(self):
        observations = self.observations_from(
            pool.AbilityPool({"a": [0.4, 0.3, 0.3], "b": [0.2, 0.3, 0.5]}, 3),
            [0.05, 0.2, 0.5],
        )
        fitted, _ = pool.fit(observations, ["a", "b"], bins=3, restarts=2)
        for shares in fitted.shares.values():
            self.assertAlmostEqual(float(shares.sum()), 1.0, places=9)
            self.assertTrue((shares > 0).all())

    def test_no_observations_is_an_error(self):
        with self.assertRaises(ValueError):
            pool.fit([], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
