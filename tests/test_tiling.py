"""Tests for reading exam curves off the department ranking."""

import collections
import unittest

import numpy as np

from pool import tiling


class TestRanked(unittest.TestCase):
    def rows(self):
        return [
            {"school": "A大學", "dept": "電機系", "score": "90"},
            {"school": "A大學", "dept": "資工系", "score": "80"},
            {"school": "B大學", "dept": "中文系", "score": "40"},
        ]

    def test_school_average_backs_up_an_unranked_department(self):
        order = {(r["school"], r["dept"]): float(r["score"]) for r in self.rows()}
        schools = {"A大學": 85.0, "B大學": 40.0}
        placed = tiling.seats_in_order(
            [{"school": "A大學", "dept": "沒排名系", "path": "uac",
              "year": "110", "seats": 10, "ceec_percentile": 0.9}],
            order, schools,
        )
        self.assertEqual(len(placed), 1)
        self.assertAlmostEqual(placed[0][0], 85.0)

    def row(self, path, group, seats=10):
        return {"school": "A大學", "dept": "電機系", "path": path, "year": "110",
                "seats": seats, "ceec_percentile": 0.9, "application_group": group}

    def test_a_split_department_places_each_group_on_its_own_rank(self):
        order = {("A大學", "電機系"): 90.0}
        groups = {("A大學", "電機系", "電機系甲組"): 95.0,
                  ("A大學", "電機系", "電機系乙組"): 70.0}
        placed = tiling.seats_in_order(
            [self.row("uac", "電機系甲組"), self.row("uac", "電機系乙組")],
            order, {"A大學": 90.0}, groups,
        )
        self.assertEqual([score for score, *_ in placed], [95.0, 70.0])

    def test_a_department_wide_bar_ignores_the_group_ranks(self):
        groups = {("A大學", "電機系", "電機系甲組"): 95.0}
        placed = tiling.seats_in_order(
            [self.row("apply", "電機系甲組")], {("A大學", "電機系"): 90.0},
            {"A大學": 90.0}, groups,
        )
        self.assertAlmostEqual(placed[0][0], 90.0)

    def test_an_unscored_group_falls_back_to_its_department(self):
        placed = tiling.seats_in_order(
            [self.row("uac", "沒排名組")], {("A大學", "電機系"): 90.0},
            {"A大學": 90.0}, {("A大學", "電機系", "電機系甲組"): 95.0},
        )
        self.assertAlmostEqual(placed[0][0], 90.0)

    def test_a_department_of_an_unknown_school_is_dropped(self):
        placed = tiling.seats_in_order(
            [{"school": "沒聽過大學", "dept": "系", "path": "uac",
              "year": "110", "seats": 10, "ceec_percentile": 0.9}],
            {}, {},
        )
        self.assertEqual(placed, [])


class TestTile(unittest.TestCase):
    def placed(self):
        # Best first: 20 seats, then 30 with no readable bar, then 50.
        return [
            (90.0, "gsat", 0.10, 20.0),
            (80.0, "gsat", None, 30.0),
            (40.0, "tongce", 0.50, 50.0),
        ]

    def test_seats_without_a_bar_still_occupy_ability(self):
        points, total = tiling.tile(self.placed())
        self.assertEqual(total, 100.0)
        # The 學測 bar sits below its own 20 seats.
        self.assertAlmostEqual(points["gsat"][0][1], 0.80)
        # 統測's bar sits below all 100, the unreadable 30 having pushed it down.
        self.assertAlmostEqual(points["tongce"][0][1], 0.0)
        self.assertEqual(len(points["gsat"]), 1, "the barless row makes no point")

    def test_a_larger_pool_lifts_every_ability(self):
        tight, _ = tiling.tile(self.placed())
        loose, total = tiling.tile(self.placed(), total=200.0)
        self.assertEqual(total, 200.0)
        for exam in tight:
            for (_, close, _), (_, far, _) in zip(tight[exam], loose[exam]):
                self.assertGreater(far, close)

    def test_abilities_fall_as_the_bar_reaches_further_down(self):
        points, _ = tiling.tile([
            (90.0, "gsat", 0.05, 10.0),
            (70.0, "gsat", 0.20, 10.0),
            (50.0, "gsat", 0.60, 80.0),
        ])
        levels = tiling.ability(tiling.curve(points["gsat"]), [0.05, 0.20, 0.60])
        self.assertEqual(list(levels), sorted(levels, reverse=True))


