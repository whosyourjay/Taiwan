import unittest

import numpy as np
from scipy import special

from pool import bars, complement, factor, model


def flat_pool(sizes, nodes=5):
    """Every exam drawn evenly from the cohort, so only loadings can bite."""
    values = {exam: np.ones(nodes) for exam in sizes}
    return model.LinearAbilityPool(values, sizes)


TONGCE = complement.VOCATIONAL[1]
SIZES = {"gsat": 120_000.0, "zhikao": 39_000.0}
SIZES.update(dict(zip(complement.VOCATIONAL, (8_000.0, 37_000.0, 21_000.0))))
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

    def base(self):
        values = {"gsat": [0.6, 1.0, 1.4], "zhikao": [0.2, 1.0, 1.8]}
        values.update(dict(zip(complement.VOCATIONAL,
                               ([1.5, 1.0, 0.5], [1.2, 1.0, 0.8], [0.8, 1.0, 1.2]))))
        return model.LinearAbilityPool(values, SIZES)

    def drift(self, loading, tops):
        """Worst gap between the factor reading and the deterministic one."""
        base = self.base()
        pool = factor.FactorPool(base, dict.fromkeys(factor.LOADED, loading))
        return max(float(np.abs(pool.implied_top(exam, tops)
                                - base.abilities(exam, tops)).max())
                   for exam in base.exams)

    def test_a_sharp_pool_approaches_the_density_model(self):
        tops = np.array([0.02, 0.1, 0.3, 0.6, 0.9])
        self.assertLess(self.drift(0.999, tops), self.drift(0.9, tops))
        self.assertLess(self.drift(0.9, tops), self.drift(0.6, tops))

    def test_a_flat_taker_pool_reads_a_bar_straight_off_the_normal(self):
        """With nobody selected in or out, a bar's posterior mean is λ times it."""
        for loading in (0.5, 0.8):
            pool = factor.FactorPool(flat_pool(SIZES),
                                     dict.fromkeys(factor.LOADED, loading))
            for top in (0.01, 0.1, 0.5, 0.9):
                want = special.ndtr(loading * special.ndtri(1 - top))
                self.assertAlmostEqual(pool.implied_top("gsat", [top])[0], want,
                                       places=3)

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
        loadings = {**dict.fromkeys(factor.LOADED, 0.7), "gsat": loading}
        return factor.FactorPool(flat_pool(SIZES), loadings)

    def test_a_gate_lifts_the_student_at_a_rank_bar(self):
        pool = self.pool(0.8)
        score = [factor.rank_score(10.0)]
        self.assertGreater(
            pool.implied_rank("gsat", score, factor.Gates([(0.12,)]))[0],
            pool.implied_rank("gsat", score, factor.Gates([()]))[0],
        )

    def test_a_gate_lifts_more_when_學測_reads_ability_sharply(self):
        score = [factor.rank_score(10.0)]
        lifts = []
        for loading in (0.4, 0.95):
            pool = self.pool(loading)
            plain = pool.implied_rank("gsat", score, factor.Gates([()]))
            gated = pool.implied_rank("gsat", score, factor.Gates([(0.12,)]))
            lifts.append(gated[0] - plain[0])
        self.assertGreater(lifts[1], lifts[0])

    def test_rows_keep_their_own_gates_when_counts_differ(self):
        pool = self.pool(0.8)
        ability = pool.posterior([0.0, 0.0, 0.0], factor.RANK)
        got = factor.Gates([(0.12, 0.25), (), (0.5,)]).factor(pool, "gsat", ability)
        self.assertEqual(got.shape, ability.shape)
        np.testing.assert_allclose(got[1], 1.0)
        self.assertTrue((got[0] <= got[2] + 1e-12).all())
        self.assertTrue((got[0] < got[2]).any())

    def test_no_gates_anywhere_leaves_every_row_alone(self):
        pool = self.pool(0.8)
        ability = pool.posterior([0.0, 0.0], factor.RANK)
        np.testing.assert_allclose(
            factor.Gates([(), ()]).factor(pool, "gsat", ability), 1.0
        )


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


def agreeing_pairs():
    """Bars that already say the same thing, so a fit has little left to do."""
    pool = factor.FactorPool(flat_pool(SIZES), dict.fromkeys(factor.LOADED, 0.9))
    out = []
    for top in (0.02, 0.05, 0.1, 0.2, 0.35, 0.5):
        for exam in ("gsat", TONGCE):
            other = pool.tail(exam, pool.threshold(exam, [top]))[0]
            out.append((bars.Bar("zhikao", 20, top=top),
                        bars.Bar(exam, 20, top=other), 20.0))
    return out


def skewed_pairs():
    """Plain bars that disagree, which a global shrink can always flatten."""
    return [(bars.Bar("zhikao", 20, top=top),
             bars.Bar("gsat", 20, top=min(top * skew, 0.95)), 20.0)
            for top, skew in ((0.02, 1.6), (0.05, 1.5), (0.1, 1.4),
                              (0.2, 1.3), (0.35, 1.2), (0.5, 1.1))]


