import unittest

import numpy as np
from scipy import special

from pool import bars, factor, model


def flat_pool(sizes, nodes=5):
    """Every exam drawn evenly from the cohort, so only loadings can bite."""
    values = {exam: np.ones(nodes) for exam in sizes}
    return model.LinearAbilityPool(values, sizes)


SIZES = {"gsat": 120_000.0, "tongce": 66_000.0, "zhikao": 39_000.0}
SHARP = dict.fromkeys(factor.LOADED, 0.999)


class TestRankScore(unittest.TestCase):
    def test_a_better_class_rank_scores_higher(self):
        self.assertGreater(factor.rank_score(1.0), factor.rank_score(17.0))

    def test_the_median_of_a_class_sits_at_zero(self):
        self.assertAlmostEqual(float(factor.rank_score(50.0)), 0.0, places=9)

    def test_it_inverts_the_normal_tail(self):
        self.assertAlmostEqual(float(special.ndtr(factor.rank_score(5.0))), 0.95)


class TestQuadrature(unittest.TestCase):
    def test_weights_are_a_probability(self):
        _, weights = factor.quadrature(64)
        self.assertAlmostEqual(float(weights.sum()), 1.0, places=12)

    def test_it_integrates_the_normal_moments(self):
        ability, weights = factor.quadrature(64)
        self.assertAlmostEqual(float(weights @ ability), 0.0, places=10)
        self.assertAlmostEqual(float(weights @ ability ** 2), 1.0, places=10)


class TestDeterministicLimit(unittest.TestCase):
    """At λ = 1 a bar and an ability are the same fact, which is the old model."""

    def test_a_sharp_pool_matches_the_density_model(self):
        base = model.LinearAbilityPool(
            {"gsat": [0.6, 1.0, 1.4], "tongce": [1.5, 1.0, 0.5],
             "zhikao": [0.2, 1.0, 1.8]},
            SIZES,
        )
        pool = factor.FactorPool(base, SHARP, nodes=200)
        tops = np.array([0.02, 0.1, 0.3, 0.6, 0.9])
        for exam in base.exams:
            got = pool.implied_top(exam, tops)
            want = base.abilities(exam, tops)
            np.testing.assert_allclose(got, want, atol=2e-3)

    def test_noise_pulls_a_top_bar_back_toward_the_middle(self):
        base = flat_pool(SIZES)
        sharp = factor.FactorPool(base, SHARP).implied_top("gsat", [0.01])[0]
        noisy = factor.FactorPool(base, dict.fromkeys(factor.LOADED, 0.5))
        self.assertLess(noisy.implied_top("gsat", [0.01])[0], sharp)
        self.assertGreater(noisy.implied_top("gsat", [0.01])[0], 0.5)


class TestTail(unittest.TestCase):
    def test_threshold_inverts_the_tail(self):
        pool = factor.FactorPool(flat_pool(SIZES), dict.fromkeys(factor.LOADED, 0.8))
        tops = np.array([0.01, 0.05, 0.2, 0.5, 0.8])
        np.testing.assert_allclose(pool.tail("gsat", pool.threshold("gsat", tops)),
                                   tops, atol=1e-4)

    def test_a_taker_pool_weighted_to_the_top_lifts_every_bar(self):
        strong = model.LinearAbilityPool(
            {exam: np.array([0.2, 1.0, 1.8]) for exam in SIZES}, SIZES
        )
        even = flat_pool(SIZES, nodes=3)
        loadings = dict.fromkeys(factor.LOADED, 0.9)
        top = [0.1]
        self.assertGreater(
            factor.FactorPool(strong, loadings).implied_top("gsat", top)[0],
            factor.FactorPool(even, loadings).implied_top("gsat", top)[0],
        )


class TestGates(unittest.TestCase):
    def pool(self, loading):
        return factor.FactorPool(flat_pool(SIZES),
                                 dict(factor.LOADED and
                                      {**dict.fromkeys(factor.LOADED, 0.7),
                                       "gsat": loading}))

    def test_a_gate_lifts_the_student_at_a_rank_bar(self):
        pool = self.pool(0.8)
        score = factor.rank_score(10.0)
        plain = factor.Gates([()]).factor(pool, "gsat")
        gated = factor.Gates([(0.12,)]).factor(pool, "gsat")
        self.assertGreater(
            pool.implied_rank("gsat", [score], gated)[0],
            pool.implied_rank("gsat", [score], plain)[0],
        )

    def test_a_gate_lifts_more_when_學測_reads_ability_sharply(self):
        score = factor.rank_score(10.0)
        lifts = []
        for loading in (0.4, 0.95):
            pool = self.pool(loading)
            plain = pool.implied_rank("gsat", [score],
                                      factor.Gates([()]).factor(pool, "gsat"))
            gated = pool.implied_rank("gsat", [score],
                                      factor.Gates([(0.12,)]).factor(pool, "gsat"))
            lifts.append(gated[0] - plain[0])
        self.assertGreater(lifts[1], lifts[0])

    def test_rows_keep_their_own_gates_when_counts_differ(self):
        pool = self.pool(0.8)
        got = factor.Gates([(0.12, 0.25), (), (0.5,)]).factor(pool, "gsat")
        self.assertEqual(got.shape, (3, len(pool.ability)))
        np.testing.assert_allclose(got[1], 1.0)
        self.assertTrue((got[0] < got[2]).all())

    def test_no_gates_anywhere_leaves_every_row_alone(self):
        pool = self.pool(0.8)
        np.testing.assert_allclose(factor.Gates([(), ()]).factor(pool, "gsat"), 1.0)