class TestCurve(unittest.TestCase):
    """Ties are pooled by seats, and a rising run is pooled away."""

    def test_departments_sharing_a_bar_pool_by_seats(self):
        # np.interp over the raw dots would land on whichever tie came last.
        tops, levels = tiling.curve([
            (0.5, 0.9, 90.0), (0.5, 0.1, 10.0),
        ])
        np.testing.assert_allclose(tops, [0.5])
        np.testing.assert_allclose(levels, [0.82])

    def test_a_rising_run_is_pooled_into_its_mean(self):
        tops, levels = tiling.curve([
            (0.1, 0.9, 1.0), (0.2, 0.2, 1.0), (0.3, 0.4, 1.0), (0.4, 0.1, 1.0),
        ])
        np.testing.assert_allclose(tops, [0.1, 0.2, 0.3, 0.4])
        np.testing.assert_allclose(levels, [0.9, 0.3, 0.3, 0.1])

    def test_an_already_falling_curve_is_left_alone(self):
        got = [(0.1, 0.9, 1.0), (0.2, 0.5, 2.0), (0.3, 0.2, 3.0)]
        _, levels = tiling.curve(got)
        np.testing.assert_allclose(levels, [0.9, 0.5, 0.2])

    def test_isotonic_never_rises_on_random_input(self):
        rng = np.random.default_rng(20260809)
        for _ in range(300):
            count = int(rng.integers(1, 40))
            levels = rng.uniform(0.0, 1.0, count)
            weights = rng.uniform(0.1, 50.0, count)
            got = tiling.isotonic(levels, weights)
            self.assertEqual(len(got), count)
            self.assertTrue((np.diff(got) <= 1e-9).all())
            # Pooling moves mass around but never creates or destroys it.
            self.assertAlmostEqual(float(got @ weights),
                                   float(levels @ weights), places=9)

    def test_scatter_measures_how_far_apart_equal_bars_land(self):
        points, _ = tiling.tile([
            (90.0, "gsat", 0.05, 50.0),
            (50.0, "gsat", 0.05, 50.0),
        ])
        # Two departments quoting one bar land 50 points apart, so the first
        # decile carries that disagreement rather than hiding it.
        spread = tiling.scatter(points, "gsat", bands=10)
        self.assertAlmostEqual(spread[0], 0.25)

    def test_scatter_skips_bands_too_thin_to_measure(self):
        points, _ = tiling.tile([(90.0, "gsat", 0.05, 10.0)])
        self.assertTrue(np.isnan(tiling.scatter(points, "gsat", bands=10)[0]))


class TestKnots(unittest.TestCase):
    def points(self, count):
        rng = np.random.default_rng(20260810)
        tops = np.linspace(0.01, 0.99, count)
        return [(float(t), float(1 - t + rng.normal(0, 0.02)),
                 float(rng.integers(1, 100))) for t in tops]

    def test_a_curve_is_pinned_at_no_more_places_than_asked(self):
        for count in (3, 8, 20, 24):
            spline = tiling.smooth(self.points(500), count)
            self.assertLessEqual(len(spline.x), count)

    def test_plenty_of_bars_fill_every_place(self):
        self.assertEqual(len(tiling.smooth(self.points(500), 20).x), 20)

    def test_fewer_bars_than_places_keeps_the_bars(self):
        spline = tiling.smooth(self.points(6), 20)
        self.assertEqual(len(spline.x), 6)

    def test_thinning_never_moves_the_ends(self):
        rng = np.random.default_rng(20260810)
        for _ in range(200):
            count = int(rng.integers(2, 60))
            got = self.points(count)
            tops, levels, weights = tiling.pooled(got)
            fitted = tiling.isotonic(levels, weights)
            wanted = int(rng.integers(2, 30))
            places, heights = tiling.knots(1.0 - tops[::-1], fitted[::-1],
                                           weights[::-1], wanted)
            self.assertLessEqual(len(places), wanted)
            self.assertAlmostEqual(places[0], 1.0 - tops[-1])
            self.assertAlmostEqual(heights[0], fitted[-1])
            self.assertAlmostEqual(places[-1], 1.0 - tops[0])
            self.assertTrue((np.diff(places) > 0).all())


