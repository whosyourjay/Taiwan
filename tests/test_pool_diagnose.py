import unittest

import numpy as np

from pool import bars, diagnose, factor, model

SIZES = {"gsat": 120_000.0, "tongce": 66_000.0, "zhikao": 39_000.0}


def pool_of(loading):
    values = {exam: np.ones(4) for exam in SIZES}
    return factor.FactorPool(model.LinearAbilityPool(values, SIZES),
                             dict.fromkeys(factor.LOADED, loading))


class TestSpread(unittest.TestCase):
    def test_it_measures_the_widest_disagreement(self):
        self.assertAlmostEqual(diagnose.spread({"a": 90.0, "b": 70.0, "c": 80.0}), 20.0)

    def test_one_path_alone_has_no_spread(self):
        self.assertIsNone(diagnose.spread({"a": 90.0, "b": None}))

    def test_a_missing_path_never_counts_as_a_low_score(self):
        self.assertAlmostEqual(diagnose.spread({"a": 90.0, "b": None, "c": 85.0}), 5.0)


class TestCell(unittest.TestCase):
    def test_a_missing_value_prints_a_dash_in_its_column(self):
        self.assertEqual(diagnose.cell(None, 6), "     -")

    def test_a_value_keeps_one_decimal(self):
        self.assertEqual(diagnose.cell(93.25, 8), "    93.2")


class TestLevels(unittest.TestCase):
    def found(self):
        return {
            ("110", "A", "X"): {
                "zhikao": bars.Bar("zhikao", 30, top=0.1),
                factor.RANK: bars.Bar("gsat", 10, score=factor.rank_score(5.0),
                                      gates=(0.25,)),
            },
            ("110", "B", "Y"): {"tongce": bars.Bar("tongce", 20, top=0.4)},
        }

    def test_every_department_keeps_its_own_buckets(self):
        got = diagnose.levels(pool_of(0.9), self.found())
        self.assertEqual(sorted(got), [("110", "A", "X"), ("110", "B", "Y")])
        self.assertEqual(sorted(got[("110", "A", "X")]), ["rank", "zhikao"])
        self.assertEqual(sorted(got[("110", "B", "Y")]), ["tongce"])

    def test_levels_are_percentage_points(self):
        for row in diagnose.levels(pool_of(0.9), self.found()).values():
            for level in row.values():
                self.assertTrue(0.0 < level < 100.0, level)

    def test_noise_pulls_a_high_bar_below_its_exact_reading(self):
        found = self.found()
        exact = diagnose.levels(diagnose.deterministic(pool_of(0.5)), found)
        noisy = diagnose.levels(pool_of(0.5), found)
        key = ("110", "A", "X")
        self.assertLess(noisy[key]["zhikao"], exact[key]["zhikao"])


class TestDeterministic(unittest.TestCase):
    def test_it_keeps_the_densities_and_sharpens_every_measurement(self):
        pool = pool_of(0.6)
        sharp = diagnose.deterministic(pool)
        self.assertEqual(set(sharp.loadings.values()), {factor.CEILING})
        for exam in pool.exams:
            np.testing.assert_allclose(sharp.pool.values[exam], pool.pool.values[exam])


if __name__ == "__main__":
    unittest.main()
