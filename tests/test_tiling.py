"""Tests for reading exam curves off the department ranking."""

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
        levels = tiling.ability(points, "gsat", [0.05, 0.20, 0.60])
        self.assertEqual(list(levels), sorted(levels, reverse=True))

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
