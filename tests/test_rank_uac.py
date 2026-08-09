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


class TestApplicationGroup(unittest.TestCase):
    def test_raw_group_survives_department_normalisation(self):
        row = {"dept": "法律學系司法組"}
        rank_uac.identify_department(row)
        self.assertEqual(row["dept"], "法律學系")
        self.assertEqual(row["application_group"], "法律學系司法組")


class TestStar(unittest.TestCase):
    def test_eighth_group_keeps_quota_and_screen_count_separate(self):
        rows = list(rank_uac.load_star("eight"))
        ntu_medicine = next(r for r in rows if r["year"] == "110"
                            and r["school"] == "國立臺灣大學" and r["dept"] == "醫學系")
        self.assertEqual(ntu_medicine["path"], "star_eight")
        self.assertEqual(ntu_medicine["screened"], 24)
        self.assertEqual(ntu_medicine["seats"], 12)


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

    def test_eighth_star_screen_has_its_own_path_in_the_composite(self):
        data = [
            {"school": "S", "dept": "D", "year": "114", "system": "uac",
             "path": "uac", "score": 20.0, "seats": 10},
            {"school": "S", "dept": "D", "year": "114", "system": "uac",
             "path": "star_eight", "score": 100.0, "seats": 10},
        ]
        got = rank_uac.aggregate(data, lambda r: (r["school"], r["dept"]))[0]
        self.assertAlmostEqual(got["score"], 60.0)
        self.assertAlmostEqual(got["seats_avg"], 20.0)
        self.assertAlmostEqual(got["by_path"]["star_eight"], 100.0)


class TestCoverageGaps(unittest.TestCase):
    def test_official_totals_cover_every_modeled_path_and_year(self):
        got = set(rank_uac.load_admission_totals())
        years = {str(year) for year in range(108, 115)}
        paths = {"uac", "tech", "star", "apply", "tech_select"}
        self.assertEqual(got, {(year, path) for year in years for path in paths})

    def test_unprocessed_and_dropped_seats_remain_in_coverage_gap(self):
        data = rows([(0.5, 7)])
        data[0]["path"] = "apply"
        totals = {
            ("114", "apply"): 10,
            ("114", "star"): 5,
            ("114", "tech_select"): 20,
        }
        gaps, residual = rank_uac.coverage_gaps(data, totals)
        self.assertEqual(gaps, {"114": 28})
        self.assertEqual(residual[("114", "apply")], 3)
        self.assertEqual(residual[("114", "star")], 5)
        self.assertEqual(residual[("114", "tech_select")], 20)


if __name__ == "__main__":
    unittest.main()
