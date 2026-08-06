import random
import unittest

import rank_uac


def rows(spec, system="uac", year="114"):
    """spec is a list of (norm, seats)."""
    return [
        {"school": "S", "dept": "d%d" % i, "year": year, "system": system,
         "path": system,
         "norm": n, "seats": s}
        for i, (n, s) in enumerate(spec)
    ]


class TestCurve(unittest.TestCase):
    def test_spans_the_seats(self):
        data = rows([(0.9, 10), (0.5, 10), (0.7, 10)])
        rank_uac.curve(data, "norm", "pct", lambda r: (r["year"], r["system"]))
        got = {r["norm"]: r["pct"] for r in data}
        self.assertAlmostEqual(got[0.5], 100 / 6)
        self.assertAlmostEqual(got[0.7], 50.0)
        self.assertAlmostEqual(got[0.9], 500 / 6)

    def test_ties_share_their_midpoint(self):
        data = rows([(0.5, 10), (0.5, 30), (0.9, 10)])
        rank_uac.curve(data, "norm", "pct", lambda r: (r["year"], r["system"]))
        tied = [r["pct"] for r in data if r["norm"] == 0.5]
        self.assertAlmostEqual(tied[0], tied[1])
        self.assertAlmostEqual(tied[0], 40.0)

    def test_weight_by_seats_not_rows(self):
        """A 1-seat department must not count as much as a 100-seat one."""
        data = rows([(0.1, 1), (0.9, 99)])
        rank_uac.curve(data, "norm", "pct", lambda r: (r["year"], r["system"]))
        got = {r["norm"]: r["pct"] for r in data}
        self.assertAlmostEqual(got[0.1], 0.5)
        self.assertAlmostEqual(got[0.9], 50.5)

    def test_years_and_systems_curve_separately(self):
        """Two years on wildly different raw scales must land on one scale."""
        data = rows([(0.9, 10), (0.7, 10)], year="113")
        data += rows([(0.3, 10), (0.1, 10)], year="114")
        rank_uac.curve(data, "norm", "pct", lambda r: (r["year"], r["system"]))
        for year in ("113", "114"):
            got = sorted(r["pct"] for r in data if r["year"] == year)
            self.assertAlmostEqual(got[0], 25.0)
            self.assertAlmostEqual(got[1], 75.0)

    def test_fuzz_is_uniform_and_monotone(self):
        rng = random.Random(0)
        for _ in range(500):
            spec = [(round(rng.uniform(0, 1), 2), rng.randint(1, 50))
                    for _ in range(rng.randint(2, 30))]
            data = rows(spec)
            rank_uac.curve(data, "norm", "pct", lambda r: (r["year"], r["system"]))
            # Seat-weighted mean of a curve is always the midpoint.
            self.assertAlmostEqual(rank_uac.wmean(data, "pct"), 50.0)
            ordered = sorted(data, key=lambda r: r["norm"])
            for a, b in zip(ordered, ordered[1:]):
                self.assertLessEqual(a["pct"], b["pct"])
                if a["norm"] == b["norm"]:
                    self.assertAlmostEqual(a["pct"], b["pct"])
            for r in data:
                self.assertTrue(0.0 <= r["pct"] <= 100.0)


class TestAggregate(unittest.TestCase):
    def test_paths_weight_by_annual_seats_not_years_of_coverage(self):
        data = [
            {"school": "S", "dept": "D", "year": "113", "system": "uac",
             "path": "uac", "score": 0.0, "seats": 10},
            {"school": "S", "dept": "D", "year": "114", "system": "uac",
             "path": "uac", "score": 0.0, "seats": 10},
            {"school": "S", "dept": "D", "year": "114", "system": "uac",
             "path": "star", "score": 100.0, "seats": 10},
        ]
        got = rank_uac.aggregate(data, lambda r: (r["school"], r["dept"]))[0]
        self.assertAlmostEqual(got["score"], 50.0)
        self.assertAlmostEqual(got["seats_avg"], 20.0)

    def test_scores_within_a_path_are_seat_weighted(self):
        data = [
            {"school": "S", "dept": "D", "year": "113", "system": "uac",
             "path": "uac", "score": 0.0, "seats": 10},
            {"school": "S", "dept": "D", "year": "114", "system": "uac",
             "path": "uac", "score": 100.0, "seats": 30},
        ]
        got = rank_uac.aggregate(data, lambda r: (r["school"], r["dept"]))[0]
        self.assertAlmostEqual(got["score"], 75.0)
        self.assertAlmostEqual(got["seats_avg"], 20.0)


if __name__ == "__main__":
    unittest.main()