def gated_pairs():
    """Rank bars behind 學測 gates, paired against plain 指考 bars."""
    return [(bars.Bar("zhikao", 20, top=top),
             bars.Bar("gsat", 20, score=factor.rank_score(gpa), gates=(gate,)), 20.0)
            for top, gpa, gate in ((0.02, 2.0, 0.12), (0.1, 8.0, 0.25),
                                   (0.3, 20.0, 0.5), (0.5, 35.0, 0.75))]


class TestFit(unittest.TestCase):
    def test_it_refuses_an_empty_problem(self):
        with self.assertRaisesRegex(ValueError, "no matched departments"):
            factor.fit([], SIZES, 2)

    def test_it_refuses_a_missing_taker_count(self):
        with self.assertRaisesRegex(ValueError, "missing observed taker counts"):
            factor.fit(agreeing_pairs(), {"gsat": 1.0}, 2)

    def test_matching_bars_leave_almost_nothing_to_explain(self):
        pool, error = factor.fit(agreeing_pairs(), SIZES, 2)
        self.assertLess(error, 1.0)
        self.assertEqual(pool.degrees, complement.degrees(2) + len(factor.LOADED))


def solve(fn, low, high, want, rounds=60):
    """Bisect a monotone increasing fn for the argument giving `want`."""
    for _ in range(rounds):
        mid = (low + high) / 2
        if fn(mid) < want:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def consistent_pairs(truth, gates=(0.25, 0.6), levels=8, tolerance=1e-6, nodes=96):
    """Bars that agree exactly at `truth`, so a fit has a truth to find.

    A strict gate puts a floor under what a rank bar can imply, so some levels
    are unreachable behind it. Those pairs would disagree at the truth itself
    and are dropped rather than fed to the fit as if they were evidence.
    """
    pool = factor.FactorPool(flat_pool(SIZES), truth, nodes)
    out = []
    for level in np.linspace(0.4, 0.95, levels):
        top = solve(lambda t: pool.implied_top("zhikao", [1 - t])[0], 0.0, 1.0, level)
        anchor = bars.Bar("zhikao", 20, top=1 - top)
        left = pool.implied_top("zhikao", [1 - top])[0]
        for gate in gates:
            one = factor.Gates([(gate,)])
            score = solve(lambda s: pool.implied_rank("gsat", [s], one)[0],
                          -6.0, 6.0, level)
            if abs(left - pool.implied_rank("gsat", [score], one)[0]) < tolerance:
                out.append((anchor,
                            bars.Bar("gsat", 20, score=score, gates=(gate,)), 20.0))
        for exam in complement.VOCATIONAL:
            share = solve(lambda t: pool.implied_top(exam, [1 - t])[0], 0.0, 1.0, level)
            if abs(left - pool.implied_top(exam, [1 - share])[0]) < tolerance:
                out.append((anchor, bars.Bar(exam, 20, top=1 - share), 20.0))
    return out


class TestRecovery(unittest.TestCase):
    """A fit that cannot find a loading it planted has nothing to say."""

    TRUTH = {"gsat": 0.85, "tongce": 0.80, "zhikao": 0.90, factor.RANK: 0.55}
    NODES = 48

    def test_the_generated_pairs_agree_at_the_loadings_that_made_them(self):
        observations = consistent_pairs(self.TRUTH)
        self.assertGreater(len(observations), 8)
        packed = factor.Bars(observations, sorted(SIZES))
        pool = factor.FactorPool(flat_pool(SIZES), self.TRUTH)
        left, right = packed.levels(pool)
        self.assertLess(float(np.abs(left - right).max()), 1e-6)
        self.assertAlmostEqual(factor.cost(packed, pool), 0.0, places=10)

    def test_it_recovers_a_loading_the_bars_actually_carry(self):
        observations = consistent_pairs(self.TRUTH, levels=5, nodes=self.NODES)
        fitted, error = factor.fit(observations, SIZES, 2, nodes=self.NODES, steps=30)
        self.assertLess(error, 0.5)
        for measure in self.TRUTH:
            self.assertAlmostEqual(fitted.loadings[measure], self.TRUTH[measure],
                                   delta=0.05, msg=measure)


class TestShrinkage(unittest.TestCase):
    """Every loading falling together pulls the levels toward the middle."""

    def sweep(self, observations, loadings=(0.95, 0.25)):
        packed = factor.Bars(observations, sorted(SIZES))
        base = flat_pool(SIZES)
        raw, scaled = [], []
        for loading in loadings:
            pool = factor.FactorPool(base, dict.fromkeys(factor.LOADED, loading))
            left, right = packed.levels(pool)
            raw.append(float((packed.weights * np.abs(left - right)).sum()))
            scaled.append(factor.cost(packed, pool))
        return raw, scaled

    def test_plain_pairs_alone_reward_shrinking_and_the_cost_does_not(self):
        raw, scaled = self.sweep(skewed_pairs())
        self.assertLess(raw[1], 0.6 * raw[0])
        self.assertLess(abs(scaled[1] - scaled[0]), 0.1 * scaled[0])

    def test_a_gate_makes_the_cost_turn_a_shrink_down(self):
        raw, scaled = self.sweep(gated_pairs())
        self.assertGreater(scaled[1], 2 * scaled[0])


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
            got = pool.implied_rank("gsat", [score], gates)
            self.assertTrue(0.0 < got[0] < 1.0, got)


if __name__ == "__main__":
    unittest.main()