class TestBars(unittest.TestCase):
    def rows(self):
        return [
            {"year": "110", "school": "A", "dept": "X", "path": "uac",
             "seats": 30, "top": 0.1},
            {"year": "110", "school": "A", "dept": "X", "path": "star",
             "seats": 10, "gpa": "5.0", "gates": "國文頂標13 英文均標11"},
        ]

    def cohort(self):
        class Fake:
            def top_fraction(self, year, label, level):
                return {"國文": 0.12, "英文": 0.5}.get(label)

        return Fake()

    def build(self):
        return bars.observations(
            self.rows(), lambda row: "gsat" if row["path"] == "star" else "zhikao",
            lambda row: row.get("top"), self.cohort(),
        )

    def test_a_department_pairs_its_rank_bar_against_its_exam_bar(self):
        got = self.build()
        self.assertEqual(len(got), 1)
        left, right, weight = got[0][1][0]
        self.assertEqual(weight, 10)
        self.assertEqual({left.exam, right.exam}, {"gsat", "zhikao"})

    def test_the_rank_bar_carries_its_binding_gates(self):
        rank = next(bar for bar in bars.flatten(self.build())[0][:2]
                    if bar.top is None)
        self.assertEqual(rank.gates, (0.12, 0.5))
        self.assertAlmostEqual(rank.score, float(factor.rank_score(5.0)))

    def test_a_gate_almost_everyone_clears_is_dropped(self):
        row = {"year": "110", "gates": "國文底標5"}

        class Loose:
            def top_fraction(self, year, label, level):
                return 0.99

        self.assertEqual(bars.star_gates(row, Loose()), [])

    def test_plain_bars_in_one_bucket_average_by_seats(self):
        got = bars.merge([bars.Bar("gsat", 30, top=0.1),
                          bars.Bar("gsat", 10, top=0.3)])
        self.assertAlmostEqual(got.top, 0.15)
        self.assertEqual(got.seats, 40)


class TestFit(unittest.TestCase):
    def observations(self):
        """Bars generated from a known truth, so the fit has something to find."""
        pool = factor.FactorPool(flat_pool(SIZES),
                                 {"gsat": 0.9, "tongce": 0.9, "zhikao": 0.9,
                                  factor.RANK: 0.6})
        out = []
        for top in (0.02, 0.05, 0.1, 0.2, 0.35, 0.5):
            level = pool.implied_top("zhikao", [top])[0]
            for exam in ("gsat", "tongce"):
                other = pool.tail(exam, pool.threshold(exam, [top]))[0]
                out.append((bars.Bar("zhikao", 20, top=top),
                            bars.Bar(exam, 20, top=other), 20.0))
            self.assertTrue(0.0 < level < 1.0)
        return out

    def test_it_refuses_an_empty_problem(self):
        with self.assertRaisesRegex(ValueError, "no matched departments"):
            factor.fit([], SIZES, 2)

    def test_it_refuses_a_missing_taker_count(self):
        with self.assertRaisesRegex(ValueError, "missing observed taker counts"):
            factor.fit(self.observations(), {"gsat": 1.0}, 2)

    def test_matching_bars_leave_almost_nothing_to_explain(self):
        pool, error = factor.fit(self.observations(), SIZES, 2)
        self.assertLess(error, 1.0)
        self.assertEqual(pool.degrees, 6 + len(factor.LOADED))

    def test_shrinking_every_loading_does_not_pay(self):
        """The cost divides by the spread, so flattening the levels gains nothing."""
        packed = factor.Bars(self.observations(), sorted(SIZES))
        cost = factor._cost(packed)
        base = flat_pool(SIZES)
        sharp = cost(factor.FactorPool(base, dict.fromkeys(factor.LOADED, 0.9)))
        flat = cost(factor.FactorPool(base, dict.fromkeys(factor.LOADED, 0.25)))
        self.assertLess(sharp, flat)


class TestFuzz(unittest.TestCase):
    def test_an_implied_level_always_rises_with_the_bar(self):
        rng = np.random.default_rng(20260809)
        for _ in range(40):
            values = {exam: rng.uniform(0.2, 1.8, 4) for exam in SIZES}
            for value in values.values():
                value *= 3 / (value[1:-1].sum() + value[[0, -1]].sum() / 2)
            loadings = {name: rng.uniform(0.3, 0.98) for name in factor.LOADED}
            pool = factor.FactorPool(model.LinearAbilityPool(values, SIZES), loadings)
            tops = np.sort(rng.uniform(0.01, 0.95, 6))[::-1]
            got = pool.implied_top("gsat", tops)
            self.assertTrue((np.diff(got) > 0).all(), f"{loadings} {tops} {got}")

    def test_every_implied_level_is_a_percentile(self):
        rng = np.random.default_rng(4242)
        for _ in range(40):
            loadings = {name: rng.uniform(0.2, 0.99) for name in factor.LOADED}
            pool = factor.FactorPool(flat_pool(SIZES), loadings)
            gates = factor.Gates([tuple(rng.uniform(0.05, 0.9, rng.integers(0, 4)))])
            score = factor.rank_score(rng.uniform(0.5, 40.0))
            got = pool.implied_rank("gsat", [score], gates.factor(pool, "gsat"))
            self.assertTrue(0.0 < got[0] < 1.0, got)


if __name__ == "__main__":
    unittest.main()