class TestSeatShares(unittest.TestCase):
    def placed(self, count=400, seed=20260810):
        rng = np.random.default_rng(seed)
        out = [(float(rng.uniform(0, 100)), str(rng.choice(["gsat", "tongce"])),
                float(rng.uniform(0, 1)), float(rng.integers(1, 90)))
               for _ in range(count)]
        return sorted(out, key=lambda item: -item[0])

    def test_the_stack_fills_the_pool_everywhere(self):
        shares, _ = tiling.seat_shares(self.placed())
        np.testing.assert_allclose(sum(shares.values()), 1.0, atol=1e-12)

    def test_every_share_is_a_fraction(self):
        shares, _ = tiling.seat_shares(self.placed())
        for got in shares.values():
            self.assertTrue((got >= -1e-12).all() and (got <= 1 + 1e-12).all())

    def test_each_exam_keeps_its_own_seats(self):
        placed = self.placed()
        shares, total = tiling.seat_shares(placed)
        want = collections.Counter()
        for _, exam, _, seats in placed:
            want[exam] += seats
        for exam, got in shares.items():
            self.assertAlmostEqual(got.mean() * total, want[exam],
                                   delta=0.02 * want[exam])

    def test_one_exam_alone_fills_the_pool(self):
        shares, _ = tiling.seat_shares([(9.0, "gsat", 0.1, 5.0),
                                        (4.0, "gsat", 0.6, 7.0)])
        np.testing.assert_allclose(shares["gsat"], 1.0)

    def test_the_bottom_of_the_pool_reads_first(self):
        # The worse department is 統測, so 統測 owns the low end of the axis.
        shares, _ = tiling.seat_shares([(9.0, "gsat", 0.1, 50.0),
                                        (1.0, "tongce", 0.9, 50.0)])
        self.assertGreater(shares["tongce"][0], 0.9)
        self.assertGreater(shares["gsat"][-1], 0.9)

    def test_shares_survive_random_pools(self):
        for seed in range(30):
            placed = self.placed(count=int(20 + seed), seed=seed)
            shares, total = tiling.seat_shares(placed, grid=60)
            np.testing.assert_allclose(sum(shares.values()), 1.0, atol=1e-9)
            self.assertAlmostEqual(total, sum(s for *_, s in placed))


class TestFuzz(unittest.TestCase):
    def test_every_ability_is_a_fraction_and_falls_with_the_ranking(self):
        rng = np.random.default_rng(20260809)
        for _ in range(200):
            count = int(rng.integers(1, 30))
            placed = sorted(
                ((float(rng.uniform(0, 100)), "gsat",
                  float(rng.uniform(0, 1)), float(rng.integers(1, 100)))
                 for _ in range(count)),
                key=lambda item: -item[0],
            )
            points, total = tiling.tile(placed)
            levels = [level for _, level, _ in points["gsat"]]
            self.assertTrue(all(-1e-9 <= x <= 1.0 for x in levels))
            self.assertAlmostEqual(min(levels), 0.0)
            self.assertAlmostEqual(total, sum(s for *_, s in placed))


if __name__ == "__main__":
    unittest.main()
